"""运维稳定性评估落地回归测试（对应 MiniMax-H3-Lite_运维稳定性评估提示词 v1.0.0）。

覆盖：日志落盘 / 健康探针就绪信号 / 队列深度 / 默认推理路径超时强制（TASK_TIMEOUT 死配置清除）。
依赖 conftest 的 fastapi 环境与临时 DB；在本机/CI 需 fastapi + torch 可用。
"""
import logging
import time
from pathlib import Path

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


def test_orphan_marked_on_timeout(monkeypatch):
    """P1-3：推理超时 → 孤儿线程计入运行时计数（供 health 暴露与槽位守卫）。

    注意双形态模块（GOTCHAS 同 config）：queue_manager 经 sys.path 导入顶层
    `runtime_state`，测试必须读同一实例，否则读到 backend.runtime_state 的独立计数。
    """
    import runtime_state as top_runtime_state
    top_runtime_state.reset_orphan_inference()
    monkeypatch.setattr(
        queue_manager, "run_inference", lambda tid: time.sleep(5) or {"asset_id": "x", "path": "y"}
    )
    monkeypatch.setattr(queue_manager.settings, "INFERENCE_TIMEOUT", 0.2)
    try:
        with pytest.raises(queue_manager._InferenceTimeout):
            queue_manager._run_with_timeout("fake-task")
        assert top_runtime_state.orphan_inference_count() >= 1, "超时后应计入孤儿计数"
    finally:
        top_runtime_state.reset_orphan_inference()


def test_slot_guard_fails_fast_when_orphan(client, new_shot, monkeypatch):
    """P1-3：存在孤儿线程时，新任务 fail-fast 标记失败，且不再启动推理。"""
    from backend.runtime_state import reset_orphan_inference
    from backend.routers import queue_manager as qm
    from backend.database import get_db
    reset_orphan_inference()

    called = {"n": 0}

    def fake_run(task_id):
        called["n"] += 1
        return {"asset_id": "ast_1", "path": "assets/x.mp4"}

    monkeypatch.setattr(qm, "run_inference", fake_run)
    # 注入孤儿：直接置位（无需真实超时线程）
    monkeypatch.setattr(qm.runtime_state, "orphan_inference_count", lambda: 1)

    _, sid = new_shot
    r = client.post("/api/generations", json={
        "shot_id": sid, "mode": "text", "prompt": "守卫测试", "params": {"duration": 5},
    })
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    # 等待 worker 消费（守卫应立即 fail-fast，任务进入 failed 终态）
    import time as _time
    for _ in range(50):
        st = client.get(f"/api/generations/{tid}").json()["status"]
        if st in ("failed", "completed"):
            break
        _time.sleep(0.1)
    body = client.get(f"/api/generations/{tid}").json()
    assert body["status"] == "failed", body
    assert "孤儿" in body.get("error", ""), f"失败原因应含孤儿提示：{body.get('error')}"
    assert called["n"] == 0, "存在孤儿时不应启动新推理"

    conn = get_db()
    conn.execute("DELETE FROM generation_tasks WHERE id=?", (tid,))
    conn.execute("UPDATE shots SET status='pending' WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    reset_orphan_inference()


def test_health_exposes_orphan_count(client):
    """P1-3：/api/health 暴露 orphan_inference_count 字段（int）。"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "orphan_inference_count" in body
    assert isinstance(body["orphan_inference_count"], int)


def test_request_trace_middleware_headers_and_log(client):
    """P1-6：请求经中间件后响应含 X-Request-ID，且访问日志写入文件 handler。

    日志文件路径取 handler 实际绑定的 baseFilename——client fixture 会把
    settings.BASE_DIR 改到临时目录，而 configure_logging 在模块导入期已按
    真实 BASE_DIR 绑定，直接断言被 patch 的路径会误判不存在。
    """
    resp = client.get("/api/health")
    assert resp.status_code == 200
    rid = resp.headers.get("X-Request-ID")
    assert rid, "响应应携带 X-Request-ID"

    root = logging.getLogger()
    fh = next(h for h in root.handlers if getattr(h, "_mmh3_log", False))
    log_file = Path(fh.baseFilename)
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert rid in content, "访问日志应含该 request_id"


def test_json_log_line_format():
    """P1-6：文件日志为 JSON 单行结构化（含 time/level/logger/message，可机读检索）。"""
    import json as _json
    configure_logging()
    marker = "JSON_LOG_MARKER_%d" % int(time.time())
    logging.getLogger("ops_test_json").info(marker)
    log_file = backend_config.settings.BASE_DIR / "logs" / "backend.log"
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    hit = None
    for line in reversed(lines):
        if marker in line:
            hit = line
            break
    assert hit, "JSON 日志未找到标记行"
    parsed = _json.loads(hit)  # 非 JSON 会抛异常 → 格式不达标
    assert parsed["message"] == marker
    assert parsed["logger"] == "ops_test_json"
    assert "level" in parsed and "time" in parsed


def test_health_dependency_probe_field(client):
    """P2-8：/api/health 含 dependency 探测字段（type/reachable/detail）。"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    dep = resp.json()["dependency"]
    assert dep["type"] in ("diffusers", "comfy", "vllm-omni")
    assert "reachable" in dep and isinstance(dep["reachable"], bool)
    assert "detail" in dep


def test_comfy_health_inprocess_self_contained(monkeypatch):
    """P2-8：未设置 MMH3_COMFY_URL 时，comfy 引擎判定为进程内自包含（恒可达）。"""
    from backend.routers import comfy_engine
    monkeypatch.delenv("MMH3_COMFY_URL", raising=False)
    h = comfy_engine.check_health()
    assert h["reachable"] is True
    assert "进程内" in h["detail"]
