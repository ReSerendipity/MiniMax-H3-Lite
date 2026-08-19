"""engine_registry.py 单元测试 — 引擎注册与切换逻辑。

覆盖：
- active_backend：环境变量 > 持久化 > 默认
- list_engines：完整性 + active/locked 标记
- switch_backend：正常切换 + 未知引擎 + 未实现引擎 + 环境锁定
- backend_locked_by_env：锁定状态
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import engine_registry as reg
from engine_registry import ENGINES, DEFAULT_BACKEND


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """每个测试清除环境变量，避免互相干扰。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    # 清空持久化
    import settings_store as ss
    monkeypatch.setattr(ss, "_load", lambda: {}, raising=True)
    monkeypatch.setattr(ss, "_save", lambda d: None, raising=True)


# ── active_backend ────────────────────────────────────

def test_active_backend_default(monkeypatch):
    """无环境变量 + 无持久化 → 默认 comfy。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    assert reg.active_backend() == DEFAULT_BACKEND


def test_active_backend_from_env(monkeypatch):
    """环境变量优先。"""
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "diffusers")
    assert reg.active_backend() == "diffusers"


def test_active_backend_env_invalid_falls_back(monkeypatch):
    """无效环境变量 → 回退默认。"""
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "nonexistent")
    assert reg.active_backend() == DEFAULT_BACKEND


def test_active_backend_from_store(monkeypatch):
    """持久化值（resolve 返回非默认）。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    # resolve 内部读 _load()，mock _load 返回持久化值
    monkeypatch.setattr("settings_store._load", lambda: {"inference_backend": "diffusers"})
    assert reg.active_backend() == "diffusers"


def test_active_backend_store_invalid_falls_back(monkeypatch):
    """持久化的无效值 → 回退默认。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    monkeypatch.setattr("settings_store.resolve", lambda key, default=None: "nonexistent")
    assert reg.active_backend() == DEFAULT_BACKEND


# ── list_engines ──────────────────────────────────────

def test_list_engines_completeness():
    """list_engines 应包含 ENGINES 中的所有引擎。"""
    engines = reg.list_engines()
    assert len(engines) == len(ENGINES)
    names = {e["name"] for e in engines}
    assert names == set(ENGINES.keys())


def test_list_engines_has_metadata():
    """每个引擎应有完整元数据。"""
    for e in reg.list_engines():
        assert "display_name" in e
        assert "description" in e
        assert "external" in e
        assert "implemented" in e
        assert "active" in e
        assert "locked" in e


def test_list_engines_one_active():
    """只有一个引擎被标记为 active。"""
    engines = reg.list_engines()
    active = [e for e in engines if e["active"]]
    assert len(active) == 1


def test_list_engines_locked_flag(monkeypatch):
    """环境变量设置时 locked=True。"""
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "diffusers")
    engines = reg.list_engines()
    assert all(e["locked"] for e in engines)


def test_list_engines_not_locked_without_env(monkeypatch):
    """无环境变量时 locked=False。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    engines = reg.list_engines()
    assert all(not e["locked"] for e in engines)


# ── switch_backend ────────────────────────────────────

def test_switch_backend_success(monkeypatch):
    """正常切换。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    result = reg.switch_backend("diffusers")
    assert result["name"] == "diffusers"
    assert result["active"] is True
    assert result["locked"] is False


def test_switch_backend_unknown_raises():
    """未知引擎 → ValueError。"""
    with pytest.raises(ValueError, match="未知引擎"):
        reg.switch_backend("nonexistent")


def test_switch_backend_env_locked_raises(monkeypatch):
    """环境变量锁定 → RuntimeError。"""
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "comfy")
    with pytest.raises(RuntimeError, match="环境变量"):
        reg.switch_backend("diffusers")


def test_switch_backend_persists(monkeypatch):
    """切换应调用 update 持久化。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    called = []
    monkeypatch.setattr("engine_registry.update", lambda d: called.append(d))
    reg.switch_backend("diffusers")
    assert len(called) == 1
    assert called[0]["inference_backend"] == "diffusers"


# ── backend_locked_by_env ─────────────────────────────

def test_backend_locked_true(monkeypatch):
    """环境变量设置 → True。"""
    monkeypatch.setenv("MMH3_INFERENCE_BACKEND", "comfy")
    assert reg.backend_locked_by_env() is True


def test_backend_locked_false(monkeypatch):
    """无环境变量 → False。"""
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    assert reg.backend_locked_by_env() is False
