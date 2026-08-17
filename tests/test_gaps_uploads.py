"""G3/G4 补齐回归测试：参考视频配对音轨 + 输入片段时长校验（2–15s/段、同类合计 ≤15s）。

使用 conftest.py fixtures 简化测试代码，避免重复辅助函数。
"""
import sys
from pathlib import Path

import pytest

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from routers import uploads  # 与应用同模块实例（main.py 以 routers.* 导入），保证 monkeypatch 生效
from backend.config import settings


def _uploads_file_count() -> int:
    """统计 uploads 目录当前文件数"""
    return len(list(settings.UPLOADS_DIR.iterdir()))


def _seed_image(client, sid) -> None:
    """音频测试需先配图（既有规则：音频须搭配图像或视频输入）。"""
    r = client.post("/api/upload", files={"file": ("seed.png", b"fake", "image/png")},
                    data={"shot_id": sid})
    assert r.status_code == 200, r.text


def test_upload_duration_too_long_rejected_and_no_orphan(client, new_project, new_shot, monkeypatch):
    """G4：探测到 20s 音频 → 422，且不留孤儿文件/资产记录。"""
    monkeypatch.setattr(uploads, "_probe_duration", lambda p: 20.0)
    
    pid = new_project
    sid = new_shot[1]
    _seed_image(client, sid)
    
    before_files = _uploads_file_count()
    r = client.post("/api/upload", files={"file": ("long.wav", b"fake", "audio/wav")},
                   data={"shot_id": sid})
    assert r.status_code == 422, r.text
    assert "2–15" in r.text
    assert _uploads_file_count() == before_files, "422 后不应遗留上传文件"


def test_upload_duration_ok_and_meta_recorded(client, new_project, new_shot, monkeypatch):
    """G4：3s 音频 → 200，assets.meta 记录 duration=3.0。"""
    monkeypatch.setattr(uploads, "_probe_duration", lambda p: 3.0)
    
    pid = new_project
    sid = new_shot[1]
    _seed_image(client, sid)
    
    r = client.post("/api/upload", files={"file": ("ok.wav", b"fake", "audio/wav")},
                   data={"shot_id": sid})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "audio"
    aid = r.json()["id"]
    
    from backend.database import get_db
    db = get_db()
    meta = db.execute("SELECT meta FROM assets WHERE id=?", (aid,)).fetchone()["meta"]
    db.close()
    assert '"duration": 3.0' in meta


def test_upload_duration_total_exceeded(client, new_project, new_shot, monkeypatch):
    """G4：同类合计 >15s → 422（已有时长 14s + 新 3s）。"""
    monkeypatch.setattr(uploads, "_probe_duration", lambda p: 3.0)
    monkeypatch.setattr(uploads, "_existing_kind_duration", lambda sid, kind: 14.0)
    
    pid = new_project
    sid = new_shot[1]
    
    r = client.post("/api/upload", files={"file": ("extra.mp4", b"fake", "video/mp4")},
                   data={"shot_id": sid})
    assert r.status_code == 422, r.text
    assert "合计时长超限" in r.text


def test_upload_pair_audio_to_video(client, new_project, new_shot, mock_ffprobe):
    """G3：视频 + 配对音轨成功；shots 接口回显 paired_video；负面用例 422。"""
    pid = new_project
    sid = new_shot[1]

    # 上传视频
    rv = client.post("/api/upload", files={"file": ("clip.mp4", b"fake", "video/mp4")},
                    data={"shot_id": sid})
    assert rv.status_code == 200, rv.text
    vid = rv.json()["id"]

    # 独立音频（不配对）
    ra = client.post("/api/upload", files={"file": ("standalone.wav", b"fake", "audio/wav")},
                    data={"shot_id": sid})
    assert ra.status_code == 200, ra.text

    # 配对音轨（paired_with=视频）
    rp = client.post("/api/upload", files={"file": ("track.wav", b"fake", "audio/wav")},
                    data={"shot_id": sid, "paired_with": vid})
    assert rp.status_code == 200, rp.text
    paid = rp.json()["id"]

    # shots 接口回显配对关系
    shots = client.get(f"/api/projects/{pid}/shots").json()
    refs = shots[0]["refs"]
    by_id = {r["id"]: r for r in refs}
    assert by_id[paid]["paired_video"] == vid
    assert by_id[ra.json()["id"]]["paired_video"] is None

    # 负面：把音频配对到图片 → 422
    ri = client.post("/api/upload", files={"file": ("img.png", b"fake", "image/png")},
                    data={"shot_id": sid})
    iid = ri.json()["id"]
    rbad = client.post("/api/upload", files={"file": ("bad.wav", b"fake", "audio/wav")},
                      data={"shot_id": sid, "paired_with": iid})
    assert rbad.status_code == 422 and "视频" in rbad.text

    # 负面：配对目标不属于当前镜头 → 422
    r2 = client.post("/api/projects", json={"name": "临时项目"})
    pid2 = r2.json()["id"]
    r3 = client.post(f"/api/projects/{pid2}/shots", json={"name": "镜头 B"})
    sid2 = r3.json()["id"]
    rv2 = client.post("/api/upload", files={"file": ("c2.mp4", b"fake", "video/mp4")},
                     data={"shot_id": sid2})
    vid2 = rv2.json()["id"]
    rbad2 = client.post("/api/upload", files={"file": ("x.wav", b"fake", "audio/wav")},
                       data={"shot_id": sid, "paired_with": vid2})
    assert rbad2.status_code == 422
