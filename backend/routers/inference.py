"""
MM·H3 工作台 — 推理客户端
使用本地 diffusers ModularPipeline 进行推理，完全独立不依赖外部服务。
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
from settings_store import resolve as resolve_setting


def _build_params(task_row: dict) -> dict:
    """
    将任务行规范化为结构化参数。
    帧长/分辨率/任务类型/参考素材分组均来自 h3.spec（官方工作流语义）。
    """
    payload = json.loads(task_row["payload"]) if isinstance(task_row["payload"], str) else task_row["payload"]
    prompt = payload.get("prompt", "")
    params = payload.get("params", {})

    mode = task_row["mode"]
    duration = params.get("duration", 8)
    aspect = params.get("aspect", "16:9")
    resolution = params.get("resolution", "768P")
    short_side = 768 if resolution == "768P" else 1440  # 2K 未开源，暂不支持
    width, height = h3.resolution_for(aspect, short_side=short_side, multiple=2)
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
                    "paired_video": None,
                })
        pair_rows = db.execute(
            "SELECT asset_id, pair_asset_id FROM shot_refs WHERE shot_id=?",
            (task_row["shot_id"],),
        ).fetchall()
        pair_map = {r["asset_id"]: r["pair_asset_id"] for r in pair_rows if r["pair_asset_id"]}
        for ref in refs:
            if ref["id"] in pair_map:
                ref["paired_video"] = pair_map[ref["id"]]
        db.close()

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

    if task_type == h3.FL2VA and params.get("size_mode") == "follow_first" and first_image:
        try:
            from PIL import Image
            with Image.open(first_image) as im:
                iw, ih = im.size
            sw = h3.SHORT_SIDE
            cap = h3.MAX_DIM
            m = 2
            if iw >= ih:
                nw, nh = sw * iw / ih, sw
            else:
                nh, nw = sw * ih / iw, sw
            nw = min(((int(nw) + m - 1) // m) * m, cap)
            nh = min(((int(nh) + m - 1) // m) * m, cap)
            if nw > 0 and nh > 0:
                width, height = nw, nh
        except Exception:
            pass

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


def _extract_thumbnail(video_path: str, output_path: str, time_offset: float = 0.5):
    """使用 ffmpeg 提取首帧作为缩略图"""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(time_offset), "-i", video_path,
             "-frames:v", "1", "-f", "image2", output_path],
            capture_output=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass


def run_inference(task_id: str) -> dict:
    """
    执行推理任务，返回 {"asset_id": "...", "path": "...", "thumbnail": "..."}
    使用本地 diffusers ModularPipeline 进行推理。
    """
    db = get_db()
    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        db.close()
        raise ValueError(f"任务不存在：{task_id}")

    params = _build_params(dict(row))
    result = _run_diffusers(params)

    aid = new_id("ast_")
    ext = ".mp4"
    stored_name = f"{aid}{ext}"
    dest = settings.ASSETS_DIR / stored_name

    if isinstance(result, (bytes, bytearray)):
        dest.write_bytes(result)
    elif isinstance(result, str) and Path(result).exists():
        import shutil
        shutil.move(result, str(dest))
    else:
        raise RuntimeError(f"推理未产出有效文件：{result!r}")

    size = dest.stat().st_size if dest.exists() else 0

    thumb_name = f"{aid}_thumb.jpg"
    thumb_path = settings.ASSETS_DIR / thumb_name
    if dest.exists() and size > 0:
        _extract_thumbnail(str(dest), str(thumb_path))

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
    输入映射按 h3.spec:t2va 纯文本；fl2va 传 image(+last_image)；ref2va 传 ref_images/ref_videos/ref_audios。
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
            ref_size_mode = params.get("ref_image_size") or "match"
            if grouped["image"]:
                inputs["ref_images"] = _scale_ref_images(grouped["image"], params["width"], params["height"], ref_size_mode)
            if grouped["video"]:
                inputs["ref_videos"] = grouped["video"]
            if grouped["audio"]:
                inputs["ref_audios"] = grouped["audio"]
            if grouped.get("ref_video_audios"):
                import inspect as _inspect
                try:
                    _sig = _inspect.signature(pipe.__call__)
                    _supports_pair = "ref_video_audios" in _sig.parameters
                except Exception:
                    _supports_pair = False
                if _supports_pair:
                    inputs["ref_video_audios"] = grouped["ref_video_audios"]
                else:
                    merged = list(inputs.get("ref_audios") or [])
                    merged += [p["audio"] for p in grouped["ref_video_audios"]]
                    inputs["ref_audios"] = merged

        output = pipe(**inputs)
        output.save(str(tmp_path))
    except Exception as e:
        raise RuntimeError(f"diffusers 推理失败:{type(e).__name__}: {e}") from e

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError("diffusers 推理未产出有效视频文件")
    return str(tmp_path)


def _scale_ref_images(paths, width, height, mode):
    """按 ref_image_size 语义缩放参考图像（PIL）。
    match：缩放到生成分辨率（更快）；
    max：短边保持 ≤2048（更强身份保真）。
    """
    try:
        from PIL import Image
    except ImportError:
        return paths
    import tempfile
    out = []
    for p in paths:
        try:
            im = Image.open(p)
            if mode == "match":
                im = im.resize((width, height), Image.LANCZOS)
            else:
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
            out.append(p)
    return out
