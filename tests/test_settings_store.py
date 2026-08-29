"""settings_store.py 单元测试 — 配置持久化逻辑。

覆盖：
- _load / _save：读写往返 + 空文件 + 损坏 JSON
- get：仅读持久化值
- resolve：环境变量 > 持久化 > default 优先级
- update：可设置键过滤 + None 过滤 + 合并写入
- all_settings：含 locked 标记
- 异常态：无效键被忽略
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from settings_store import (
    SETTABLE_KEYS,
    _DEFAULTS,
    _ENV_KEYS,
    all_settings,
    get,
    resolve,
    update,
)


@pytest.fixture()
def isolated_store(monkeypatch, tmp_path):
    """隔离的 settings.json + 清理环境变量。"""
    store_path = tmp_path / "settings.json"
    # patch _STORE_PATH 在两个模块中的引用
    import settings_store as ss
    monkeypatch.setattr(ss, "_STORE_PATH", store_path, raising=True)

    # 清除所有 MMH3_ 环境变量
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return store_path


# ── _load / _save 往返 ─────────────────────────────────

def test_save_load_roundtrip(isolated_store):
    """update 写入后 get 应读到。"""
    update({"sampler": "euler"})
    assert get("sampler") == "euler"


def test_load_empty_file(isolated_store):
    """无文件时 get 返回 None。"""
    assert get("nonexistent_key") is None


def test_load_corrupted_json(isolated_store, isolated_store_path=None):
    """损坏的 JSON 文件应被忽略（返回空字典）。"""
    import settings_store as ss
    ss._STORE_PATH.write_text("<<<corrupted>>>", encoding="utf-8")
    assert get("sampler") is None  # 不抛异常，返回默认 None
    # update 应能修复文件
    update({"steps": 10})
    assert get("steps") == 10


# ── get ───────────────────────────────────────────────

def test_get_returns_none_for_missing(isolated_store):
    """不存在的键 → None。"""
    assert get("missing") is None


def test_get_returns_persisted_value(isolated_store):
    """get 应返回已持久化的值。"""
    update({"quantization": "bf16"})
    assert get("quantization") == "bf16"


# ── resolve（优先级链）────────────────────────────────

def test_resolve_env_overrides_store(isolated_store, monkeypatch):
    """环境变量 > 持久化。"""
    update({"inference_backend": "diffusers"})
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "comfy")
    assert resolve("inference_backend") == "comfy"


def test_resolve_store_over_default(isolated_store):
    """持久化 > default。"""
    update({"quantization": "int4"})
    assert resolve("quantization", "bf16") == "int4"


def test_resolve_default_when_unset(isolated_store):
    """未设置时返回 default。"""
    assert resolve("sampler", "euler") == "euler"


def test_resolve_env_ignored_for_non_env_key(isolated_store):
    """不在 _ENV_KEYS 中的键不受环境变量影响。"""
    update({"sampler": "euler"})
    # sampler 不在 _ENV_KEYS 中，即使有同名环境变量也不读
    assert resolve("sampler") == "euler"


# ── update（写入过滤）─────────────────────────────────

def test_update_filters_non_settable_keys(isolated_store):
    """不可设置的键应被忽略。"""
    update({"inference_backend": "comfy", "INVALID_KEY": "x"})
    assert get("INVALID_KEY") is None


def test_update_filters_none_values(isolated_store):
    """None 值应被忽略。"""
    update({"sampler": "euler", "steps": None})
    assert get("sampler") == "euler"
    assert get("steps") is None


def test_update_merges_existing(isolated_store):
    """update 应与已有配置合并，而非覆盖。"""
    update({"sampler": "euler"})
    update({"steps": 25})
    assert get("sampler") == "euler"
    assert get("steps") == 25


def test_update_returns_full_config(isolated_store):
    """update 应返回完整持久化配置。"""
    update({"sampler": "euler"})
    result = update({"steps": 25})
    assert result["sampler"] == "euler"
    assert result["steps"] == 25


# ── all_settings ──────────────────────────────────────

def test_all_settings_returns_all_settable_keys(isolated_store):
    """all_settings 应包含所有 SETTABLE_KEYS。"""
    result = all_settings()
    for key in SETTABLE_KEYS:
        assert key in result
        assert "value" in result[key]
        assert "locked" in result[key]


def test_all_settings_uses_defaults(isolated_store):
    """未设置时应用 _DEFAULTS。"""
    result = all_settings()
    assert result["sampler"]["value"] == _DEFAULTS["sampler"]
    assert result["steps"]["value"] == _DEFAULTS["steps"]


def test_all_settings_locked_flag(isolated_store, monkeypatch):
    """环境变量锁定时 locked=True。"""
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "comfy")
    result = all_settings()
    assert result["inference_backend"]["locked"] is True
    assert result["sampler"]["locked"] is False  # sampler 不在 _ENV_KEYS
