"""
PRD §8: 生成任务 API
POST   /api/generations           提交生成任务
GET    /api/generations/{task_id} 查询任务状态
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db, new_id, row_to_dict
from config import settings

router = APIRouter()


class GenRequest(BaseModel):
    shot_id: str
    mode: str = "text"
    prompt: str = ""
    params: dict = {}
    ref_ids: list[str] = []


@router.post("/generations")
def submit_generation(body: GenRequest):
    db = get_db()
    # 验证镜头存在
    shot = db.execute("SELECT * FROM shots WHERE id=?", (body.shot_id,)).fetchone()
    if not shot:
        db.close()
        raise HTTPException(404, "镜头不存在")

    # 提示词校验
    if len(body.prompt) > settings.MAX_PROMPT_CHARS:
        db.close()
        raise HTTPException(422, f"提示词超限，上限 {settings.MAX_PROMPT_CHARS} 字符")

    # 时长校验
    duration = body.params.get("duration", shot["duration"])
    if duration not in settings.SUPPORTED_DURATIONS:
        db.close()
        raise HTTPException(422, f"时长不合法，可选 {settings.SUPPORTED_DURATIONS}")

    # 创建任务
    tid = new_id("task_")
    payload = json.dumps(
        {"prompt": body.prompt, "params": body.params, "ref_ids": body.ref_ids},
        ensure_ascii=False,
    )
    db.execute(
        """INSERT INTO generation_tasks (id, shot_id, mode, payload, status)
           VALUES (?, ?, ?, ?, 'pending')""",
        (tid, body.shot_id, body.mode, payload),
    )
    # 更新镜头状态
    db.execute("UPDATE shots SET status='queued' WHERE id=?", (body.shot_id,))
    db.commit()
    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (tid,)).fetchone()
    db.close()

    # 异步入队（阶段 C 实现 Worker，这里先返回 pending）
    # worker.enqueue(tid)  — 阶段 C 接入
    try:
        from routers.queue_manager import enqueue
        enqueue(tid)
    except ImportError:
        pass  # 阶段 C 尚未实现

    return row_to_dict(row)


@router.get("/generations/{tid}")
def get_generation(tid: str):
    db = get_db()
    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (tid,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "任务不存在")
    return row_to_dict(row)
