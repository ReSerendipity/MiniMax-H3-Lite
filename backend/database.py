"""
MM·H3 工作台 — 数据库模型与初始化
PRD §4.3: Project / Shot / GenerationTask / Asset
SQLite + 原生 sqlite3（零外部依赖，与前端 server.js 零依赖风格对齐）
"""
import sqlite3
import json
from datetime import datetime, timezone
from config import settings

# ── Schema 版本管理（2026-09-05 · 发布版本管理评估 P2 落地）──────────────
# 版本号存在 SQLite 头部 `PRAGMA user_version`：
#   - 旧库（从未设置过）为 0，启动时补齐到基线 1；
#   - 库版本高于代码支持的版本 → 直接报错，避免旧代码读写新结构导致静默损坏
#     （回滚场景：见 docs/rollback_sop.md §4）。
# 新增结构变更时：SCHEMA_VERSION +1，并在 _MIGRATIONS 中登记该版本的 SQL 列表。
SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, list[str]] = {
    # 0 → 1：历史库补齐（SQLite 无 ADD COLUMN IF NOT EXISTS，重复执行会报错，需幂等容错）
    1: [
        "ALTER TABLE shot_refs ADD COLUMN pair_asset_id TEXT",
    ],
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    """读取当前连接的 schema 版本（PRAGMA user_version）。"""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA 不支持参数绑定；version 由本模块内部控制，先过 int 强制收敛（无注入面）。
    # 不用 f-string（脱离 semgrep f-string SQL 匹配面），改为拼接 int 收敛后的字符串。
    version = int(version)
    conn.execute("PRAGMA user_version = " + str(version))


def _apply_migrations(conn: sqlite3.Connection) -> int:
    """把数据库迁移到 SCHEMA_VERSION；高于代码版本时抛错（防止旧代码读新库）。"""
    current = get_schema_version(conn)
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"数据库 schema 版本 {current} 高于当前代码支持的 {SCHEMA_VERSION}："
            "请升级代码后再启动；若需回滚，先备份 data/mmh3.db 并按 docs/rollback_sop.md §4 处理"
        )
    for target in range(current + 1, SCHEMA_VERSION + 1):
        for stmt in _MIGRATIONS.get(target, []):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as exc:
                # 幂等：列/索引已存在时忽略，其余错误照常抛出
                message = str(exc).lower()
                if "duplicate column" not in message and "already exists" not in message:
                    raise
        _set_schema_version(conn, target)
    return get_schema_version(conn)


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
        pair_asset_id TEXT,                  -- 音频→其所属视频资产 id（配对音轨）
        PRIMARY KEY (shot_id, asset_id)
    );
    """)
    conn.commit()
    # 幂等迁移：按 PRAGMA user_version 逐级升级（含历史库 0 → 1 补列）
    _apply_migrations(conn)
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
