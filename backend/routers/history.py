"""
PRD §8: 历史库 API
GET /api/projects/{pid}/history  项目历史（已完成镜头/结果）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter
from database import get_db, rows_to_dicts

router = APIRouter()


@router.get("/projects/{pid}/history")
def project_history(pid: str):
    db = get_db()
    rows = db.execute(
        """SELECT t.id, t.shot_id, t.mode, t.status, t.progress, t.error,
                  t.result_asset_id, t.created_at, t.finished_at,
                  s.name AS shot_name, s.prompt, s.duration, s.aspect,
                  a.path AS result_path, a.mime AS result_mime
           FROM generation_tasks t
           JOIN shots s ON s.id = t.shot_id
           LEFT JOIN assets a ON a.id = t.result_asset_id
           WHERE s.project_id = ?
           ORDER BY t.created_at DESC""",
        (pid,),
    ).fetchall()
    db.close()
    return rows_to_dicts(rows)
