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

    # 模式 × 参考素材校验（PRD §6.1 / §8）
    mode = body.mode
    if mode in ("first_frame", "last_frame", "first_last") and not body.ref_ids:
        db.close()
        raise HTTPException(422, f"模式「{mode}」需要提供对应图片参考素材")
    if mode == "first_last" and len(body.ref_ids) < 2:
        db.close()
        raise HTTPException(422, "首尾帧模式需要至少 2 张图片（首帧 + 末帧）")
    if mode == "ref" and not body.ref_ids:
        db.close()
        raise HTTPException(422, "多模态参考模式需要提供参考素材")

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

    # 异步入队（queue_manager 真实 Worker：pending → processing → completed/failed）
    from routers.queue_manager import enqueue
    try:
        enqueue(tid)
    except Exception as e:
        # 入队失败 → 任务如实标记失败，绝不静默
        db = get_db()
        db.execute(
            "UPDATE generation_tasks SET status='failed', error=? WHERE id=?",
            (f"入队失败: {type(e).__name__}: {e}", tid),
        )
        db.commit()
        db.close()
        raise HTTPException(500, f"任务入队失败: {e}")

    return row_to_dict(row)


@router.get("/generations/{tid}")
def get_generation(tid: str):
    db = get_db()
    row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "任务不存在")
    data = row_to_dict(row)
    # 附带结果文件路径（assets.path = assets/xxx.mp4），供前端直接回填舞台
    if data.get("result_asset_id"):
        a = db.execute(
            "SELECT path FROM assets WHERE id=?", (data["result_asset_id"],)
        ).fetchone()
        data["result_path"] = a["path"] if a else None
    db.close()
    return data
