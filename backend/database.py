"""
MM·H3 工作台 — 数据库模型与初始化
PRD §4.3: Project / Shot / GenerationTask / Asset
SQLite + 原生 sqlite3（零外部依赖，与前端 server.js 零依赖风格对齐）
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from config import settings


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """建库建表（幂等）"""
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL DEFAULT '未命名项目',
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS shots (
        id              TEXT PRIMARY KEY,
        project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        ord             INTEGER NOT NULL DEFAULT 0,
        name            TEXT NOT NULL DEFAULT '新镜头',
        prompt          TEXT NOT NULL DEFAULT '',
        mode            TEXT NOT NULL DEFAULT 'text',   -- text|first_frame|last_frame|first_last|ref
        params          TEXT NOT NULL DEFAULT '{}',      -- JSON: aspect, resolution, duration, fps, audio_sr, motion, style, bridge, twok
        duration        INTEGER NOT NULL DEFAULT 8,
        aspect          TEXT NOT NULL DEFAULT '16:9',
        status          TEXT NOT NULL DEFAULT 'idle',   -- idle|queued|processing|completed|failed
        result_asset_id  TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS generation_tasks (
        id              TEXT PRIMARY KEY,
        shot_id         TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
        mode            TEXT NOT NULL DEFAULT 'text',
        payload         TEXT NOT NULL DEFAULT '{}',      -- JSON: prompt + params + ref_ids
        status          TEXT NOT NULL DEFAULT 'pending', -- pending|processing|completed|failed
        progress        INTEGER NOT NULL DEFAULT 0,      -- 0-100
        error           TEXT,
        result_asset_id TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at     TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_tasks_shot ON generation_tasks(shot_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON generation_tasks(status);

    CREATE TABLE IF NOT EXISTS assets (
        id          TEXT PRIMARY KEY,
        kind        TEXT NOT NULL,           -- image|video|audio|result
        path        TEXT NOT NULL,
        mime        TEXT NOT NULL,
        size        INTEGER NOT NULL DEFAULT 0,
        meta        TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);

    CREATE TABLE IF NOT EXISTS shot_refs (
        shot_id     TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
        asset_id    TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
        ref_type    TEXT NOT NULL,           -- image|video|audio
        ord         INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (shot_id, asset_id)
    );
    """)
    conn.commit()
    conn.close()


# ── 辅助函数 ──────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str = "") -> str:
    """生成短 ID（时间戳 + 随机后缀）"""
    import uuid
    return prefix + uuid.uuid4().hex[:12]


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    # JSON 字段反序列化
    for k in ("params", "payload", "meta"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [row_to_dict(r) for r in rows]
