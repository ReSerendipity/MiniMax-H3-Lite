"""
MM·H3 工作台 — 运行时配置持久化
可在前端切换并持久化（data/settings.json），环境变量优先级最高。
"""
import json
import os
from pathlib import Path
from config import settings

_STORE_PATH = settings.BASE_DIR / "data" / "settings.json"

# 允许运行时写入的键（其余仅由 config/env 提供）
SETTABLE_KEYS = {
    "inference_backend",
    "inference_url",
    "quantization",
    "max_concurrency",
    "sampler",
    "scheduler",
    "steps",
    "denoise",
    "save_prefix",
    "ref_image_size",
    "load_video_node",
    "load_audio_node",
}

# 环境变量名 → 键
_ENV_KEYS = {
    "MMH3_INFERENCE_BACKEND": "inference_backend",
    "MMH3_INFERENCE_URL": "inference_url",
    "MMH3_QUANTIZATION": "quantization",
    "MMH3_MAX_CONCURRENCY": "max_concurrency",
}

# 键 → 默认值（未持久化也未设环境变量时）
_DEFAULTS = {
    "inference_backend": "diffusers",
    "inference_url": "http://127.0.0.1:8188",
    "quantization": "int8",
    "max_concurrency": 1,
    "sampler": "res_multistep",
    "scheduler": "simple",
    "steps": 20,
    "denoise": 1.0,
    "save_prefix": "mmh3",
    "ref_image_size": "match",
    "load_video_node": "LoadVideo",
    "load_audio_node": "LoadAudio",
}


def _load() -> dict:
    try:
        if _STORE_PATH.exists():
            return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save(data: dict):
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get(key: str, default=None):
    """仅读持久化值"""
    return _load().get(key, default)


def resolve(key: str, default=None):
    """环境变量 > 持久化 > default"""
    env_key = next((e for e, k in _ENV_KEYS.items() if k == key), None)
    if env_key and os.environ.get(env_key):
        return os.environ[env_key]
    store = _load()
    return store.get(key, default)


def update(patch: dict) -> dict:
    """合并写入可设置键，返回完整持久化配置"""
    patch = {k: v for k, v in patch.items() if k in SETTABLE_KEYS and v is not None}
    data = _load()
    data.update(patch)
    _save(data)
    return data


def all_settings() -> dict:
    """返回全部可读配置：值 + 是否被环境变量锁定"""
    data = _load()
    out = {}
    for key in SETTABLE_KEYS:
        env_key = next((e for e, k in _ENV_KEYS.items() if k == key), None)
        locked = bool(env_key and os.environ.get(env_key))
        out[key] = {"value": resolve(key, _DEFAULTS.get(key)), "locked": locked}
    return out
