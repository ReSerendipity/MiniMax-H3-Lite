"""database.py 单元测试 — 纯 CRUD 逻辑（不依赖 FastAPI / TestClient）。

覆盖：
- new_id：前缀 + 长度 + 唯一性
- row_to_dict：正常行 / None / JSON 反序列化 / 损坏 JSON
- rows_to_dicts：列表映射
- now_iso：ISO 8601 格式
- init_db：幂等建表 + 外键约束 + 索引
- get_db：连接属性（WAL / foreign_keys / Row factory）
- 完整 CRUD 往返：projects / shots / assets / generation_tasks / shot_refs
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from backend.database import get_db, init_db, new_id, now_iso, row_to_dict, rows_to_dicts
from backend.config import Settings


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    """完全隔离的临时 DB，双形态 patch。"""
    db_path = tmp_path / "test.db"
    s = Settings(DB_PATH=db_path)
    import backend.config as bcfg
    import config as tcfg
    monkeypatch.setattr(bcfg, "settings", s)
    monkeypatch.setattr(tcfg, "settings", s)
    init_db()
    return db_path


# ── new_id ─────────────────────────────────────────────

def test_new_id_default_prefix():
    """无前缀 → 12 位 hex。"""
    nid = new_id()
    assert len(nid) == 12
    assert all(c in "0123456789abcdef" for c in nid)


def test_new_id_with_prefix():
    """有前缀 → 前缀 + 12 位 hex。"""
    nid = new_id("proj_")
    assert nid.startswith("proj_")
    assert len(nid) == len("proj_") + 12


def test_new_id_unique():
    """连续调用应产生不同 ID。"""
    ids = {new_id("t_") for _ in range(100)}
    assert len(ids) == 100


# ── now_iso ────────────────────────────────────────────

def test_now_iso_format():
    """now_iso 应返回 ISO 8601 格式（以 Z 结尾）。"""
    ts = now_iso()
    assert ts.endswith("Z")
    assert "T" in ts
    # 应可被解析
    from datetime import datetime, timezone
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.tzinfo == timezone.utc


# ── row_to_dict ────────────────────────────────────────

def test_row_to_dict_none():
    """None 行 → None。"""
    assert row_to_dict(None) is None


def test_row_to_dict_basic():
    """普通行 → 字典。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (id TEXT, name TEXT)")
    conn.execute("INSERT INTO t VALUES ('1', 'hello')")
    row = conn.execute("SELECT * FROM t").fetchone()
    d = row_to_dict(row)
    assert d["id"] == "1"
    assert d["name"] == "hello"
    conn.close()


def test_row_to_dict_json_fields():
    """JSON 字段（params/payload/meta）应被反序列化。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (id TEXT, params TEXT, payload TEXT, meta TEXT)")
    conn.execute("INSERT INTO t VALUES ('1', '{\"key\":\"v\"}', '{\"p\":1}', '{\"m\":2}')")
    row = conn.execute("SELECT * FROM t").fetchone()
    d = row_to_dict(row)
    assert d["params"] == {"key": "v"}
    assert d["payload"] == {"p": 1}
    assert d["meta"] == {"m": 2}
    conn.close()


def test_row_to_dict_corrupted_json_kept_as_string():
    """损坏的 JSON 应保留为原始字符串（不抛异常）。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (id TEXT, params TEXT)")
    conn.execute("INSERT INTO t VALUES ('1', '<<<not json>>>')")
    row = conn.execute("SELECT * FROM t").fetchone()
    d = row_to_dict(row)
    assert d["params"] == "<<<not json>>>"
    conn.close()


def test_row_to_dict_null_json_field():
    """NULL JSON 字段 → 保持 None。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (id TEXT, params TEXT)")
    conn.execute("INSERT INTO t VALUES ('1', NULL)")
    row = conn.execute("SELECT * FROM t").fetchone()
    d = row_to_dict(row)
    assert d["params"] is None
    conn.close()


# ── rows_to_dicts ──────────────────────────────────────

def test_rows_to_dicts_empty():
    """空列表 → 空列表。"""
    assert rows_to_dicts([]) == []


def test_rows_to_dicts_multiple():
    """多行 → 字典列表。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (id TEXT, name TEXT)")
    conn.execute("INSERT INTO t VALUES ('1', 'a')")
    conn.execute("INSERT INTO t VALUES ('2', 'b')")
    rows = conn.execute("SELECT * FROM t ORDER BY id").fetchall()
    result = rows_to_dicts(rows)
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[1]["id"] == "2"
    conn.close()


# ── init_db ────────────────────────────────────────────

def test_init_db_idempotent(isolated_db):
    """多次 init_db 不应报错（幂等）。"""
    init_db()  # 第二次
    init_db()  # 第三次
    # 表应存在
    db = get_db()
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    db.close()
    assert "projects" in tables
    assert "shots" in tables
    assert "generation_tasks" in tables
    assert "assets" in tables
    assert "shot_refs" in tables


def test_init_db_creates_indexes(isolated_db):
    """索引应被创建。"""
    db = get_db()
    indexes = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    ).fetchall()]
    db.close()
    assert "idx_tasks_shot" in indexes
    assert "idx_tasks_status" in indexes
    assert "idx_assets_kind" in indexes


# ── get_db 属性 ────────────────────────────────────────

def test_get_db_row_factory(isolated_db):
    """get_db 返回的连接应使用 Row factory。"""
    db = get_db()
    assert db.row_factory == sqlite3.Row
    db.close()


def test_get_db_wal_mode(isolated_db):
    """WAL 模式应启用。"""
    db = get_db()
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    db.close()
    assert mode.lower() == "wal"


def test_get_db_foreign_keys(isolated_db):
    """外键约束应启用。"""
    db = get_db()
    fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
    db.close()
    assert fk == 1


# ── CRUD 往返 ──────────────────────────────────────────

def test_project_crud(isolated_db):
    """projects 表 CRUD 往返。"""
    db = get_db()
    pid = new_id("proj_")
    db.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (pid, "测试项目"))
    db.commit()

    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    d = row_to_dict(row)
    assert d["name"] == "测试项目"

    db.execute("UPDATE projects SET name=? WHERE id=?", ("改名", pid))
    db.commit()
    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    assert row["name"] == "改名"

    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM projects WHERE id=?", (pid,)).fetchone()[0] == 0
    db.close()


def test_shot_cascade_delete(isolated_db):
    """删除项目应级联删除其镜头。"""
    db = get_db()
    pid = new_id("proj_")
    sid = new_id("shot_")
    db.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (pid, "p"))
    db.execute("INSERT INTO shots (id, project_id, ord, name) VALUES (?, ?, 0, 's')", (sid, pid))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM shots WHERE project_id=?", (pid,)).fetchone()[0] == 1

    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM shots WHERE project_id=?", (pid,)).fetchone()[0] == 0
    db.close()


def test_shot_ref_cascade_delete(isolated_db):
    """删除镜头应级联删除其 shot_refs。"""
    db = get_db()
    pid = new_id("proj_")
    sid = new_id("shot_")
    aid = new_id("ast_")
    db.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (pid, "p"))
    db.execute("INSERT INTO shots (id, project_id, ord, name) VALUES (?, ?, 0, 's')", (sid, pid))
    db.execute("INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
               (aid, "image", "uploads/x.png", "image/png", 100, "{}"))
    db.execute("INSERT INTO shot_refs (shot_id, asset_id, ref_type, ord) VALUES (?, ?, 'image', 0)",
               (sid, aid))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM shot_refs WHERE shot_id=?", (sid,)).fetchone()[0] == 1

    db.execute("DELETE FROM shots WHERE id=?", (sid,))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM shot_refs WHERE shot_id=?", (sid,)).fetchone()[0] == 0
    db.close()


def test_generation_task_insert_and_query(isolated_db):
    """generation_tasks 表插入与查询。"""
    db = get_db()
    pid = new_id("proj_")
    sid = new_id("shot_")
    tid = new_id("task_")
    db.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (pid, "p"))
    db.execute("INSERT INTO shots (id, project_id, ord, name) VALUES (?, ?, 0, 's')", (sid, pid))
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES (?, ?, ?, ?, ?)",
        (tid, sid, "text", json.dumps({"prompt": "hi"}), "pending"),
    )
    db.commit()

    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (tid,)).fetchone()
    d = row_to_dict(row)
    assert d["status"] == "pending"
    assert d["payload"]["prompt"] == "hi"  # JSON 反序列化
    assert d["progress"] == 0
    db.close()


def test_asset_insert_with_meta(isolated_db):
    """assets 表插入含 meta JSON。"""
    db = get_db()
    aid = new_id("ast_")
    meta = {"original_name": "photo.png", "width": 1920, "height": 1080}
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
        (aid, "image", f"uploads/{aid}.png", "image/png", 2048, json.dumps(meta)),
    )
    db.commit()
    row = db.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    d = row_to_dict(row)
    assert d["kind"] == "image"
    assert d["meta"]["width"] == 1920
    db.close()
