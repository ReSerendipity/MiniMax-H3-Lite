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
                })
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
            if grouped["image"]:
                inputs["ref_images"] = grouped["image"]
            if grouped["video"]:
                inputs["ref_videos"] = grouped["video"]
            if grouped["audio"]:
                inputs["ref_audios"] = grouped["audio"]

        output = pipe(**inputs)
        output.save(str(tmp_path))
    except Exception as e:
        raise RuntimeError(f"diffusers 推理失败: {type(e).__name__}: {e}") from e

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError("diffusers 推理未产出有效视频文件")
    return str(tmp_path)


def _run_comfyui(params: dict) -> str:
    """委托 ComfyUI 可选执行器（backend/comfy_workflow.py），按任务类型选择官方权重。"""
    from comfy_workflow import run_comfyui

    task_type = params["task_type"]
    scheduler = h3.REF2VA_SCHEDULER if task_type == h3.REF2VA else h3.SCHEDULER
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
    }
    return run_comfyui(task)
