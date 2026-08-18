"""
MM·H3 工作台 — 任务队列管理器
PRD §4.2: 单机串行/受限并发执行，状态机 pending → processing → completed/failed
超时与重试，失败原因记录

路线图 #7: 接入 checkpoint 断点续跑（模式移植自 TTS_MultiModel TaskCheckpoint）。
- _run_task 开始处理时写 checkpoint；成功/终态失败时删除。
- 每完成 CHECKPOINT_EVERY 个镜头，快照所有未完成任务到 checkpoint。
- resume_unfinished_tasks 在启动时扫描 pending/processing 残留任务并重新入队。
"""
import sys
import json
import logging
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_db, now_iso
from config import settings
from checkpoint import TaskCheckpoint

logger = logging.getLogger(__name__)

# ── 队列状态 ──────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# ── 内部队列 ──────────────────────────────────────
_queue: list[str] = []
_lock = threading.Lock()
_worker_started = False

# ── 断点续跑（checkpoint #7）─────────────────────
_checkpoint: TaskCheckpoint | None = None
_ckpt_lock = threading.Lock()
_completed_since_checkpoint = 0


def _get_checkpoint() -> TaskCheckpoint:
    """懒加载 TaskCheckpoint 单例（避免导入期创建目录）。"""
    global _checkpoint
    if _checkpoint is None:
        _checkpoint = TaskCheckpoint(settings.CHECKPOINT_DIR)
    return _checkpoint


def _snapshot_unfinished() -> None:
    """把当前所有未完成任务（pending/processing）写入 checkpoint 快照。"""
    ckpt = _get_checkpoint()
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, shot_id, payload FROM generation_tasks WHERE status IN (?, ?)",
            (STATUS_PENDING, STATUS_PROCESSING),
        ).fetchall()
        for r in rows:
            try:
                cfg = json.loads(r["payload"]) if isinstance(r["payload"], str) else (r["payload"] or {})
            except (json.JSONDecodeError, TypeError):
                cfg = {}
            ckpt.save(
                r["id"],
                {
                    "engine": settings.INFERENCE_BACKEND,
                    "total": 1,
                    "completed_items": [],
                    "remaining": [r["shot_id"]],
                    "config": cfg,
                },
            )
    finally:
        db.close()


def _on_task_completed() -> None:
    """每完成 CHECKPOINT_EVERY 个镜头，把未完成任务快照到 checkpoint。"""
    global _completed_since_checkpoint
    with _ckpt_lock:
        _completed_since_checkpoint += 1
        if not _get_checkpoint().should_checkpoint(_completed_since_checkpoint, settings.CHECKPOINT_EVERY):
            return
        _completed_since_checkpoint = 0
    _snapshot_unfinished()


def resume_unfinished_tasks() -> list[str]:
    """启动时扫描未完成任务并恢复续跑。

    扫描 ``generation_tasks`` 中 status 为 pending/processing 的任务，
    重置为 pending 并重新入队；同时清理终态任务残留的 checkpoint 文件。

    Returns:
        被恢复（重新入队）的任务 ID 列表。
    """
    ckpt = _get_checkpoint()
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, shot_id FROM generation_tasks WHERE status IN (?, ?)",
            (STATUS_PENDING, STATUS_PROCESSING),
        ).fetchall()
        restored: list[str] = []
        for r in rows:
            tid = r["id"]
            db.execute(
                "UPDATE generation_tasks SET status=?, error=NULL WHERE id=?",
                (STATUS_PENDING, tid),
            )
            db.execute(
                "UPDATE shots SET status='queued' WHERE id=?", (r["shot_id"],),
            )
            restored.append(tid)
        db.commit()

        # 清理终态任务残留的 checkpoint 文件（任务已完成/失败，无需恢复）
        terminal_ids = {
            r["id"]
            for r in db.execute(
                "SELECT id FROM generation_tasks WHERE status IN (?, ?)",
                (STATUS_COMPLETED, STATUS_FAILED),
            ).fetchall()
        }
        for data in list(ckpt.list()):
            tid = data.get("task_id", "")
            if tid and tid in terminal_ids:
                ckpt.remove(tid)
    finally:
        db.close()

    for tid in restored:
        enqueue(tid)
    return restored


def enqueue(task_id: str):
    """将任务 ID 入队，启动 Worker 线程（懒启动）"""
    with _lock:
        _queue.append(task_id)
        global _worker_started
        if not _worker_started:
            _worker_started = True
            t = threading.Thread(target=_worker_loop, daemon=True)
            t.start()


def _worker_loop():
    """主 Worker 循环：从队列取任务，受限并发执行"""
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENCY)

    while True:
        tid = None
        with _lock:
            if _queue:
                tid = _queue.pop(0)
        if tid is None:
            time.sleep(0.3)
            continue
        pool.submit(_run_task, tid)


def _run_task(task_id: str):
    """执行单个任务：状态流转 + 超时 + 重试 + checkpoint"""
    db = get_db()
    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        db.close()
        return

    retry_count = 0
    while retry_count <= settings.TASK_RETRY_MAX:
        # 标记 processing
        db.execute(
            "UPDATE generation_tasks SET status=?, progress=0, error=NULL WHERE id=?",
            (STATUS_PROCESSING, task_id),
        )
        db.execute("UPDATE shots SET status='processing' WHERE id=?", (row["shot_id"],))
        db.commit()

        # 断点续跑：任务开始处理时写 checkpoint（进程中断后可由 startup 恢复）
        payload_cfg = row["payload"] or {}
        if isinstance(payload_cfg, str):
            try:
                payload_cfg = json.loads(payload_cfg)
            except (json.JSONDecodeError, TypeError):
                payload_cfg = {}
        _get_checkpoint().save(
            task_id,
            {
                "engine": settings.INFERENCE_BACKEND,
                "total": 1,
                "completed_items": [],
                "remaining": [row["shot_id"]],
                "config": payload_cfg,
            },
        )

        try:
            # 调用推理
            from routers.inference import run_inference
            result = run_inference(task_id)

            # 成功 → 更新状态
            db.execute(
                "UPDATE generation_tasks SET status=?, progress=100, result_asset_id=?, finished_at=? WHERE id=?",
                (STATUS_COMPLETED, result["asset_id"], now_iso(), task_id),
            )
            db.execute(
                "UPDATE shots SET status='completed', result_asset_id=? WHERE id=?",
                (result["asset_id"], row["shot_id"]),
            )
            db.commit()
            db.close()

            # 断点续跑：任务完成 → 删除 checkpoint，并按 CHECKPOINT_EVERY 快照未完成任务
            _get_checkpoint().remove(task_id)
            _on_task_completed()
            return

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            retry_count += 1
            if retry_count <= settings.TASK_RETRY_MAX:
                db.execute(
                    "UPDATE generation_tasks SET error=? WHERE id=?",
                    (f"重试 {retry_count}/{settings.TASK_RETRY_MAX}: {err_msg}", task_id),
                )
                db.commit()
                time.sleep(1)
            else:
                # 最终失败
                db.execute(
                    "UPDATE generation_tasks SET status=?, error=?, finished_at=? WHERE id=?",
                    (STATUS_FAILED, err_msg, now_iso(), task_id),
                )
                db.execute("UPDATE shots SET status='failed' WHERE id=?", (row["shot_id"],))
                db.commit()
                db.close()
                # 断点续跑：终态失败 → 删除 checkpoint（不会恢复重跑）
                _get_checkpoint().remove(task_id)
                return
