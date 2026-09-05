"""运维稳定性评估落地回归测试（对应 MiniMax-H3-lite_运维稳定性评估提示词 v1.0.0）。

覆盖：日志落盘 / 健康探针就绪信号 / 队列深度 / 默认推理路径超时强制（TASK_TIMEOUT 死配置清除）。
依赖 conftest 的 fastapi 环境与临时 DB；在本机/CI 需 fastapi + torch 可用。
"""
import logging
import time

import pytest

from backend import config as backend_config
from backend.logging_config import configure_logging
from backend.runtime_state import is_model_loaded, mark_model_loaded
from backend.routers import queue_manager


def test_logging_persist():
    """T1：configure_logging 把日志落盘到 <BASE_DIR>/logs/backend.log。"""
    configure_logging()
    logger = logging.getLogger("ops_test_persist")
    marker = "OPS_MARKER_PERSIST_%d" % int(time.time())
    logger.info(marker)
    # 幂等 handler 已在进程启动时绑定到真实 BASE_DIR/logs（同一 handler，不重复添加）
    log_file = backend_config.settings.BASE_DIR / "logs" / "backend.log"
    assert log_file.exists(), "日志文件未生成"
    assert marker in log_file.read_text(encoding="utf-8"), "日志内容未落盘"


def test_runtime_state_toggle():
    """T2：mark_model_loaded / is_model_loaded 基本可用性。"""
    mark_model_loaded()
    assert is_model_loaded() is True


def test_queue_depth_type():
    """T2：queue_depth 返回 int。"""
    assert isinstance(queue_manager.queue_depth(), int)


def test_health_contains_readiness_fields(client):
    """T2：/api/health 含 model_loaded 与 queue_depth 真实就绪信号。"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "model_loaded" in body
    assert "queue_depth" in body
    assert isinstance(body["queue_depth"], int)


def test_run_with_timeout_raises_on_hang(monkeypatch):
    """T6：默认推理路径超时被标记失败（不再永久 processing）。"""
    monkeypatch.setattr(
        queue_manager, "run_inference", lambda tid: time.sleep(5) or {"asset_id": "x", "path": "y"}
    )
    monkeypatch.setattr(queue_manager.settings, "INFERENCE_TIMEOUT", 0.2)
    with pytest.raises(queue_manager._InferenceTimeout):
        queue_manager._run_with_timeout("fake-task")


def test_run_with_timeout_success_returns(monkeypatch):
    """T6：未超时则正常返回推理结果。"""
    monkeypatch.setattr(
        queue_manager, "run_inference", lambda tid: {"asset_id": "ast_1", "path": "assets/x.mp4"}
    )
    monkeypatch.setattr(queue_manager.settings, "INFERENCE_TIMEOUT", 5)
    assert queue_manager._run_with_timeout("fake-task")["asset_id"] == "ast_1"


def test_task_timeout_dead_config_removed():
    """T6：config 中不再存在 TASK_TIMEOUT 死配置（仅 INFERENCE_TIMEOUT 保留）。"""
    assert not hasattr(backend_config.Settings, "TASK_TIMEOUT")
    assert hasattr(backend_config.settings, "INFERENCE_TIMEOUT")
