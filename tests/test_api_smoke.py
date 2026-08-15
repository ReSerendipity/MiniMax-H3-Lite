"""MM·H3 工作台 API 冒烟测试（重构后：真实数据流，无占位假成功）"""
import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app


def _new_project(client) -> str:
    r = client.post("/api/projects", json={"name": "冒烟测试项目"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_health():
    with TestClient(app) as c:
        h = c.get("/api/health").json()
        assert h["status"] == "ok"
        assert h["model"] and h["max_concurrency"] > 0


def test_project_crud():
    with TestClient(app) as c:
        pid = _new_project(c)
        # 列表
        lst = c.get("/api/projects").json()
        assert any(p["id"] == pid for p in lst)
        # 重命名
        r = c.put(f"/api/projects/{pid}", json={"name": "改名"})
        assert r.status_code == 200 and r.json()["name"] == "改名"
        # 删除
        assert c.delete(f"/api/projects/{pid}").status_code == 200


def test_shot_crud_and_refs():
    with TestClient(app) as c:
        pid = _new_project(c)
        # 创建镜头
        r = c.post(f"/api/projects/{pid}/shots", json={"name": "镜头A", "prompt": "测试", "duration": 8})
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        # 列表（含 refs 字段）
        shots = c.get(f"/api/projects/{pid}/shots").json()
        assert len(shots) == 1 and shots[0]["refs"] == []
        # 更新镜头
        r = c.put(f"/api/shots/{sid}", json={"prompt": "新提示词", "duration": 4})
        assert r.status_code == 200 and r.json()["prompt"] == "新提示词"
        # 删除镜头
        assert c.delete(f"/api/shots/{sid}").status_code == 200


def test_upload():
    with TestClient(app) as c:
        pid = _new_project(c)
        sid = c.post(f"/api/projects/{pid}/shots", json={"name": "镜头A"}).json()["id"]
        # 上传 png
        r = c.post("/api/upload", files={"file": ("a.png", io.BytesIO(b"fake-png"), "image/png")},
                   data={"shot_id": sid})
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        assert r.json()["kind"] == "image"
        # 镜头列表 refs 带出素材
        shots = c.get(f"/api/projects/{pid}/shots").json()
        assert shots[0]["refs"][0]["id"] == aid
        # 不支持的格式
        r = c.post("/api/upload", files={"file": ("x.exe", io.BytesIO(b"x"), "application/octet-stream")})
        assert r.status_code == 422


def test_generation_validation_and_submit(monkeypatch):
    # 真实推理在当前环境依赖不完整（diffusers/transformers 版本不兼容），
    # 用假推理函数验证完整状态机流转（pending → processing → completed + result_path）
    import backend.routers.inference as inf
    import routers.inference as inf2  # worker 通过该路径导入（同一文件的两个模块实例）

    def fake_infer(task_id):
        # 与真实 run_inference 一致：落盘资产记录后返回真实 aid
        import backend.database as dbm
        conn = dbm.get_db()
        aid = dbm.new_id("ast_")
        conn.execute(
            "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
            (aid, "result", f"assets/{aid}.mp4", "video/mp4", 0, "{}"),
        )
        conn.commit()
        conn.close()
        return {"asset_id": aid, "path": f"assets/{aid}.mp4"}
    monkeypatch.setattr(inf, "run_inference", fake_infer)
    monkeypatch.setattr(inf2, "run_inference", fake_infer)
    with TestClient(app) as c:
        # 镜头不存在 → 404
        r = c.post("/api/generations", json={"shot_id": "nope", "mode": "text", "prompt": "x", "params": {}})
        assert r.status_code == 404
        # 正常提交
        pid = _new_project(c)
        sid = c.post(f"/api/projects/{pid}/shots", json={"name": "镜头A", "prompt": "黄昏", "duration": 8}).json()["id"]
        r = c.post("/api/generations", json={
            "shot_id": sid, "mode": "text", "prompt": "黄昏的海岸线",
            "params": {"duration": 8, "aspect": "16:9", "resolution": "768P"},
            "ref_ids": [],
        })
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        assert r.json()["status"] == "pending"
        # 任务查询：pending + 无 result_path（未完成）
        # 轮询至终态（真实 Worker 状态机）
        import time
        final = None
        for _ in range(30):
            t = c.get(f"/api/generations/{tid}").json()
            if t["status"] in ("completed", "failed"):
                final = t
                break
            time.sleep(0.2)
        assert final is not None, "任务未在超时内进入终态"
        assert final["status"] == "completed", f"任务应完成: {final}"
        assert final["result_path"] == "assets/" + final["result_asset_id"] + ".mp4"
        # 镜头状态同步为 completed
        shots = c.get(f"/api/projects/{pid}/shots").json()
        assert shots[0]["status"] == "completed"


def test_inference_no_placeholder():
    """推理模块不再有占位假成功路径"""
    import backend.routers.inference as inf
    assert not hasattr(inf, "_run_placeholder"), "占位推理必须删除"
    src = Path(inf.__file__).read_text(encoding="utf-8")
    assert "演示模式" not in src and "占位" not in src, "推理模块残留占位/演示逻辑"


def test_frontend_no_demo_mode():
    """前端不再有演示模式回退与假镜头数据"""
    html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
    assert "演示模式" not in html, "前端残留演示模式"
    assert "shot_id:'demo'" not in html, "前端残留假 shot_id"
    assert "舞台独白" not in html, "前端残留假镜头 pool"
    assert 'data-name="黄昏海岸"' not in html, "前端残留静态演示镜头"
    assert "_run_placeholder" not in html
