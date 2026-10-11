"""结果资产配额清理测试（AI/ML 评估 P2 · 产物只增不减治理）。

覆盖：
  * 未超配额 → 不删任何资产
  * 超配额 → 按 created_at 裁剪最旧，保留最近 N 个
  * 解除引用：generation_tasks / shots 的 result_asset_id 置 NULL
  * 缩略图文件与 DB 行同步删除（meta.thumbnail）
  * 不触碰非 result 资产（用户上传参考素材）
  * max_assets<=0 → 跳过（不误删）
全部用 temp_db_path + tmp assets 目录，不触碰真实数据。
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import pytest

from cleanup import enforce_result_quota


@pytest.fixture()
def quota_env(temp_db_path):
    """temp_db_path 已隔离 DB + BASE_DIR/UPLOADS_DIR/ASSETS_DIR；返回 assets 目录。"""
    from config import settings
    return settings.ASSETS_DIR


def _insert_result(db, assets_dir, aid, order, *, thumb=True, kind="result"):
    """插入一个 result 资产 + 真实占位文件（+ 缩略图），created_at 由 order 错开。"""
    path = f"assets/{aid}.mp4"
    (assets_dir / f"{aid}.mp4").write_bytes(b"video-" + str(order).encode())
    meta = {}
    if thumb:
        (assets_dir / f"{aid}_thumb.jpg").write_bytes(b"thumb-" + str(order).encode())
        meta["thumbnail"] = f"assets/{aid}_thumb.jpg"
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (aid, kind, path, "video/mp4", 1, json.dumps(meta), f"2026-10-01 00:00:{order:02d}"),
    )


def _result_ids(db):
    return [r["id"] for r in db.execute(
        "SELECT id FROM assets WHERE kind='result' ORDER BY created_at ASC, rowid ASC"
    ).fetchall()]


def test_under_quota_no_removal(quota_env):
    from database import get_db
    db = get_db()
    for i in range(3):
        _insert_result(db, quota_env, f"r{i}", i)
    db.commit()
    assert enforce_result_quota(10, quota_env) == 0
    assert len(_result_ids(db)) == 3
    db.close()


def test_over_quota_removes_oldest_keeps_recent(quota_env):
    from database import get_db
    db = get_db()
    for i in range(5):
        _insert_result(db, quota_env, f"r{i}", i)
    db.commit()

    removed = enforce_result_quota(3, quota_env)
    assert removed == 2
    ids = _result_ids(db)
    assert ids == ["r2", "r3", "r4"], f"应保留最近 3 个（created_at 升序），实际: {ids}"
    # 文件同步删除
    assert not (quota_env / "r0.mp4").exists()
    assert not (quota_env / "r0_thumb.jpg").exists()
    assert (quota_env / "r4.mp4").exists()
    db.close()


def test_references_cleared(quota_env):
    from database import get_db
    db = get_db()
    _insert_result(db, quota_env, "r0", 0)
    _insert_result(db, quota_env, "r1", 1)
    # r0 被任务引用（将裁剪）；r1 被镜头引用（将保留）
    db.execute("INSERT INTO projects (id, name) VALUES ('p0', 'p')")
    db.execute(
        "INSERT INTO shots (id, project_id, name, prompt, status, result_asset_id) "
        "VALUES ('s0', 'p0', 'shot', '', 'completed', 'r1')"
    )
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status, result_asset_id) "
        "VALUES ('t0', 's0', 'text', '{}', 'completed', 'r0')"
    )
    db.commit()

    enforce_result_quota(1, quota_env)

    # 被裁剪资产（r0）的引用解除；保留资产（r1）的引用保持不断链
    assert db.execute("SELECT result_asset_id FROM generation_tasks WHERE id='t0'").fetchone()[0] is None
    assert db.execute("SELECT result_asset_id FROM shots WHERE id='s0'").fetchone()[0] == "r1"
    db.close()


def test_non_result_assets_untouched(quota_env):
    from database import get_db
    db = get_db()
    _insert_result(db, quota_env, "r0", 0, thumb=False)
    _insert_result(db, quota_env, "r1", 1, thumb=False)
    # 用户上传的参考素材（kind=image）不属于 result，绝不清理
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta, created_at) "
        "VALUES ('u0', 'image', 'uploads/u0.png', 'image/png', 1, '{}', '2026-10-01 00:00:00')"
    )
    (quota_env / "u0.png").write_bytes(b"user-upload")
    db.commit()
    db.close()

    # 2 个 result 超配额 1 → 裁剪 1 个；image 参考素材必须保留
    assert enforce_result_quota(1, quota_env) == 1

    from database import get_db as g2
    db = g2()
    ids = [r["id"] for r in db.execute("SELECT id FROM assets ORDER BY id").fetchall()]
    assert "u0" in ids, "参考素材不得被清理"
    assert "r1" in ids and "r0" not in ids
    assert (quota_env / "u0.png").exists(), "参考素材文件不得被删除"
    assert not (quota_env / "r0.mp4").exists()
    db.close()


def test_invalid_quota_skips(quota_env):
    from database import get_db
    db = get_db()
    _insert_result(db, quota_env, "r0", 0)
    db.commit()
    assert enforce_result_quota(0, quota_env) == 0
    assert len(_result_ids(db)) == 1
    assert enforce_result_quota(-1, quota_env) == 0
    assert len(_result_ids(db)) == 1
    db.close()
