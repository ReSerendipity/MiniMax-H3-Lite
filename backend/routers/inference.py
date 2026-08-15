"""
MM·H3 工作台 — 推理客户端
PRD §6: 对接本地 H3-Base 推理服务
默认后端 diffusers（进程内 ModularPipeline，脱离 ComfyUI 可运行）；
可选后端 comfyui（消费同一任务规格层，见 backend/comfy_workflow.py）。
参数映射以 backend/h3/spec.py（源自三份官方工作流）为单一事实源。
"""
import sys
import json
import time
import subprocess
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_db, new_id, now_iso
from config import settings
from h3 import spec as h3
from engine_registry import active_backend
from settings_store import resolve as resolve_setting


def _build_params(task_row: dict) -> dict:
    """
    将任务行规范化为后端无关的结构化参数。
    帧长 / 分辨率 / 任务类型 / 参考素材分组均来自 h3.spec（官方工作流语义）。
    """
    payload = json.loads(task_row["payload"]) if isinstance(task_row["payload"], str) else task_row["payload"]
    prompt = payload.get("prompt", "")
    params = payload.get("params", {})

    mode = task_row["mode"]
    duration = params.get("duration", 8)
    aspect = params.get("aspect", "16:9")
    resolution = params.get("resolution", "768P")
    short_side = 768 if resolution == "768P" else 1440  # 2K 未开源，暂不支持
    multiple = 32 if active_backend() == "comfyui" else 2
    width, height = h3.resolution_for(aspect, short_side=short_side, multiple=multiple)
    num_frames = h3.frames_for_duration(duration)
    task_type = h3.MODE_TO_TASK.get(mode, h3.T2VA)

    # 参考素材（assets → 本地路径）
    ref_ids = payload.get("ref_ids", [])
    refs = []
    if ref_ids:
        db = get_db()
        for rid in ref_ids:
            asset = db.execute("SELECT * FROM assets WHERE id=?", (rid,)).fetchone()
            if asset:
                refs.append({
                    "id": rid,
                    "kind": asset["kind"],
                    "path": str(settings.BASE_DIR / asset["path"]),
                    "paired_video": None,  # 从 shot_refs 查询填充
                })
        # 查询 shot_refs 表获取配对关系
        shot_row = db.execute("SELECT project_id FROM shots WHERE id=?", (task_row["shot_id"],)).fetchone()
        if shot_row:
            pair_rows = db.execute(
                "SELECT asset_id, pair_asset_id FROM shot_refs WHERE shot_id=?",
                (task_row["shot_id"],),
            ).fetchall()
            pair_map = {r["asset_id"]: r["pair_asset_id"] for r in pair_rows if r["pair_asset_id"]}
            for ref in refs:
                if ref["id"] in pair_map:
                    ref["paired_video"] = pair_map[ref["id"]]
        db.close()

    # 首帧 / 末帧（fl2va）
    first_image = None
    last_image = None
    if task_type == h3.FL2VA:
        images = [r["path"] for r in refs if r["kind"] == "image"]
        if images:
            if mode == "last_frame":
                last_image = images[0]
            else:
                first_image = images[0]
                if mode == "first_last" and len(images) > 1:
                    last_image = images[1]

    # G7: i2v「跟随首帧图像尺寸」——首帧图尺寸决定 width/height（768p 短边 + 32 倍数对齐 + 1344 封顶）
    if task_type == h3.FL2VA and params.get("size_mode") == "follow_first" and first_image:
        try:
            from PIL import Image
            with Image.open(first_image) as im:
                iw, ih = im.size
            sw = h3.SHORT_SIDE  # 768
            cap = h3.MAX_DIM    # 1344
            m = 32 if active_backend() == "comfyui" else 2
            if iw >= ih:
                nw, nh = sw * iw / ih, sw
            else:
                nh, nw = sw * ih / iw, sw
            # round up to multiple, cap to MAX_DIM
            nw = min(((int(nw) + m - 1) // m) * m, cap)
            nh = min(((int(nh) + m - 1) // m) * m, cap)
            if nw > 0 and nh > 0:
                width, height = nw, nh
        except Exception:
            pass  # PIL 不可用时跳过，保持原始 resolution_for 值

    return {
        "task_type": task_type,
        "mode": mode,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "duration": duration,
        "fps": settings.FPS,
        "audio_sample_rate": settings.AUDIO_SAMPLE_RATE,
        "refs": refs,
        "first_image": first_image,
        "last_image": last_image,
        "seed": params.get("seed") or int(time.time() * 1000) % (2 ** 32),
        "ref_image_size": params.get("ref_image_size") or resolve_setting("ref_image_size", settings.REF_IMAGE_SIZE),
        "sampler_name": params.get("sampler") or resolve_setting("sampler", settings.SAMPLER_NAME),
        "steps": int(params.get("steps") or resolve_setting("steps", settings.STEPS)),
        "denoise": float(params.get("denoise") or resolve_setting("denoise", settings.DENOISE)),
    }


# ── 缩略帧提取 ────────────────────────────────────
def _extract_thumbnail(video_path: str, output_path: str, time_offset: float = 0.5):
    """使用 ffmpeg 提取首帧作为缩略图"""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(time_offset), "-i", video_path,
             "-frames:v", "1", "-f", "image2", output_path],
            capture_output=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        # ffmpeg 不可用或超时，跳过缩略图
        pass


def run_inference(task_id: str) -> dict:
    """
    执行推理任务，返回 {"asset_id": "...", "path": "...", "thumbnail": "..."}
    按当前激活引擎（engine_registry.active_backend）选择后端。
    """
    db = get_db()
    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        db.close()
        raise ValueError(f"任务不存在: {task_id}")

    params = _build_params(dict(row))
    backend = active_backend()

    if backend == "diffusers":
        result = _run_diffusers(params)
    elif backend == "comfyui":
        result = _run_comfyui(params)
    else:
        raise RuntimeError(f"推理后端 {backend} 尚未实现，请切换为 diffusers（本地）或 comfyui")

    # 落盘 + 资产记录
    aid = new_id("ast_")
    ext = ".mp4"
    stored_name = f"{aid}{ext}"
    dest = settings.ASSETS_DIR / stored_name

    # 写入结果文件
    if isinstance(result, (bytes, bytearray)):
        dest.write_bytes(result)
    elif isinstance(result, str) and Path(result).exists():
        import shutil
        shutil.move(result, str(dest))
    else:
        raise RuntimeError(f"推理未产出有效文件: {result!r}")

    size = dest.stat().st_size if dest.exists() else 0

    # 提取缩略帧
    thumb_name = f"{aid}_thumb.jpg"
    thumb_path = settings.ASSETS_DIR / thumb_name
    if dest.exists() and size > 0:
        _extract_thumbnail(str(dest), str(thumb_path))

    # 写资产记录
    meta = json.dumps({
        "thumbnail": f"assets/{thumb_name}" if thumb_path.exists() else None,
        "width": params["width"],
        "height": params["height"],
        "duration": params["duration"],
        "fps": params["fps"],
    }, ensure_ascii=False)
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
        (aid, "result", f"assets/{stored_name}", "video/mp4", size, meta),
    )
    db.commit()
    db.close()

    return {"asset_id": aid, "path": f"assets/{stored_name}"}


def _run_diffusers(params: dict) -> str:
    """
    使用 diffusers ModularPipeline 本地推理（PRD §6.2: MiniMaxAI/MiniMax-H3）。
    输入映射按 h3.spec：t2va 纯文本；fl2va 传 image(+last_image)；ref2va 传 ref_images/ref_videos/ref_audios。
    依赖缺失或推理失败时抛出 RuntimeError（任务如实 failed），绝不假成功。
    """
    try:
        from diffusers import ModularPipeline
        import torch
    except ImportError as e:
        raise RuntimeError(
            "diffusers 推理后端依赖缺失，请先安装：pip install diffusers torch"
        ) from e

    model_id = settings.MODEL_PATH or settings.MODEL_NAME
    tmp_path = settings.ASSETS_DIR / f"tmp_{uuid.uuid4().hex}.mp4"
    try:
        pipe = ModularPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
        if settings.QUANTIZATION:
            pipe.enable_model_cpu_offload()

        inputs: dict = {
            "prompt": params["prompt"],
            "width": params["width"],
            "height": params["height"],
            "num_frames": params["num_frames"],
            "fps": params["fps"],
            "audio_sample_rate": params["audio_sample_rate"],
        }
        if params["task_type"] == h3.FL2VA:
            if params.get("first_image"):
                inputs["image"] = params["first_image"]
            if params.get("last_image"):
                inputs["last_image"] = params["last_image"]
        elif params["task_type"] == h3.REF2VA:
            grouped = h3.group_refs(params["refs"])
            # ref_image_size：match/max 缩放参考图像（diffusers 后端不直接接受该参数，按语义预处理）
            ref_size_mode = params.get("ref_image_size") or "match"
            if grouped["image"]:
                inputs["ref_images"] = _scale_ref_images(grouped["image"], params["width"], params["height"], ref_size_mode)
            if grouped["video"]:
                inputs["ref_videos"] = grouped["video"]
            if grouped["audio"]:
                inputs["ref_audios"] = grouped["audio"]
            if grouped.get("ref_video_audios"):
                # 若 ModularPipeline 支持配对音轨参数则透传；否则按顺序拆出独立列表
                inputs["ref_video_audios"] = grouped["ref_video_audios"]

        output = pipe(**inputs)
        output.save(str(tmp_path))
    except Exception as e:
        raise RuntimeError(f"diffusers 推理失败: {type(e).__name__}: {e}") from e

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError("diffusers 推理未产出有效视频文件")
    return str(tmp_path)


def _scale_ref_images(paths, width, height, mode):
    """按 ref_image_size 语义缩放参考图像（PIL，避免新依赖：ffmpeg scale 也可但 PIL 更简洁）。
    match：缩放到生成分辨率（更快）；
    max：短边保持 ≤2048（更强身份保真）。
    """
    try:
        from PIL import Image
    except ImportError:
        return paths  # Pillow 不可用时跳过缩放，原样返回
    import tempfile
    out = []
    for p in paths:
        try:
            im = Image.open(p)
            if mode == "match":
                im = im.resize((width, height), Image.LANCZOS)
            else:  # max：短边 ≤2048，等比缩放
                w, h = im.size
                short = min(w, h)
                if short > 2048:
                    k = 2048 / short
                    im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
            dst = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            dst.close()
            im.convert("RGB").save(dst.name)
            out.append(dst.name)
        except Exception:
            out.append(p)  # 单张失败回退原路径
    return out


def _run_comfyui(params: dict) -> str:
    """委托 ComfyUI 可选执行器（backend/comfy_workflow.py），按任务类型选择官方权重。"""
    from comfy_workflow import run_comfyui

    task_type = params["task_type"]
    scheduler = h3.REF2VA_SCHEDULER if task_type == h3.REF2VA else h3.SCHEDULER
    # 高级参数覆盖：用户显式传值时优先于全局/默认
    if params.get("scheduler_override"):
        scheduler = params["scheduler_override"]
    grouped = h3.group_refs(params["refs"]) if task_type == h3.REF2VA else {}
    task = {
        **params,
        "unet_model": settings.MODEL_REF2VA if task_type == h3.REF2VA else settings.MODEL_FL2VA,
        "clip_model": settings.MODEL_CLIP,
        "vae_video_model": settings.MODEL_VAE_VIDEO,
        "vae_audio_model": settings.MODEL_VAE_AUDIO,
        "scheduler": scheduler,
        "first_frame_path": params.get("first_image"),
        "last_frame_path": params.get("last_image"),
        "ref_image_paths": [r["path"] for r in params["refs"] if r["kind"] == "image"],
        "ref_video_paths": [r["path"] for r in params["refs"] if r["kind"] == "video"],
        "ref_audio_paths": [r["path"] for r in params["refs"] if r["kind"] == "audio"],
        "ref_video_audios": grouped.get("ref_video_audios", []),
    }
    return run_comfyui(task)
