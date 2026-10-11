"""
PRD §8: 生成任务 API
POST   /api/generations           提交生成任务
GET    /api/generations/{task_id} 查询任务状态
"""
import sys
import json
import secrets
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

    # 时长校验（官方模型支持 0~15s，UI 从 DURATION_MIN 起；整秒档位）
    duration = body.params.get("duration", shot["duration"])
    if duration not in settings.SUPPORTED_DURATIONS:
        db.close()
        raise HTTPException(
            422,
            f"时长不合法，可选 {settings.SUPPORTED_DURATION_MIN}–{settings.SUPPORTED_DURATION_MAX} 秒（整秒）",
        )

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

    # aspect / resolution 白名单校验（后端服务设计评估 P1-5）：替代静默回退——
    # 原先非法比例经 h3.spec.RATIOS.get 兜底为 16:9、非法档位经 inference 静默归一，
    # 现于 API 边界拒绝（422），杜绝「参数非法但成功返回错误画幅/档位」。
    aspect = body.params.get("aspect")
    if aspect is not None and aspect not in settings.SUPPORTED_RATIOS:
        db.close()
        raise HTTPException(
            422,
            f"不支持的画面比例: {aspect}（支持: {'/'.join(sorted(settings.SUPPORTED_RATIOS))}）",
        )
    resolution = body.params.get("resolution")
    if resolution is not None and resolution not in settings.RESOLUTION_PRESETS:
        # 兼容旧载荷别名：768P/2K 为历史前端遗留值，显式放行（inference 归一为 0.98/0.75）
        if resolution not in ("768P", "2K"):
            db.close()
            raise HTTPException(
                422,
                f"不支持的清晰度档位: {resolution}"
                f"（支持: {'/'.join(sorted(settings.RESOLUTION_PRESETS))} 及旧别名 768P/2K）",
            )

    # seed 血缘（可复现性，MLOps 评估 P1）：提交时确定 seed 并写入 payload 落库。
    # 未指定 → 服务端生成随机 seed；显式指定 → 校验范围（uint32）后原样采用。
    # 重试 / 断点续跑 / 同参数重放均复用同一 seed，「同参数 + 同 seed」⇒ 结果可复现。
    seed = body.params.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            db.close()
            raise HTTPException(422, "seed 必须是整数")
        if not (0 <= seed < 2**32):
            db.close()
            raise HTTPException(422, f"seed 超出有效范围（0 ~ {2**32 - 1}）")
    else:
        seed = secrets.randbits(32)
    body.params["seed"] = seed

    # 幂等去重（后端服务设计评估 P0-1）：同一镜头已存在活跃任务
    # （pending/processing）时直接返回既有任务，不重复建任务——
    # 重复点击提交 / 重放请求不会产生重复推理与重复资产。
    active = db.execute(
        "SELECT id FROM generation_tasks WHERE shot_id=? AND status IN ('pending','processing')"
        " ORDER BY created_at LIMIT 1",
        (body.shot_id,),
    ).fetchone()
    if active:
        row = db.execute("SELECT * FROM generation_tasks WHERE id=?", (active["id"],)).fetchone()
        db.close()
        return row_to_dict(row)

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
