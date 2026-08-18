"""MM·H3 工作台 — 核心 API 集成测试（路线图 #1）

覆盖四大路由：uploads / projects / generations / history，共 10 个用例。
复用 conftest.py fixtures（isolated temp DB + TestClient + mock_inference）。
"""
import pytest

pytestmark = pytest.mark.integration


# ── uploads（3）─────────────────────────────────────────────
def test_upload_image_success(client, new_shot):
    """上传图片资产成功。"""
    _, sid = new_shot
    r = client.post(
        "/api/upload",
        files={"file": ("test.png", b"fake-png-content", "image/png")},
        data={"shot_id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"]


def test_upload_without_shot_id_succeeds(client):
    """不绑定镜头（独立上传）按设计允许，落盘为独立资产。"""
    r = client.post(
        "/api/upload",
        files={"file": ("standalone.png", b"fake-png-content", "image/png")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"]


def test_upload_rejects_unknown_file_type(client, new_shot):
    """不支持的文件类型应被拒绝。"""
    _, sid = new_shot
    r = client.post(
        "/api/upload",
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
        data={"shot_id": sid},
    )
    assert r.status_code >= 400, r.text


# ── projects（3）────────────────────────────────────────────
def test_project_create_and_get(client):
    """创建项目后可读取详情。"""
    r = client.post("/api/projects", json={"name": "集成测试项目"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    try:
        detail = client.get(f"/api/projects/{pid}")
        assert detail.status_code == 200
        assert detail.json()["name"] == "集成测试项目"
    finally:
        client.delete(f"/api/projects/{pid}")


def test_project_create_default_name(client):
    """不提供名称时使用默认名。"""
    r = client.post("/api/projects", json={})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "未命名项目"
    client.delete(f"/api/projects/{r.json()['id']}")


def test_project_clear_all(client):
    """清空全部项目后列表为空。"""
    p1 = client.post("/api/projects", json={"name": "A"}).json()["id"]
    p2 = client.post("/api/projects", json={"name": "B"}).json()["id"]
    r = client.post("/api/projects/clear")
    assert r.status_code == 200, r.text
    lst = client.get("/api/projects").json()
    assert all(p["id"] not in (p1, p2) for p in lst)


# ── generations（2）─────────────────────────────────────────
def test_generation_submit_and_status(client, new_shot, mock_inference):
    """提交生成任务后可通过 tid 查询状态。"""
    _, sid = new_shot
    r = client.post("/api/generations", json={
        "shot_id": sid,
        "mode": "text",
        "prompt": "一只猫在月光下奔跑",
        "params": {"aspect": "16:9", "duration": 5, "fps": 24},
    })
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    t = client.get(f"/api/generations/{tid}")
    assert t.status_code == 200
    body = t.json()
    assert body["id"] == tid
    assert body["status"] in ("pending", "processing", "completed", "failed")


def test_generation_rejects_unknown_shot(client):
    """不存在的镜头应被拒绝。"""
    r = client.post("/api/generations", json={
        "shot_id": "shot_does_not_exist",
        "mode": "text",
        "prompt": "测试",
    })
    assert r.status_code >= 400, r.text


# ── history（2）─────────────────────────────────────────────
def test_history_lists_generation(client, new_shot, mock_inference):
    """完成生成后项目历史应包含该任务。"""
    pid, sid = new_shot
    client.post("/api/generations", json={
        "shot_id": sid,
        "mode": "text",
        "prompt": "历史记录测试",
        "params": {"duration": 5},
    })
    r = client.get(f"/api/projects/{pid}/history")
    assert r.status_code == 200, r.text
    history = r.json()
    assert isinstance(history, list)
    assert len(history) >= 1


def test_history_empty_project(client, new_project):
    """新项目历史为空列表。"""
    pid = new_project
    r = client.get(f"/api/projects/{pid}/history")
    assert r.status_code == 200, r.text
    assert r.json() == []
