"""
MM·H3 工作台 — 推理引擎注册表
- diffusers：进程内 ModularPipeline 推理（fallback）
- comfy：进程内复用 ComfyUI 内核源码加载官方单文件权重（B 方案，当前默认）
- vllm-omni：外部 vllm-omni 服务（Apache-2.0，OpenAI 兼容 /v1/videos；消费者级 GPU recipe，ADR-0003 推荐默认）
  注：DEFAULT_BACKEND 暂维持 "comfy"，待 vllm-omni 实际 provisioning + RTX 5070 Ti recipe 验证后翻转为 "vllm-omni"。
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
    "vllm-omni": {
        "display_name": "远程 · vllm-omni",
        "description": "外部 vllm-omni 服务（Apache-2.0），调用 OpenAI 兼容 /v1/videos；消费者级 GPU recipe（4090/5090 已验证）",
        "external": True,
        "implemented": True,
    },
}

DEFAULT_BACKEND = "comfy"  # ADR-0003：vllm-omni 已注册为推荐默认，待 provisioning + 5070Ti recipe 验证后翻转
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
