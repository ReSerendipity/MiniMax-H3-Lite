"""PRD §8: 生成任务 API（后端服务设计评估 P1-1 收口后：路由只留参数绑定与响应）

POST   /api/generations           提交生成任务（业务逻辑见 services/generation_service.py）
GET    /api/generations/{task_id} 查询任务状态
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException, Request

from database import get_db, row_to_dict
from services.generation_service import GenRequest, submit_generation

router = APIRouter()


@router.post("/generations")
def submit_generation_route(request: Request, body: GenRequest):
    # request_id 由 main.request_trace_middleware 注入（P1-2：随任务落库贯通）
    return submit_generation(request_id=getattr(request.state, "request_id", ""), body=body)


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
