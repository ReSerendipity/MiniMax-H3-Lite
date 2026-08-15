"""
MM·H3 工作台 — 系统路由：引擎切换 + 运行时设置
GET    /api/engines                可用引擎列表（含激活态）
POST   /api/engine/switch          切换当前推理引擎（持久化，env 优先）
GET    /api/system/settings        读取可配置项（含是否被 env 锁定）
POST   /api/system/settings        更新并持久化可配置项
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine_registry import list_engines, switch_backend, active_backend, backend_locked_by_env
from settings_store import update as store_update, all_settings

router = APIRouter()


class SwitchRequest(BaseModel):
    backend: str


class SettingsPatch(BaseModel):
    inference_backend: str | None = None
    inference_url: str | None = None
    quantization: str | None = None
    max_concurrency: int | None = None
    sampler: str | None = None
    scheduler: str | None = None
    steps: int | None = None
    denoise: float | None = None
    save_prefix: str | None = None
    ref_image_size: str | None = None
    load_video_node: str | None = None
    load_audio_node: str | None = None


@router.get("/engines")
def get_engines():
    return {"engines": list_engines(), "active": active_backend(), "locked": backend_locked_by_env()}


@router.post("/engine/switch")
def switch_engine(body: SwitchRequest):
    try:
        return switch_backend(body.backend)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.get("/system/settings")
def get_settings():
    return all_settings()


@router.post("/system/settings")
def post_settings(body: SettingsPatch):
    patch = body.model_dump(exclude_none=True)
    return store_update(patch)
