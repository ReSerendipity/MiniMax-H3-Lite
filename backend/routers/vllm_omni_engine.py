"""
MM·H3 工作台 — vllm-omni 推理引擎适配器（SCAFFOLD）

ADR-0003：将 vllm-omni 作为推荐默认引擎（Apache-2.0，消费者级 GPU recipe）。
vllm-omni 提供 OpenAI 兼容的 /v1/videos 接口；本适配器把 h3.spec 归一化的
params 映射为该请求，并把返回视频落盘为临时文件（与 comfy_engine.run 同约定：
返回已存在的视频文件路径字符串，由 inference.py 统一归档）。

⚠️ SCAFFOLD 标记：
- 仅当 MMH3_INFERENCE_BACKEND=vllm-omni（或设置 inference_backend=vllm-omni）时激活，
  不影响默认 comfy 路径。
- 请求字段名需对照所选 vllm-omni recipe（4090/5090）最终对齐；当前为合理默认映射。
- 运行期依赖：vllm-omni 服务已在 VLLM_OMNI_ENDPOINT 启动（默认 http://localhost:8000）。
"""
import os
import uuid
import logging
from pathlib import Path

from config import settings

_log = logging.getLogger(__name__)

VLLM_OMNI_ENDPOINT = os.environ.get("VLLM_OMNI_ENDPOINT", "http://localhost:8000").rstrip("/")


def run(params: dict) -> str:
    """调用 vllm-omni /v1/videos，返回落盘视频路径。"""
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError(
            "vllm-omni 适配器依赖 httpx，请先安装：pip install httpx"
        ) from e

    task_type = params.get("task_type")
    payload = {
        "prompt": params.get("prompt", ""),
        "width": params.get("width"),
        "height": params.get("height"),
        "duration": round((params.get("num_frames", 1) / max(params.get("fps", 24), 1)), 2),
        "fps": params.get("fps", 24),
        "task_type": task_type,
    }
    # 参考素材：vllm-omni 接收文件路径/URL；此处直接传本地路径（服务需可访问）。
    refs = params.get("refs") or []
    if refs:
        payload["reference_images"] = [r["path"] for r in refs if r.get("kind") == "image"]
        payload["reference_videos"] = [r["path"] for r in refs if r.get("kind") == "video"]
        payload["reference_audios"] = [r["path"] for r in refs if r.get("kind") == "audio"]
    if params.get("first_image"):
        payload["first_image"] = params["first_image"]
    if params.get("last_image"):
        payload["last_image"] = params["last_image"]

    tmp_path = settings.ASSETS_DIR / f"tmp_{uuid.uuid4().hex}.mp4"
    try:
        with httpx.Client(timeout=1800.0) as client:
            resp = client.post(f"{VLLM_OMNI_ENDPOINT}/v1/videos", json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"vllm-omni 返回非 200：{resp.status_code} {resp.text[:500]}"
            )
        # 返回可能是视频字节（video/mp4 / application/octet-stream）或 JSON 含 url。
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:
            data = resp.json()
            video_url = data.get("url") or data.get("video") or data.get("path")
            if not video_url:
                raise RuntimeError(f"vllm-omni 返回 JSON 但无 video url：{data}")
            with httpx.Client(timeout=1800.0) as c2:
                vresp = c2.get(video_url)
            if vresp.status_code != 200:
                raise RuntimeError(f"下载 vllm-omni 视频失败：{vresp.status_code}")
            tmp_path.write_bytes(vresp.content)
        else:
            tmp_path.write_bytes(resp.content)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"vllm-omni 推理失败：{type(e).__name__}: {e}") from e

    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError("vllm-omni 未产出有效视频文件")
    return str(tmp_path)
