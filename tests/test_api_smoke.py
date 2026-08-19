"""MM·H3 工作台 API 冒烟测试（重构后：真实数据流，无占位假成功）

使用 conftest.py 提供的 fixtures：
- client: TestClient with isolated temp DB
- new_project: auto-cleanup project fixture
- mock_inference: stub for inference without real model
"""
import io
import sys
import time
from pathlib import Path

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_health(client):
    """健康检查应返回模型信息与并发数"""
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["model"] and h["max_concurrency"] > 0


def test_project_crud(client):
    """项目 CRUD 操作验证"""
    # 创建
    r = client.post("/api/projects", json={"name": "冒烟测试项目"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    try:
        # 列表
        lst = client.get("/api/projects").json()
        assert any(p["id"] == pid for p in lst)

        # 重命名
        r = client.put(f"/api/projects/{pid}", json={"name": "改名"})
        assert r.status_code == 200 and r.json()["name"] == "改名"
    finally:
        # 删除
        client.delete(f"/api/projects/{pid}")


def test_shot_crud_and_refs(client, new_project):
    """镜头 CRUD 及 refs 字段验证"""
    pid = new_project

    # 创建镜头
    r = client.post(f"/api/projects/{pid}/shots", json={"name": "镜头 A", "prompt": "测试", "duration": 8})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    try:
        # 列表（含 refs 字段）
        shots = client.get(f"/api/projects/{pid}/shots").json()
        assert len(shots) == 1 and shots[0]["refs"] == []

        # 更新镜头
        r = client.put(f"/api/shots/{sid}", json={"prompt": "新提示词", "duration": 4})
        assert r.status_code == 200 and r.json()["prompt"] == "新提示词"
    finally:
        # 删除镜头
        client.delete(f"/api/shots/{sid}")


def test_upload(client, new_project):
    """素材上传及镜头 refs 回显验证"""
    pid = new_project

    # 创建镜头
    r = client.post(f"/api/projects/{pid}/shots", json={"name": "镜头 A"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    try:
        # 上传 png
        r = client.post(
            "/api/upload",
            files={"file": ("a.png", io.BytesIO(b"fake-png"), "image/png")},
            data={"shot_id": sid},
        )
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        assert r.json()["kind"] == "image"

        # 镜头列表 refs 带出素材
        shots = client.get(f"/api/projects/{pid}/shots").json()
        assert shots[0]["refs"][0]["id"] == aid

        # 不支持的格式
        r = client.post("/api/upload", files={"file": ("x.exe", io.BytesIO(b"x"), "application/octet-stream")})
        assert r.status_code == 422
    finally:
        client.delete(f"/api/shots/{sid}")


def test_generation_rejects_unknown_shot(client, mock_inference):
    """镜头不存在 → 404。"""
    r = client.post("/api/generations", json={"shot_id": "nope", "mode": "text", "prompt": "x", "params": {}})
    assert r.status_code == 404


def test_generation_submit_returns_pending(client, new_project, mock_inference):
    """正常提交 → 200 + status=pending。"""
    pid = new_project
    r = client.post(f"/api/projects/{pid}/shots", json={"name": "镜头 A", "prompt": "黄昏", "duration": 8})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r = client.post("/api/generations", json={
        "shot_id": sid, "mode": "text", "prompt": "黄昏的海岸线",
        "params": {"duration": 8, "aspect": "16:9", "resolution": "768P"},
        "ref_ids": [],
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"

def test_generation_completes_and_syncs_shot(client, new_project, mock_inference):
    """任务轮询至 completed + 镜头状态同步为 completed。"""
    pid = new_project
    r = client.post(f"/api/projects/{pid}/shots", json={"name": "镜头 A", "prompt": "黄昏", "duration": 8})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r = client.post("/api/generations", json={
        "shot_id": sid, "mode": "text", "prompt": "黄昏的海岸线",
        "params": {"duration": 8, "aspect": "16:9"},
        "ref_ids": [],
    })
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    final = None
    for _ in range(30):
        t = client.get(f"/api/generations/{tid}").json()
        if t["status"] in ("completed", "failed"):
            final = t
            break
        time.sleep(0.2)

    assert final is not None, "任务未在超时内进入终态"
    assert final["status"] == "completed", f"任务应完成：{final}"
    assert final["result_path"] == "assets/" + final["result_asset_id"] + ".mp4"


    shots = client.get(f"/api/projects/{pid}/shots").json()
    assert shots[0]["status"] == "completed"


def test_inference_no_placeholder():
    """推理模块不再有占位假成功路径"""
    import backend.routers.inference as inf

    assert not hasattr(inf, "_run_placeholder"), "占位推理必须删除"
    src = Path(inf.__file__).read_text(encoding="utf-8")
    assert "演示模式" not in src and "占位" not in src, "推理模块残留占位/演示逻辑"


def test_frontend_no_demo_mode(project_root):
    """前端模板不再有演示模式回退与假镜头数据"""
    html = (project_root / "backend" / "templates" / "t2v.html").read_text(encoding="utf-8")
    assert "演示模式" not in html, "前端残留演示模式"
    assert "shot_id:'demo'" not in html, "前端残留假 shot_id"
    assert "舞台独白" not in html, "前端残留假镜头 pool"
    assert 'data-name="黄昏海岸"' not in html, "前端残留静态演示镜头"
    assert "_run_placeholder" not in html
