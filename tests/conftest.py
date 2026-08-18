"""
MM·H3 工作台 - Pytest 共享 Fixtures 与配置

提供：
- 测试专用临时数据库（内存 SQLite）
- 可复用的项目/镜头/资产创建辅助函数
- TestClient 自动管理
"""
import io
import sys
import tempfile
import json
from pathlib import Path

import pytest

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db


@pytest.fixture(scope="session")
def project_root():
    """返回项目根目录路径"""
    return PROJECT_ROOT


@pytest.fixture(scope="function")
def temp_db_path():
    """创建临时数据库文件路径（每个测试函数独立）"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    # 使用临时路径覆盖 settings
    original_db_path = None
    try:
        from backend import config
        original_db_path = config.settings.DB_PATH
        config.settings.DB_PATH = db_path
        init_db()
        yield db_path
    finally:
        # 清理临时数据库
        if db_path.exists():
            db_path.unlink()
        # 恢复原始配置
        if original_db_path:
            from backend import config
            config.settings.DB_PATH = original_db_path


@pytest.fixture(scope="function")
def client(temp_db_path):
    """
    提供 TestClient 实例，自动管理数据库生命周期。
    每个测试函数使用独立的临时数据库。
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def new_project(client):
    """
    创建一个测试项目，测试结束后自动清理。
    返回项目 ID。
    """
    r = client.post("/api/projects", json={"name": "测试项目"})
    assert r.status_code == 200, f"创建项目失败：{r.text}"
    pid = r.json()["id"]
    yield pid
    # 清理
    try:
        client.delete(f"/api/projects/{pid}")
    except Exception:
        pass


@pytest.fixture(scope="function")
def new_shot(client, new_project):
    """
    创建一个测试镜头，测试结束后随项目自动清理。
    返回 (项目 ID, 镜头 ID)。
    """
    pid = new_project
    r = client.post(
        f"/api/projects/{pid}/shots",
        json={"name": "测试镜头", "prompt": "测试提示词", "duration": 8}
    )
    assert r.status_code == 200, f"创建镜头失败：{r.text}"
    sid = r.json()["id"]
    return pid, sid


@pytest.fixture(scope="function")
def uploaded_asset(client, new_shot):
    """
    上传一个测试图片资产，测试结束后随镜头自动清理。
    返回 (项目 ID, 镜头 ID, 资产 ID)。
    """
    pid, sid = new_shot
    r = client.post(
        "/api/upload",
        files={"file": ("test.png", b"fake-png-content", "image/png")},
        data={"shot_id": sid}
    )
    assert r.status_code == 200, f"上传资产失败：{r.text}"
    aid = r.json()["id"]
    return pid, sid, aid


@pytest.fixture(scope="function")
def uploaded_video_asset(client, new_shot):
    """
    上传一个测试视频资产。
    返回 (项目 ID, 镜头 ID, 资产 ID)。
    """
    pid, sid = new_shot
    r = client.post(
        "/api/upload",
        files={"file": ("test.mp4", b"fake-mp4-content", "video/mp4")},
        data={"shot_id": sid}
    )
    assert r.status_code == 200, f"上传视频失败：{r.text}"
    aid = r.json()["id"]
    return pid, sid, aid


@pytest.fixture(scope="function")
def uploaded_audio_asset(client, new_shot):
    """
    上传一个测试音频资产（需先有图像或视频）。
    返回 (项目 ID, 镜头 ID, 资产 ID)。
    """
    pid, sid = new_shot
    # 先上传种子图片
    client.post(
        "/api/upload",
        files={"file": ("seed.png", b"fake-png", "image/png")},
        data={"shot_id": sid}
    )
    # 再上传音频
    r = client.post(
        "/api/upload",
        files={"file": ("test.wav", b"fake-wav-content", "audio/wav")},
        data={"shot_id": sid}
    )
    assert r.status_code == 200, f"上传音频失败：{r.text}"
    aid = r.json()["id"]
    return pid, sid, aid


@pytest.fixture(scope="function")
def paired_assets(client, new_shot):
    """
    上传配对的视频 + 音频资产。
    返回 (项目 ID, 镜头 ID, 视频 ID, 音频 ID)。
    """
    pid, sid = new_shot
    # 上传视频
    vr = client.post(
        "/api/upload",
        files={"file": ("clip.mp4", b"fake-mp4", "video/mp4")},
        data={"shot_id": sid}
    )
    vid = vr.json()["id"]
    # 上传配对音频
    ar = client.post(
        "/api/upload",
        files={"file": ("track.wav", b"fake-wav", "audio/wav")},
        data={"shot_id": sid, "paired_with": vid}
    )
    assert ar.status_code == 200, f"上传配对音频失败：{ar.text}"
    aid = ar.json()["id"]
    return pid, sid, vid, aid


@pytest.fixture(scope="function")
def mock_ffprobe(monkeypatch):
    """
    桩化 ffprobe 调用，返回 None（表示无法探测时长）。
    用于避免测试依赖真实 ffmpeg。
    """
    from routers import uploads
    monkeypatch.setattr(uploads, "_probe_duration", lambda p: None)
    return


@pytest.fixture(scope="function")
def mock_ffprobe_duration(monkeypatch):
    """
    桩化 ffprobe 调用，返回固定时长 5.0 秒。
    """
    from routers import uploads
    monkeypatch.setattr(uploads, "_probe_duration", lambda p: 5.0)
    return


@pytest.fixture(scope="function")
def mock_inference(monkeypatch):
    """
    桩化推理函数，模拟成功完成的任务。
    用于测试任务状态流转而不依赖真实模型。
    """
    import backend.routers.inference as inf
    import routers.inference as inf2

    def fake_run_inference(task_id):
        from backend.database import get_db, new_id
        conn = get_db()
        aid = new_id("ast_")
        conn.execute(
            "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
            (aid, "result", f"assets/{aid}.mp4", "video/mp4", 0, "{}"),
        )
        conn.commit()
        conn.close()
        return {"asset_id": aid, "path": f"assets/{aid}.mp4"}

    monkeypatch.setattr(inf, "run_inference", fake_run_inference)
    monkeypatch.setattr(inf2, "run_inference", fake_run_inference)
    return fake_run_inference


@pytest.fixture(scope="function")
def real_png_image():
    """
    生成真实的 PNG 图像字节数据（用于需要 PIL 解析的测试）。
    """
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (120, 90, 60)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="function")
def task_row_factory():
    """
    返回一个构建任务行数据的工厂函数，用于直接测试 _build_params。
    """
    def _factory(shot_id, mode, ref_ids, params):
        return {
            "shot_id": shot_id,
            "mode": mode,
            "payload": json.dumps({"prompt": "测试提示词", "params": params, "ref_ids": ref_ids}, ensure_ascii=False),
        }
    return _factory


@pytest.fixture(scope="function")
def h3_spec():
    """
    导入 H3 规格模块，供测试使用。
    """
    from h3 import spec as h3
    return h3
