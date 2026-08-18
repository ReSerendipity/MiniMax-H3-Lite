"""
MM·H3 工作台 — FastAPI 主应用
PRD §5: FastAPI 后端 + SQLite + asyncio/线程池队列
"""
import logging
import sys
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

logger = logging.getLogger(__name__)

app = FastAPI(
    title="MM·H3 工作台 API",
    version="0.1.0",
    description="MiniMax H3 视频生成时间线工作台后端",
)

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
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def page_t2v(request: Request):
    return templates.TemplateResponse(request, "t2v.html")


@app.get("/i2v", response_class=HTMLResponse, include_in_schema=False)
def page_i2v(request: Request):
    return templates.TemplateResponse(request, "i2v.html")


@app.get("/r2v", response_class=HTMLResponse, include_in_schema=False)
def page_r2v(request: Request):
    return templates.TemplateResponse(request, "r2v.html")


@app.on_event("startup")
def startup():
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
    }