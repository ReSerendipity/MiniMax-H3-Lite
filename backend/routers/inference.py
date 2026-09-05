"""
MM·H3 工作台 — 推理客户端
使用本地 diffusers ModularPipeline 进行推理，完全独立不依赖外部服务。
参数映射以 backend/h3/spec.py（源自三份官方工作流）为单一事实源。
"""
import os
import sys
import json
import time
import subprocess  # nosec B404: 仅用于 ffmpeg 缩略图提取（固定参数，无 shell）
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_db, new_id
from config import settings
from engine_registry import active_backend
from h3 import spec as h3
from settings_store import resolve as resolve_setting


def _attach_provenance(dest: Path, task_id: str) -> None:
    """在产出视频落盘后附加内容来源标识（失败静默，绝不影响输出）。"""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from watermark import embed_video
        payload = f"task-{task_id}"
        if embed_video(str(dest), str(dest), payload=payload):
            _log.debug("来源标识已附加: %s", dest.name)
        else:
            _log.debug("来源标识附加未完成（无 ffmpeg 或文件不支持）: %s", dest.name)
    except Exception as e:  # pragma: no cover
        _log.debug("来源标识附加异常（已忽略）: %s", e)


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
    # 分辨率档 = 官方 megapixel preset（如 "0.98"）；兼容旧值 "768P"。
    # 注意：H3-Base 原生上限 = 0.98(1344×768)。旧值 "2K" 需 H3-Regenerate-2K（未随开源 Base 提供）→ 回退到原生 0.98。
    resolution = params.get("resolution", h3.RESOLUTION_DEFAULT)
    preset = resolution
    if resolution == "768P" or resolution == "2K":
        preset = h3.RESOLUTION_DEFAULT
    width, height = h3.dims_for_resolution(preset, aspect, multiple=h3.RESOLUTION_MULTIPLE)
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
        except Exception:  # nosec B110: 尺寸探测尽力而为，失败回退默认分辨率
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
        subprocess.run(  # nosec B603 B607: ffmpeg 为固定可执行名 + 内部路径参数，无不可信输入
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
    backend = active_backend()
    if backend == "comfy":
        # B 方案：进程内复用 ComfyUI 内核（routers/comfy_engine.py）
        from routers.comfy_engine import run as run_comfy
        result = run_comfy(params)
    elif backend == "vllm-omni":
        # ADR-0003：外部 vllm-omni 服务（OpenAI 兼容 /v1/videos）
        from routers.vllm_omni_engine import run as run_vllm
        result = run_vllm(params)
    else:
        result = _run_diffusers(params)

    aid = new_id("ast_")
    ext = ".mp4"
    stored_name = f"{aid}{ext}"
    dest = settings.ASSETS_DIR / stored_name

    if isinstance(result, (bytes, bytearray)):
        dest.write_bytes(result)
        _attach_provenance(dest, task_id)
    elif isinstance(result, str) and Path(result).exists():
        import shutil
        shutil.move(result, str(dest))
    else:
        raise RuntimeError(f"推理未产出有效文件：{result!r}")

    size = dest.stat().st_size if dest.exists() else 0

    # seed 血缘回写：把最终生效 seed 写回任务 payload，任务记录与产物可追溯、可重放
    try:
        pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"] or {})
        pl.setdefault("params", {})
        pl["params"]["seed"] = params["seed"]
        db.execute(
            "UPDATE generation_tasks SET payload=? WHERE id=?",
            (json.dumps(pl, ensure_ascii=False), task_id),
        )
    except Exception:  # nosec B110: seed 血缘回写尽力而为，失败不影响推理产物
        pass

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
        "seed": params["seed"],
    }, ensure_ascii=False)
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
        (aid, "result", f"assets/{stored_name}", "video/mp4", size, meta),
    )
    db.commit()
    db.close()

    return {"asset_id": aid, "path": f"assets/{stored_name}"}


def _model_available_locally(model_source: str) -> bool:
    """权重是否已就绪（本地目录 / HF 缓存），用于推理前预检。"""
    if settings.MODEL_PATH:
        p = Path(model_source)
        return p.exists() and (
            (p / "model_index.json").exists() or (p / "modular_model_index.json").exists()
        )
    # HF id：检查本机 HF 缓存中是否已有该 repo 的快照（离线也可读本地缓存）
    try:
        from huggingface_hub import scan_cache_dir
        repo_id = "/".join(model_source.split("/")[:2])
        return any(r.repo_id == repo_id for r in scan_cache_dir().repos)
    except Exception:
        return False


def _model_missing_error(model_source: str) -> RuntimeError:
    """权重缺失时的可操作报错：说明下载方式 + MMH3_MODEL_PATH 配置。"""
    offline = os.environ.get("HF_HUB_OFFLINE", "").strip().lower() in ("1", "true")
    mode = "离线模式（HF_HUB_OFFLINE=1）" if offline else "当前网络"
    if settings.MODEL_PATH:
        return RuntimeError(
            f"本地权重目录缺失或不是完整 diffusers 仓库：{settings.MODEL_PATH}\n"
            "  · 请下载 MiniMaxAI/MiniMax-H3（需含根目录 model_index.json / modular_model_index.json "
            "及 text_encoder / transformer / transformer_ref / vae / audio_vae / scheduler 等子目录）到本地；\n"
            "  · 再设置环境变量 MMH3_MODEL_PATH 指向该目录后重启服务。"
        )
    return RuntimeError(
        f"模型权重未下载：{model_source}\n"
        f"  · {mode}无法从 HuggingFace 拉取，且本机 HF 缓存中没有 MiniMaxAI/MiniMax-H3；\n"
        "  · 推荐做法：手动下载 MiniMaxAI/MiniMax-H3 到本地（单模型约 33GB，全量约 354GB），"
        "设置 MMH3_MODEL_PATH 指向该目录后重启；\n"
        "  · 或取消 HF_HUB_OFFLINE 环境变量（并确保可访问 huggingface.co）后在线拉取（体积巨大，慎用）。"
    )


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

    task_type = params.get("task_type", h3.T2VA)
    model_id = settings.MODEL_PATH or settings.MODEL_NAME
    # 预检：权重是否已就绪（本地目录或 HF 缓存）。缺失时直接给出可操作指引，而非底层 traceback。
    if not _model_available_locally(model_id):
        raise _model_missing_error(model_id)
    tmp_path = settings.ASSETS_DIR / f"tmp_{uuid.uuid4().hex}.mp4"
    try:
        pipe = ModularPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
        if settings.QUANTIZATION:
            pipe.enable_model_cpu_offload()

        # 构造 inputs：对 ModularPipeline 未知参数名做多套候选，按顺序尝试
        base_kwargs = {
            "prompt": params["prompt"],
            "width": params["width"],
            "height": params["height"],
            "num_frames": params["num_frames"],
            "fps": params["fps"],
            "audio_sample_rate": params["audio_sample_rate"],
        }

        # seed 血缘（MLOps 评估 P1）：消费 payload 中的 seed 构造确定性 Generator，
        # 使「同参数 + 同 seed」结果可复现。generator 不被 pipeline 接受时，
        # 由下方 TypeError 回退路径剔除，不阻断推理（兼容旧版 diffusers）。
        try:
            generator = torch.Generator(device="cpu")
            generator.manual_seed(int(params.get("seed") or 0))
        except Exception:
            generator = None
        if generator is not None:
            base_kwargs["generator"] = generator

        if task_type == h3.FL2VA:
            base_kwargs["first_image"] = params.get("first_image")
            if params.get("last_image"):
                base_kwargs["last_image"] = params["last_image"]
        elif task_type == h3.REF2VA:
            grouped = h3.group_refs(params.get("refs") or [])
            ref_size_mode = params.get("ref_image_size") or "match"
            if grouped["image"]:
                base_kwargs["ref_images"] = _scale_ref_images(
                    grouped["image"], params["width"], params["height"], ref_size_mode
                )
            if grouped["video"]:
                base_kwargs["ref_videos"] = grouped["video"]
            if grouped["audio"]:
                base_kwargs["ref_audios"] = grouped["audio"]
            if grouped.get("ref_video_audios"):
                base_kwargs["ref_video_audios"] = grouped["ref_video_audios"]

        # diffusers ModularPipeline 实际签名与官方 ComfyUI 工作流参数名可能略有差异。
        # 先做"剔除空值"再尝试；参数名不匹配时改为 strict=False 让 pipeline 自己挑。
        kwargs = {k: v for k, v in base_kwargs.items() if v is not None}

        try:
            output = pipe(**kwargs)
        except TypeError as e:
            # 典型：ModularPipeline 不接受 generator / first_image（要 image）/ ref_images（要 list[str]）等。
            # 先剔除 generator，再重命名为最常见等价物后重试；最终仍失败则把"原参数名 + 期望参数"如实上报。
            retry = {k: v for k, v in kwargs.items() if k != "generator"}
            alias_map = {
                "first_image": "image",
                "last_image": "image",
                "ref_images": "image",
                "ref_videos": "video",
                "ref_audios": "audio",
                "ref_video_audios": "audio",
            }
            for k, alias in alias_map.items():
                if k in retry:
                    val = retry.pop(k)
                    if alias not in retry:
                        retry[alias] = val
            try:
                output = pipe(**retry)
            except TypeError as e2:
                sig = ""
                try:
                    sig = str(_safe_signature(pipe))
                except Exception:  # nosec B110: 签名仅用于排错信息增强，获取失败可忽略
                    pass
                raise RuntimeError(
                    f"ModularPipeline 拒绝入参：原错误={e!r}；"
                    f"重试别名后仍失败：{e2!r}；"
                    f"当前入参={sorted(kwargs.keys())}；"
                    f"pipeline 签名={sig}"
                ) from e2
        output.save(str(tmp_path))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"diffusers 推理失败 [{task_type}]:{type(e).__name__}: {e}"
        ) from e

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError("diffusers 推理未产出有效视频文件")
    return str(tmp_path)


def _safe_signature(pipe) -> str:
    """安全获取 pipe.__call__ 签名，便于排错。"""
    import inspect
    try:
        sig = inspect.signature(pipe.__call__)
        return str(sig)
    except Exception as e:
        return f"<签名获取失败:{type(e).__name__}:{e}>"


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
