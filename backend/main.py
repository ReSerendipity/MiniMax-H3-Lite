"""
MM·H3 工作台 — FastAPI 主应用
PRD §5: FastAPI 后端 + SQLite + asyncio/线程池队列
"""
import logging
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import init_db
from config import settings
from engine_registry import active_backend, list_engines
from routers import projects, shots, generations, uploads, history, system
from routers import comfy_engine, vllm_omni_engine
from logging_config import configure_logging
from runtime_state import is_model_loaded, orphan_inference_count
from routers.queue_manager import queue_depth

configure_logging()  # 日志落盘到 logs/backend.log（滚动），崩溃后可回放

# 版本单一事实来源：仓库根 package.json（发版时人工随 tag 同步，见 docs/adr/0004 修订注记）
try:  # 扁平导入（backend 目录已加入 sys.path）
    from version import __version__ as APP_VERSION
except ImportError:  # pragma: no cover - 包形态兜底
    from backend.version import __version__ as APP_VERSION  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

app = FastAPI(
    title="MM·H3 工作台 API",
    version=APP_VERSION,
    description="MiniMax H3 视频生成时间线工作台后端",
)


@app.middleware("http")
async def request_trace_middleware(request: Request, call_next):
    """请求级追踪（后端服务设计评估 P1-6，2026-10-11）。

    生成 request_id 注入 request.state（业务 handler 可经 request.state.request_id 读取），
    响应头回传 X-Request-ID；记录请求起止与耗时到日志（消息内嵌 request_id，与
    既有 task_id 前缀风格一致，JSON 文件日志可直接检索）。不落请求体，避免敏感素材入日志。
    """
    request_id = uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_id=%s %s %s 未捕获异常", request_id, request.method, request.url.path
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request_id=%s %s %s -> %s %.0fms",
        request_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response

# Jinja2 模板（服务端渲染，单端口直出页面 + 静态；参考家族项目模板拆分）
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# 静态文件：结果视频 + 上传素材 + 前端资源（css/js/img）
app.mount("/assets", StaticFiles(directory=str(settings.ASSETS_DIR)), name="assets")
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")

# 路由
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(shots.router, prefix="/api", tags=["shots"])
app.include_router(generations.router, prefix="/api", tags=["generations"])
app.include_router(uploads.router, prefix="/api", tags=["uploads"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(system.router, prefix="/api", tags=["system"])


# ---- 页面路由（Jinja2 模板，单端口直出） ----
# 页面上下文统一注入 app_version（状态栏可见版本位，发版阶段 1 断言用；
# 单一事实源与 app.version 同源，禁止模板内硬编码）
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def page_t2v(request: Request):
    return templates.TemplateResponse(request, "t2v.html", {"app_version": APP_VERSION})


@app.get("/i2v", response_class=HTMLResponse, include_in_schema=False)
def page_i2v(request: Request):
    return templates.TemplateResponse(request, "i2v.html", {"app_version": APP_VERSION})


@app.get("/r2v", response_class=HTMLResponse, include_in_schema=False)
def page_r2v(request: Request):
    return templates.TemplateResponse(request, "r2v.html", {"app_version": APP_VERSION})


@app.on_event("startup")
def startup():
    # R10 代码完整性自检：enforce（默认 true）失败即拒绝启动（fail-closed）。
    # 必须在一切初始化之前执行——被篡改/清单缺失的代码不得运行。
    # （依赖 cryptography，Docker/venv 均经 requirements-lock 显式钉装）
    from security.integrity_selfcheck import run_startup_selfcheck

    run_startup_selfcheck(enforce=settings.INTEGRITY_ENFORCE)
    init_db()
    # 断点续跑（checkpoint #7）：扫描未完成任务并恢复续跑
    # 失败不阻塞启动（仅 warning）
    try:
        from routers.queue_manager import resume_unfinished_tasks
        restored = resume_unfinished_tasks()
        if restored:
            logger.info("[Checkpoint] 启动时恢复 %d 个未完成任务: %s", len(restored), restored)
    except Exception as e:  # pragma: no cover
        logger.warning("[Checkpoint] 启动恢复扫描失败（不影响启动）: %s", e)

    # 产物配额清理（AI/ML 评估 P2）：保留最近 N 个 result 资产，尽力而为
    try:
        from cleanup import enforce_result_quota
        removed = enforce_result_quota(settings.MAX_RESULT_ASSETS, settings.ASSETS_DIR)
        if removed:
            logger.info("[Cleanup] 启动清理 %d 个超出配额的结果资产", removed)
    except Exception as e:  # pragma: no cover
        logger.warning("[Cleanup] 启动配额清理失败（不影响启动）: %s", e)


@app.get("/api/health")
def health():
    active = active_backend()
    meta = next((e for e in list_engines() if e["name"] == active), {})
    return {
        "status": "ok",
        "engine": "MiniMax H3",
        "model": settings.MODEL_NAME,
        "backend": active,
        "backend_requires_external": bool(meta.get("external")),
        "quantization": settings.QUANTIZATION,
        "max_concurrency": settings.MAX_CONCURRENCY,
        # 运维稳定性评估补强：原仅静态配置回显 → 增加真实就绪信号
        "model_loaded": is_model_loaded(),
        "queue_depth": queue_depth(),
        # 后端服务设计评估 P1-3：超时孤儿推理线程计数（>0 时新任务将 fail-fast，需重启回收）
        "orphan_inference_count": orphan_inference_count(),
        # 后端服务设计评估 P2-8：对激活引擎做短超时主动探测，探测失败不影响应用自身健康
        "dependency": _dependency_status(active, meta),
    }


def _dependency_status(active: str, meta: dict) -> dict:
    """引擎依赖存活探测：vllm-omni（外部）/ comfy（进程内或 HTTP）/ diffusers（进程内）。"""
    dep = {"type": active, "requires_external": bool(meta.get("external"))}
    if active == "vllm-omni":
        h = vllm_omni_engine.check_health()
    elif active == "comfy":
        h = comfy_engine.check_health()
    else:
        h = {"reachable": True, "detail": "进程内引擎（无外部依赖）"}
    dep["reachable"] = h["reachable"]
    dep["detail"] = h["detail"]
    return dep
