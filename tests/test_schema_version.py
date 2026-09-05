"""数据库 schema 版本管理测试（发布版本管理评估 P2 防回归）。

覆盖：
- 新建库：init_db 后 user_version == SCHEMA_VERSION
- 幂等：重复 init_db 版本不变、不报错
- 历史库（user_version=0）：补齐到基线版本
- 未来库（版本高于代码）：init_db 抛 RuntimeError，避免旧代码读新结构
- get_schema_version 直接读取 PRAGMA
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from backend.database import SCHEMA_VERSION, get_schema_version, get_db, init_db  # noqa: E402


@pytest.fixture()
def db_settings(monkeypatch, tmp_path):
    """把 settings 指向临时 DB。

    必须**改属性**而不是重新绑定模块变量：`backend.database` 在 import 时就把
    `config.settings` 这个对象绑进了自己的命名空间，重绑 `config.settings`
    不会影响它（会静默打到真实 data/mmh3.db）。双形态（backend.config / config）
    是两个模块对象，各持一个 Settings 实例，因此两处都要改。
    """
    db_path = tmp_path / "schema_test.db"
    import backend.config as bcfg
    import config as tcfg

    monkeypatch.setattr(bcfg.settings, "DB_PATH", db_path)
    monkeypatch.setattr(tcfg.settings, "DB_PATH", db_path)
    return db_path


def test_init_db_sets_baseline_schema_version(db_settings):
    init_db()
    conn = get_db()
    try:
        assert get_schema_version(conn) == SCHEMA_VERSION
    finally:
        conn.close()


def test_init_db_is_idempotent(db_settings):
    init_db()
    init_db()
    conn = get_db()
    try:
        assert get_schema_version(conn) == SCHEMA_VERSION
        # 迁移语句重复执行不报错，且 pair_asset_id 列存在
        cols = [r[1] for r in conn.execute("PRAGMA table_info(shot_refs)").fetchall()]
        assert "pair_asset_id" in cols
    finally:
        conn.close()


def test_legacy_database_is_upgraded(db_settings):
    """模拟历史库：先建到基线，再把 user_version 打回 0，重启后应补齐。"""
    init_db()
    conn = get_db()
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()

    init_db()
    conn = get_db()
    try:
        assert get_schema_version(conn) == SCHEMA_VERSION
    finally:
        conn.close()


def test_future_schema_version_is_rejected(db_settings):
    """库版本高于代码支持 → 明确报错，而不是静默读写。"""
    init_db()
    conn = get_db()
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="schema 版本"):
        init_db()


def test_get_schema_version_reads_pragma(tmp_path):
    """get_schema_version 直接反映 PRAGMA user_version。"""
    db_path = tmp_path / "raw.db"
    conn = sqlite3.connect(str(db_path))
    try:
        assert get_schema_version(conn) == 0
        conn.execute("PRAGMA user_version = 3")
        assert get_schema_version(conn) == 3
    finally:
        conn.close()
