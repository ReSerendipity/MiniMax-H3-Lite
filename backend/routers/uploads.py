"""
PRD §8: 参考素材上传 API
POST /api/upload  参考素材上传（返回 asset_id）
校验：格式、大小、上限（图≤9 / 视频≤3 / 音频≤3 / 混合≤12 / 音频须配图或视频）
"""
import sys
import json
import mimetypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database import get_db, new_id, row_to_dict
from config import settings

router = APIRouter()

ALLOWED_MIME = {
    "image": {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"},
    "video": {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"},
    "audio": {"audio/wav", "audio/mpeg", "audio/x-wav", "audio/mp3"},
}

EXT_BY_TYPE = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"},
    "video": {".mp4", ".mov", ".avi", ".mkv"},
    "audio": {".wav", ".mp3"},
}


def detect_kind(filename: str, mime: str) -> str | None:
    ext = Path(filename).suffix.lower()
    for kind, mimes in ALLOWED_MIME.items():
        if mime in mimes or ext in EXT_BY_TYPE[kind]:
            return kind
    return None


@router.post("/upload")
async def upload_ref(
    file: UploadFile = File(...),
    shot_id: str = Form(default=""),
):
    # 1. 格式校验
    kind = detect_kind(file.filename or "", file.content_type or "")
    if not kind:
        raise HTTPException(422, f"不支持的文件格式: {file.filename}")

    # 2. 大小校验
    data = await file.read()
    size = len(data)
    if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"文件过大，上限 {settings.MAX_UPLOAD_SIZE_MB}MB")

    # 3. 如果绑定了 shot，做上限校验
    if shot_id:
        db = get_db()
        existing = db.execute(
            "SELECT ref_type, COUNT(*) as cnt FROM shot_refs WHERE shot_id=? GROUP BY ref_type",
            (shot_id,),
        ).fetchall()
        counts = {r["ref_type"]: r["cnt"] for r in existing}
        total = sum(counts.values())

        kind_label = {"image": "图片", "video": "视频", "audio": "音频"}[kind]
        max_map = {
            "image": settings.MAX_IMAGE_COUNT,
            "video": settings.MAX_VIDEO_COUNT,
            "audio": settings.MAX_AUDIO_COUNT,
        }
        if counts.get(kind, 0) >= max_map[kind]:
            db.close()
            raise HTTPException(422, f"{kind_label}数量超限，上限 {max_map[kind]} 个")
        if total >= settings.MAX_TOTAL_REFS:
            db.close()
            raise HTTPException(422, f"参考素材总数超限，上限 {settings.MAX_TOTAL_REFS} 个")
        # 音频须配图或视频
        if kind == "audio":
            if counts.get("image", 0) == 0 and counts.get("video", 0) == 0:
                db.close()
                raise HTTPException(422, "音频须搭配图像或视频输入")
        db.close()

    # 4. 落盘
    aid = new_id("ast_")
    ext = Path(file.filename or "").suffix.lower() or ".bin"
    stored_name = f"{aid}{ext}"
    dest = settings.UPLOADS_DIR / stored_name
    dest.write_bytes(data)

    # 5. 写资产记录
    db = get_db()
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
        (aid, kind, f"uploads/{stored_name}", mime, size, json.dumps({"original_name": file.filename})),
    )
    # 6. 绑定到 shot
    if shot_id:
        # ord = 当前最大 ord + 1
        max_ord = db.execute(
            "SELECT COALESCE(MAX(ord), -1) FROM shot_refs WHERE shot_id=?", (shot_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO shot_refs (shot_id, asset_id, ref_type, ord) VALUES (?, ?, ?, ?)",
            (shot_id, aid, kind, max_ord + 1),
        )
    db.commit()
    row = db.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    db.close()
    result = row_to_dict(row)
    result["kind"] = kind
    return result
