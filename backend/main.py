"""
MM·H3 工作台 — FastAPI 主应用
PRD §5: FastAPI 后端 + SQLite + asyncio/线程池队列
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import init_db
from config import settings
from routers import projects, shots, generations, uploads, history

app = FastAPI(
    title="MM·H3 工作台 API",
    version="0.1.0",
    description="MiniMax H3 视频生成时间线工作台后端",
)

# CORS（本地开发：前端 8080 ↔ 后端 18080）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{settings.FRONTEND_PORT}", f"http://127.0.0.1:{settings.FRONTEND_PORT}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件：结果视频 + 上传素材
app.mount("/assets", StaticFiles(directory=str(settings.ASSETS_DIR)), name="assets")
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")

# 路由
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(shots.router, prefix="/api", tags=["shots"])
app.include_router(generations.router, prefix="/api", tags=["generations"])
app.include_router(uploads.router, prefix="/api", tags=["uploads"])
app.include_router(history.router, prefix="/api", tags=["history"])


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "engine": "MiniMax H3",
        "model": settings.MODEL_NAME,
        "quantization": settings.QUANTIZATION,
        "max_concurrency": settings.MAX_CONCURRENCY,
    }
