"""Isolation self-test: assert test settings point at temp DB, not real data/mmh3.db."""

from backend.config import settings as pkg_settings
import config as top_settings


def test_db_path_is_temp(temp_db_path):
    """运行测试期间 settings.DB_PATH 必须指向临时文件，而非真实 data/mmh3.db。"""
    real = "data/mmh3.db"
    assert real not in str(pkg_settings.DB_PATH), f"backend.config 仍指向真实库: {pkg_settings.DB_PATH}"
    assert real not in str(top_settings.settings.DB_PATH), f"顶层 config 仍指向真实库: {top_settings.settings.DB_PATH}"
    assert str(pkg_settings.DB_PATH) == str(temp_db_path)
    assert str(top_settings.settings.DB_PATH) == str(temp_db_path)


def test_temp_db_is_isolated(client, temp_db_path):
    """在隔离库上写数据不影响真实库。"""
    r = client.post("/api/projects", json={"name": "隔离自证"})
    assert r.status_code == 200, r.text
    # 临时库中应能查到该项目
    import sqlite3
    conn = sqlite3.connect(str(temp_db_path))
    cnt = conn.execute("SELECT COUNT(*) FROM projects WHERE name='隔离自证'").fetchone()[0]
    conn.close()
    assert cnt == 1
