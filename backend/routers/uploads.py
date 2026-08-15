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

import subprocess
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database import get_db, new_id, row_to_dict
from config import settings

# ── 片段时长限制（官方规格：每段 2–15s，同类合计 ≤15s）──
MIN_SEGMENT_DURATION = 2.0
MAX_SEGMENT_DURATION = 15.0
MAX_TOTAL_KIND_DURATION = 15.0

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


def _probe_duration(path: Path) -> float | None:
    """ffprobe 探测时长；不可用/失败返回 None（由调用方决定策略）。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _existing_kind_duration(shot_id: str, kind: str) -> float:
    """查询 shot 下同 kind 资产的已有时长合计（从 assets.meta.duration 读取）。"""
    db = get_db()
    rows = db.execute(
        """SELECT a.meta FROM shot_refs r JOIN assets a ON a.id=r.asset_id
           WHERE r.shot_id=? AND r.ref_type=?""",
        (shot_id, kind),
    ).fetchall()
    db.close()
    total = 0.0
    for r in rows:
        try:
            import json as _json
            meta = _json.loads(r["meta"] or "{}")
            d = meta.get("duration")
            if d and isinstance(d, (int, float)):
                total += float(d)
        except Exception:
            pass
    return total


@router.post("/upload")
async def upload_ref(
    file: UploadFile = File(...),
    shot_id: str = Form(default=""),
    paired_with: str = Form(default=""),
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

    # 4.5 时长校验（video/audio 探测 + 同类合计 ≤15s）
    meta_info = {"original_name": file.filename}
    if kind in ("video", "audio"):
        dur = _probe_duration(dest)
        meta_info["duration"] = dur
        if dur is not None:
            kind_label = {"image": "图片", "video": "视频", "audio": "音频"}[kind]
            if dur < MIN_SEGMENT_DURATION or dur > MAX_SEGMENT_DURATION:
                dest.unlink(missing_ok=True)
                raise HTTPException(422, f"{kind_label}时长需在 {MIN_SEGMENT_DURATION:.0f}–{MAX_SEGMENT_DURATION:.0f} 秒内，当前 {dur:.1f}s")
            if shot_id:
                total = dur + _existing_kind_duration(shot_id, kind)
                if total > MAX_TOTAL_KIND_DURATION:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(422, f"{kind_label}合计时长超限（≤{MAX_TOTAL_KIND_DURATION:.0f}s），当前合计 {total:.1f}s")
        # 探测失败时放行，meta 中 duration=null，前端显示「时长未知」

    # G7: 记录图像尺寸（用于「跟随首帧图像尺寸」模式）
    if kind == "image":
        try:
            from PIL import Image
            with Image.open(dest) as im:
                meta_info["width"], meta_info["height"] = im.size
        except Exception:
            pass

    # 5. 写资产记录
    db = get_db()
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    db.execute(
        "INSERT INTO assets (id, kind, path, mime, size, meta) VALUES (?, ?, ?, ?, ?, ?)",
        (aid, kind, f"uploads/{stored_name}", mime, size, json.dumps(meta_info, ensure_ascii=False)),
    )
    # 6. 绑定到 shot
    if shot_id:
        # 校验配对关系：仅 audio 允许配对，paired_with 须指向同 shot 下已存在的 video 资产
        pair_asset_id = None
        if paired_with and kind == "audio":
            pair_row = db.execute(
                "SELECT a.kind FROM shot_refs r JOIN assets a ON a.id=r.asset_id WHERE r.shot_id=? AND r.asset_id=?",
                (shot_id, paired_with),
            ).fetchone()
            if not pair_row:
                db.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(422, "配对目标资产不存在或不属于当前镜头")
            if pair_row["kind"] != "video":
                db.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(422, "配对目标须为视频资产")
            pair_asset_id = paired_with
        # ord = 当前最大 ord + 1
        max_ord = db.execute(
            "SELECT COALESCE(MAX(ord), -1) FROM shot_refs WHERE shot_id=?", (shot_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO shot_refs (shot_id, asset_id, ref_type, ord, pair_asset_id) VALUES (?, ?, ?, ?, ?)",
            (shot_id, aid, kind, max_ord + 1, pair_asset_id),
        )
    db.commit()
    row = db.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    db.close()
    result = row_to_dict(row)
    result["kind"] = kind
    return result
