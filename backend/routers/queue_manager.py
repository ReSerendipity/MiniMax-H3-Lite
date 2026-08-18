"""
MM·H3 工作台 — 任务队列管理器
PRD §4.2: 单机串行/受限并发执行，状态机 pending → processing → completed/failed
超时与重试，失败原因记录
"""
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_db, now_iso
from config import settings

# ── 队列状态 ──────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# ── 内部队列 ──────────────────────────────────────
_queue: list[str] = []
_lock = threading.Lock()
_worker_started = False


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
    """执行单个任务：状态流转 + 超时 + 重试"""
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
                return
