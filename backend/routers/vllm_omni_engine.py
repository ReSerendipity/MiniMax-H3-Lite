"""
MM·H3 工作台 — vllm-omni 推理引擎适配器

ADR-0003：将 vllm-omni 作为推荐默认引擎（Apache-2.0，消费者级 GPU recipe）。
vllm-omni 提供 OpenAI 兼容的 /v1/videos 接口；本适配器把 h3.spec 归一化的
params 映射为该请求，并把返回视频落盘为临时文件（与 comfy_engine.run 同约定：
返回已存在的视频文件路径字符串，由 inference.py 统一归档）。

⚠️ SCAFFOLD 标记：
- 仅当 MMH3_INFERENCE_BACKEND=vllm-omni（或设置 inference_backend=vllm-omni）时激活，
  不影响默认 comfy 路径。
- 请求字段名需对照所选 vllm-omni recipe（4090/5090）最终对齐；当前为合理默认映射。
- 运行期依赖：vllm-omni 服务已在 settings.VLLM_OMNI_ENDPOINT 启动（默认 http://localhost:8000）。

容错（后端服务设计评估 P0-2，2026-10-11）：
- 端点/超时/重试次数全部经 Settings 外部化（MMH3_VLLM_OMNI_*），删除模块级 env 直读；
- 传输层失败（连接/超时/读错误）做有限重试 + 指数退避 + 抖动；
  业务层失败（非 200）不重试——生成类接口重试可能触发二次昂贵推理；
- run() 推理前对外部服务做存活探测（check_health），不可达即快速失败并给可操作指引。
"""
import logging
import random
import time
import uuid
from typing import Any

from config import settings

_log = logging.getLogger(__name__)

# 健康探测短超时（秒）：仅用于存活判定，与推理请求超时无关
_HEALTH_TIMEOUT = 5.0


def backoff_delay(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:
    """指数退避 + 抖动（纯计算，便于单测）：base * 2^attempt，±20% 抖动，封顶 cap（抖动后封顶）。"""
    delay = base * (2 ** max(attempt, 0))
    delay *= 1 + (random.random() - 0.5) * 0.4
    return min(max(delay, 0.05), cap)


def _backoff_sleep(attempt: int) -> None:
    """按指数退避+抖动延迟休眠（attempt 从 0 起）。"""
    time.sleep(backoff_delay(attempt))


def check_health() -> dict:
    """对外部 vllm-omni 服务做存活探测（短超时，不抛异常）。

    可达性判定：收到任意 HTTP 响应（<500，含 404/405 等路由不存在）即视为可达——
    「服务器在响应」与「该路由存在」是两回事，探测只关心前者。
    仅传输层错误（连接失败/超时/依赖缺失）判为不可达。

    Returns:
        {"reachable": bool, "detail": str}。
    """
    try:
        import httpx
    except ImportError:
        return {"reachable": False, "detail": "httpx 未安装，请先安装：pip install httpx"}
    endpoint = settings.VLLM_OMNI_ENDPOINT.rstrip("/")
    last = "未发起探测"
    for path in ("/v1/models", "/health"):
        try:
            with httpx.Client(timeout=_HEALTH_TIMEOUT) as client:
                resp = client.get(f"{endpoint}{path}")
            # 有 HTTP 响应即服务可达（2xx/3xx/4xx 均算，探测不关心业务语义）
            if resp is not None and resp.status_code < 500:
                return {"reachable": True, "detail": f"GET {endpoint}{path} -> {resp.status_code}"}
            last = f"GET {endpoint}{path} -> HTTP {getattr(resp, 'status_code', '无响应')}"
        except Exception as e:  # noqa: BLE001 - 探测失败仅记录，不抛异常
            last = f"{type(e).__name__}: {e}"
    return {"reachable": False, "detail": last}


def _post_with_retry(httpx, payload: dict, endpoint: str) -> Any:
    """POST /v1/videos：传输层失败有限重试（指数退避+抖动），业务层失败不重试。

    返回类型 Any：httpx 为运行时惰性导入（CI typecheck 环境无 httpx），
    响应对象为鸭子类型（status_code/headers/content/json），不引入静态依赖。
    """
    retries = settings.VLLM_OMNI_RETRIES
    last_transport: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=settings.VLLM_OMNI_TIMEOUT) as client:
                resp = client.post(f"{endpoint}/v1/videos", json=payload)
            return resp  # 传输层成功 → 状态码判定交给调用方（不重试非 200）
        except Exception as e:  # noqa: BLE001 - 传输层异常（连接/超时/读错误）进入重试
            last_transport = e
            if attempt < retries:
                _log.warning(
                    "vllm-omni POST 传输失败，重试 %s/%s：%s",
                    attempt + 1, retries, e,
                )
                _backoff_sleep(attempt)
    raise RuntimeError(
        f"vllm-omni 请求失败（传输层重试 {retries} 次后）："
        f"{type(last_transport).__name__}: {last_transport}"
    )


def _get_with_retry(httpx, url: str) -> Any:
    """GET 下载产物：传输层失败有限重试（幂等操作，重试安全）。返回类型见 _post_with_retry。"""
    retries = settings.VLLM_OMNI_RETRIES
    last_transport: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=settings.VLLM_OMNI_TIMEOUT) as client:
                resp = client.get(url)
            return resp
        except Exception as e:  # noqa: BLE001
            last_transport = e
            if attempt < retries:
                _log.warning(
                    "vllm-omni 产物下载传输失败，重试 %s/%s：%s",
                    attempt + 1, retries, e,
                )
                _backoff_sleep(attempt)
    raise RuntimeError(
        f"vllm-omni 产物下载失败（传输层重试 {retries} 次后）："
        f"{type(last_transport).__name__}: {last_transport}"
    )


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

    endpoint = settings.VLLM_OMNI_ENDPOINT.rstrip("/")

    # 存活预检（评估 P0-2）：外部服务不可达时快速失败，给出可操作指引而非漫长超时。
    # 注意：httpx 导入检查必须先于探测——依赖缺失时保留原安装指引错误信息。
    health = check_health()
    if not health["reachable"]:
        raise RuntimeError(
            f"vllm-omni 服务不可达（{health['detail']}）；"
            f"请确认服务已在 {endpoint} 启动（VLLM_OMNI_ENDPOINT 可配置）"
        )

    tmp_path = settings.ASSETS_DIR / f"tmp_{uuid.uuid4().hex}.mp4"
    try:
        resp = _post_with_retry(httpx, payload, endpoint)
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
            vresp = _get_with_retry(httpx, video_url)
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
