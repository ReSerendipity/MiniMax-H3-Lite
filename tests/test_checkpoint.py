"""MM·H3 工作台 — checkpoint 断点续跑测试（路线图 #7）

覆盖：
- TaskCheckpoint save → load 往返
- should_checkpoint 阈值
- list / remove 清理
- 恢复逻辑（fake 数据，不跑真实推理）
- _snapshot_unfinished / _on_task_completed 快照

隔离说明：backend 下模块以两种形态存在（顶层 `routers.queue_manager`/`config`
与 `backend.routers.queue_manager`/`backend.config` 是不同模块对象）。测试通过
`isolated_settings` fixture 同时覆盖两种 settings，并把 DB/checkpoint 指向临时目录，
绝不触碰真实 data/mmh3.db 与 data/checkpoints。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


@pytest.fixture()
def isolated_settings(monkeypatch, tmp_path):
    """把两种形态的 settings 同时指向临时 DB 与临时 checkpoint 目录。"""
    import backend.config as bcfg
    import config as tcfg
    from backend.database import init_db

    db_path = tmp_path / "test.db"
    ckpt_dir = tmp_path / "ckpts"
    for cfg_mod in (tcfg, bcfg):
        monkeypatch.setattr(cfg_mod.settings, "DB_PATH", db_path)
        monkeypatch.setattr(cfg_mod.settings, "CHECKPOINT_DIR", ckpt_dir)
        monkeypatch.setattr(cfg_mod.settings, "CHECKPOINT_EVERY", 5)
    init_db()
    return db_path, ckpt_dir


# ── TaskCheckpoint 基础单元 ────────────────────────────────


def test_save_load_roundtrip(tmp_path):
    """save → load 往返：写入后能正确读回所有字段。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    state = {
        "engine": "diffusers",
        "total": 10,
        "completed_items": ["s1", "s2", "s3"],
        "remaining": ["s4", "s5", "s6", "s7", "s8", "s9", "s10"],
        "config": {"mode": "text", "duration": 8, "prompt": "测试"},
    }
    ckpt.save("task_abc", state)
    data = ckpt.load("task_abc")
    assert data is not None
    assert data["task_id"] == "task_abc"
    assert data["engine"] == "diffusers"
    assert data["total"] == 10
    assert data["completed"] == 3
    assert data["completed_items"] == ["s1", "s2", "s3"]
    assert data["remaining"] == ["s4", "s5", "s6", "s7", "s8", "s9", "s10"]
    assert data["config"]["mode"] == "text"
    assert data["config"]["prompt"] == "测试"
    assert isinstance(data["updated_at"], float)


def test_load_nonexistent(tmp_path):
    """不存在任务返回 None。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    assert ckpt.load("no_such_task") is None


def test_load_corrupted_file(tmp_path):
    """损坏的 JSON 文件返回 None。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    ckpt._path("bad").write_text("<<<not json>>>", encoding="utf-8")
    assert ckpt.load("bad") is None


def test_path_sanitization(tmp_path):
    """路径穿越字符被过滤。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    p = ckpt._path("task/../../etc/passwd")
    assert ".." not in p.name
    assert "/" not in p.name
    assert p.suffix == ".json"


def test_save_atomic(tmp_path):
    """原子写入：即使重复 save 同一 task_id，文件内容始终一致。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    ckpt.save("t1", {"engine": "a", "total": 2, "completed_items": [], "remaining": ["x"], "config": {}})
    ckpt.save("t1", {"engine": "b", "total": 2, "completed_items": ["x"], "remaining": [], "config": {}})
    data = ckpt.load("t1")
    assert data["engine"] == "b"
    assert data["completed"] == 1


# ── should_checkpoint 阈值 ─────────────────────────────────


def test_should_checkpoint_threshold(tmp_path):
    """should_checkpoint 在 completed_count 为 checkpoint_every 的倍数时返回 True。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    assert not ckpt.should_checkpoint(0, 5)
    assert not ckpt.should_checkpoint(3, 5)
    assert ckpt.should_checkpoint(5, 5)
    assert not ckpt.should_checkpoint(7, 5)
    assert ckpt.should_checkpoint(10, 5)
    assert ckpt.should_checkpoint(15, 5)


def test_should_checkpoint_custom_every(tmp_path):
    """自定义 checkpoint_every。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    assert ckpt.should_checkpoint(2, 2)
    assert not ckpt.should_checkpoint(1, 2)
    assert ckpt.should_checkpoint(4, 2)
    assert ckpt.should_checkpoint(1, 1)


def test_should_checkpoint_zero_every_disabled(tmp_path):
    """checkpoint_every <= 0 视为关闭。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    assert not ckpt.should_checkpoint(5, 0)
    assert not ckpt.should_checkpoint(10, -1)


# ── list / remove ──────────────────────────────────────────


def test_list_and_remove(tmp_path):
    """list 仅返回未完成任务（completed < total）；remove 清理。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    # 未完成
    ckpt.save("t1", {"engine": "x", "total": 2, "completed_items": ["a"], "remaining": ["b"], "config": {}})
    # 已完成（不出现在 list 中）
    ckpt.save("t2", {"engine": "x", "total": 2, "completed_items": ["a", "b"], "remaining": [], "config": {}})

    unfinished = ckpt.list()
    ids = {d["task_id"] for d in unfinished}
    assert "t1" in ids
    assert "t2" not in ids  # completed == total

    assert ckpt.remove("t1") is True
    assert ckpt.remove("t1") is False  # 已删除
    assert ckpt.load("t1") is None


def test_list_skips_corrupted(tmp_path):
    """list 跳过损坏文件，不中断。"""
    from backend.checkpoint import TaskCheckpoint

    ckpt = TaskCheckpoint(tmp_path / "ckpts")
    ckpt._path("bad").write_text("garbage", encoding="utf-8")
    ckpt.save("good", {"engine": "x", "total": 2, "completed_items": [], "remaining": ["a"], "config": {}})
    unfinished = ckpt.list()
    ids = {d["task_id"] for d in unfinished}
    assert "good" in ids
    assert "bad" not in ids


# ── 恢复逻辑（fake 数据，不跑真实推理）─────────────────────


def test_resume_unfinished_tasks_fake_data(monkeypatch, isolated_settings):
    """恢复逻辑：pending/processing 任务重置为 pending 并重新入队；终态不动；清理残留 ckpt。"""
    import routers.queue_manager as qm
    from backend.database import get_db

    qm._checkpoint = None  # 重置懒加载缓存（指向临时目录）
    qm._completed_since_checkpoint = 0

    db = get_db()
    db.execute("INSERT INTO projects (id, name) VALUES ('proj_r', 't')")
    db.execute("INSERT INTO shots (id, project_id, ord) VALUES ('shot_p', 'proj_r', 0)")
    db.execute("INSERT INTO shots (id, project_id, ord) VALUES ('shot_x', 'proj_r', 1)")
    db.execute("INSERT INTO shots (id, project_id, ord) VALUES ('shot_d', 'proj_r', 2)")
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES ('task_p', 'shot_p', 'text', '{}', 'pending')"
    )
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES ('task_x', 'shot_x', 'text', '{}', 'processing')"
    )
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES ('task_d', 'shot_d', 'text', '{}', 'completed')"
    )
    db.commit()
    db.close()

    # 模拟中断前已写入的 checkpoint：task_p（未完成）+ task_d（终态残留，应被清理）
    ckpt = qm._get_checkpoint()
    ckpt.save("task_p", {"engine": "diffusers", "total": 1, "completed_items": [], "remaining": ["shot_p"], "config": {}})
    ckpt.save("task_d", {"engine": "diffusers", "total": 1, "completed_items": [], "remaining": ["shot_d"], "config": {}})

    # 桩化 enqueue，避免真实 worker 线程
    enqueued = []
    monkeypatch.setattr(qm, "enqueue", lambda tid: enqueued.append(tid))

    restored = qm.resume_unfinished_tasks()
    assert set(restored) == {"task_p", "task_x"}
    assert sorted(enqueued) == ["task_p", "task_x"]

    # 验证 DB 状态
    db2 = get_db()
    rows = db2.execute("SELECT id, status FROM generation_tasks ORDER BY id").fetchall()
    status = {r["id"]: r["status"] for r in rows}
    assert status["task_p"] == "pending"
    assert status["task_x"] == "pending"
    assert status["task_d"] == "completed"  # 终态不动

    shot_rows = db2.execute("SELECT id, status FROM shots ORDER BY id").fetchall()
    shot_status = {r["id"]: r["status"] for r in shot_rows}
    assert shot_status["shot_p"] == "queued"
    assert shot_status["shot_x"] == "queued"
    db2.close()

    # task_d 的残留 checkpoint 已被清理
    assert ckpt.load("task_d") is None


# ── _snapshot_unfinished / _on_task_completed ───────────────


def test_snapshot_unfinished_tasks(monkeypatch, isolated_settings):
    """_snapshot_unfinished 把 DB 中 pending/processing 任务写入 checkpoint。"""
    import routers.queue_manager as qm
    from backend.database import get_db

    qm._checkpoint = None
    qm._completed_since_checkpoint = 0

    db = get_db()
    db.execute("INSERT INTO projects (id, name) VALUES ('proj_s', 't')")
    db.execute("INSERT INTO shots (id, project_id, ord) VALUES ('shot_a', 'proj_s', 0)")
    db.execute("INSERT INTO shots (id, project_id, ord) VALUES ('shot_b', 'proj_s', 1)")
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES ('task_a', 'shot_a', 'text', '{\"prompt\":\"hello\"}', 'pending')"
    )
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES ('task_b', 'shot_b', 'text', '{}', 'processing')"
    )
    db.commit()
    db.close()

    qm._snapshot_unfinished()
    ckpt = qm._get_checkpoint()
    data_a = ckpt.load("task_a")
    data_b = ckpt.load("task_b")
    assert data_a is not None
    assert data_a["total"] == 1
    assert data_a["completed"] == 0
    assert data_a["remaining"] == ["shot_a"]
    assert data_a["config"]["prompt"] == "hello"
    assert data_b is not None
    assert data_b["remaining"] == ["shot_b"]
    assert ckpt.load("nope") is None


def test_on_task_completed_snapshot(monkeypatch, isolated_settings):
    """_on_task_completed 在达到 CHECKPOINT_EVERY 阈值时触发快照。"""
    import config as tcfg
    import routers.queue_manager as qm
    from backend.database import get_db

    monkeypatch.setattr(tcfg.settings, "CHECKPOINT_EVERY", 2)
    qm._checkpoint = None
    qm._completed_since_checkpoint = 0

    db = get_db()
    db.execute("INSERT INTO projects (id, name) VALUES ('proj_o', 't')")
    db.execute("INSERT INTO shots (id, project_id, ord) VALUES ('shot_c', 'proj_o', 0)")
    db.execute(
        "INSERT INTO generation_tasks (id, shot_id, mode, payload, status) VALUES ('task_c', 'shot_c', 'text', '{}', 'pending')"
    )
    db.commit()
    db.close()

    ckpt = qm._get_checkpoint()
    # 第 1 次完成 → 不触发
    qm._on_task_completed()
    assert ckpt.load("task_c") is None

    # 第 2 次完成 → 触发 snapshot
    qm._on_task_completed()
    data = ckpt.load("task_c")
    assert data is not None
    assert data["remaining"] == ["shot_c"]
    assert qm._completed_since_checkpoint == 0  # 计数器已重置
