"""PRD §8: 参考素材上传 API（后端服务设计评估 P1-1 收口后：路由只留参数绑定）

POST /api/upload  参考素材上传（返回 asset_id）
校验/落盘逻辑见 services/upload_service.py（格式/数量/时长/配对校验与流式写入）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, File, Form, UploadFile

from services.upload_service import store_upload

router = APIRouter()


@router.post("/upload")
def upload_ref(
    file: UploadFile = File(...),
    shot_id: str = Form(default=""),
    paired_with: str = Form(default=""),
):
    return store_upload(file=file, shot_id=shot_id, paired_with=paired_with)
