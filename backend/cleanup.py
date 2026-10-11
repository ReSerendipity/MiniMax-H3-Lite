"""结果资产配额清理（AI/ML 评估 P2 · 产物只增不减治理）。

背景：result 资产（生成成片 + 缩略图 + DB 行）随任务成功只增不减，
无清理策略时磁盘无限增长。本模块提供按保留数量上限的裁剪：
  * 仅作用于 kind='result' 的资产（绝不触碰用户上传的参考素材 image/video/audio）；
  * 按 created_at 保留最近 N 个，超出部分解除 shots/generation_tasks 引用后
    删除文件（含缩略图）与 DB 行；
  * 由 backend.main.startup 调用（尽力而为，失败仅 warning，不阻塞启动）。

配额语义是「裁剪历史成片」的产品取舍：默认保留最近 200 个结果资产，
可通过 MMH3_MAX_RESULT_ASSETS 覆盖。被引用的旧成片会被解除引用后删除
（历史库回看会失去最老成片）——这是磁盘治理的有意取舍，写入本 docstring
与 .env.example 说明。
"""
import json
import logging
from pathlib import Path

from database import get_db

logger = logging.getLogger(__name__)


def _resolve_thumbnail(meta_raw: object) -> str | None:
    """从 assets.meta JSON 解析缩略图相对路径；解析失败返回 None（不阻断清理）。"""
    try:
        if isinstance(meta_raw, str):
            meta = json.loads(meta_raw)
        elif isinstance(meta_raw, dict):
            meta = meta_raw
        else:
            meta = {}
        return meta.get("thumbnail")
    except (json.JSONDecodeError, TypeError):
        return None


def enforce_result_quota(max_assets: int, assets_dir: Path) -> int:
    """按 created_at 保留最近 max_assets 个 result 资产，超出裁剪。

    Returns: 清理的资产数量（文件删除 + DB 行删除）。
    """
    if max_assets <= 0:
        logger.warning("[cleanup] MAX_RESULT_ASSETS=%d 非法，跳过清理", max_assets)
        return 0

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, path, meta, created_at FROM assets WHERE kind='result' "
            "ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
        if len(rows) <= max_assets:
            return 0

        removed = 0
        for r in rows[: len(rows) - max_assets]:
            aid = r["id"]
            # 解除引用（任务与镜头的历史回填，避免悬空 result_asset_id）
            db.execute(
                "UPDATE generation_tasks SET result_asset_id=NULL WHERE result_asset_id=?", (aid,)
            )
            db.execute(
                "UPDATE shots SET result_asset_id=NULL WHERE result_asset_id=?", (aid,)
            )
            # 删除缩略图（若 meta 记录；仅取文件名防路径穿越）
            thumb = _resolve_thumbnail(r["meta"])
            if thumb:
                thumb_path = assets_dir / Path(thumb).name
                try:
                    thumb_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("[cleanup] 缩略图删除失败（已忽略）: %s", thumb_path)
            # 删除产物文件（path 形如 assets/xxx.mp4；仅取文件名防路径穿越）
            asset_path = assets_dir / Path(r["path"]).name
            try:
                asset_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("[cleanup] 产物文件删除失败（已忽略）: %s", asset_path)
            db.execute("DELETE FROM assets WHERE id=?", (aid,))
            removed += 1
        db.commit()
        return removed
    finally:
        db.close()
