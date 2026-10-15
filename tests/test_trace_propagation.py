"""request_id ↔ task_id 贯通回归（后端服务设计评估 P1-2）。

middleware 注入的 request_id 须随任务 payload 落库（可追溯）、响应头 X-Request-ID
回传；queue_manager 侧日志 extra 携带双 ID（由 logging_config.JsonFormatter 的
extra 白名单承接，结构化 JSON 日志可检索）。
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_request_id_flows_to_task_payload(client, new_shot, mock_inference):
    _, sid = new_shot
    r = client.post("/api/generations", json={"shot_id": sid, "mode": "text", "prompt": "trace"})
    assert r.status_code == 200, r.text
    rid = r.headers.get("x-request-id")
    assert rid, "响应头缺 X-Request-ID"
    tid = r.json()["id"]
    g = client.get(f"/api/generations/{tid}").json()
    assert g["payload"].get("request_id") == rid


def test_request_id_is_sixteen_hex(client):
    r = client.get("/api/health")
    rid = r.headers.get("x-request-id", "")
    assert re.fullmatch(r"[0-9a-f]{16}", rid), f"request_id 形态漂移: {rid!r}"
