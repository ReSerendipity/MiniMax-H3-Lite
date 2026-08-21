"""
MM·H3 工作台 — 推理引擎注册表
- diffusers：进程内 ModularPipeline 推理
- comfy：进程内复用 ComfyUI 内核源码加载官方单文件权重（B 方案，默认）
"""
import os
from settings_store import resolve, update

ENGINES = {
    "diffusers": {
        "display_name": "本地 · diffusers",
        "description": "进程内 ModularPipeline 推理（需 diffusers 格式权重目录）",
        "external": False,
        "implemented": True,
    },
    "comfy": {
        "display_name": "本地 · Comfy 内核",
        "description": "进程内复用 ComfyUI 内核加载官方单文件权重 (B 方案)",
        "external": False,
        "implemented": True,
    },
}

DEFAULT_BACKEND = "comfy"
ENV_BACKEND = "MMH3_INFERENCE_BACKEND"


def active_backend() -> str:
    """当前激活引擎：环境变量 > 运行时持久化 > 默认 comfy"""
    env_val = os.environ.get(ENV_BACKEND)
    if env_val:
        return env_val if env_val in ENGINES else DEFAULT_BACKEND
    stored = resolve("inference_backend", DEFAULT_BACKEND)
    return stored if stored in ENGINES else DEFAULT_BACKEND


def backend_locked_by_env() -> bool:
    return bool(os.environ.get(ENV_BACKEND))


def list_engines() -> list[dict]:
    active = active_backend()
    locked = backend_locked_by_env()
    return [
        {
            "name": name,
            "display_name": meta["display_name"],
            "description": meta["description"],
            "external": meta["external"],
            "implemented": meta["implemented"],
            "active": name == active,
            "locked": locked,
        }
        for name, meta in ENGINES.items()
    ]


def switch_backend(name: str) -> dict:
    if name not in ENGINES:
        raise ValueError(f"未知引擎:{name}")
    if not ENGINES[name]["implemented"]:
        raise ValueError(f"引擎{name}尚未实现，暂不可用")
    if backend_locked_by_env():
        raise RuntimeError("推理引擎已被环境变量 MMH3_INFERENCE_BACKEND 锁定，无法在前端切换")
    update({"inference_backend": name})
    return {"name": name, "active": True, "locked": False, **ENGINES[name]}
