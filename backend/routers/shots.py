"""
PRD §8: 镜头 CRUD API
GET    /api/projects/{pid}/shots   镜头列表
POST   /api/projects/{pid}/shots   新增镜头
PUT    /api/shots/{sid}            更新镜头（提示词/参数/顺序）
DELETE /api/shots/{sid}            删除镜头
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db, new_id, row_to_dict, rows_to_dicts, now_iso

router = APIRouter()


class ShotCreate(BaseModel):
    name: str = "新镜头"
    prompt: str = ""
    mode: str = "text"
    duration: int = 8
    aspect: str = "16:9"
    params: dict = {}


class ShotUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
    mode: str | None = None
    duration: int | None = None
    aspect: str | None = None
    params: dict | None = None
    ord: int | None = None


@router.get("/projects/{pid}/shots")
def list_shots(pid: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM shots WHERE project_id=? ORDER BY ord", (pid,)
    ).fetchall()
    db.close()
    return rows_to_dicts(rows)


@router.post("/projects/{pid}/shots")
def create_shot(pid: str, body: ShotCreate):
    db = get_db()
    # 验证项目存在
    proj = db.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone()
    if not proj:
        db.close()
        raise HTTPException(404, "项目不存在")
    # 自动 ord = 当前最大 ord + 1
    max_ord = db.execute(
        "SELECT COALESCE(MAX(ord), -1) FROM shots WHERE project_id=?", (pid,)
    ).fetchone()[0]
    sid = new_id("shot_")
    db.execute(
        """INSERT INTO shots (id, project_id, ord, name, prompt, mode, params, duration, aspect)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sid, pid, max_ord + 1, body.name, body.prompt, body.mode,
         json.dumps(body.params, ensure_ascii=False), body.duration, body.aspect),
    )
    db.execute("UPDATE projects SET updated_at=? WHERE id=?", (now_iso(), pid))
    db.commit()
    row = db.execute("SELECT * FROM shots WHERE id=?", (sid,)).fetchone()
    db.close()
    return row_to_dict(row)


@router.put("/shots/{sid}")
def update_shot(sid: str, body: ShotUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM shots WHERE id=?", (sid,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "镜头不存在")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.prompt is not None:
        updates["prompt"] = body.prompt
    if body.mode is not None:
        updates["mode"] = body.mode
    if body.duration is not None:
        updates["duration"] = body.duration
    if body.aspect is not None:
        updates["aspect"] = body.aspect
    if body.params is not None:
        updates["params"] = json.dumps(body.params, ensure_ascii=False)
    if body.ord is not None:
        updates["ord"] = body.ord
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [sid]
    db.execute(f"UPDATE shots SET {set_clause} WHERE id=?", values)
    # 同步项目 updated_at
    db.execute(
        "UPDATE projects SET updated_at=? WHERE id=(SELECT project_id FROM shots WHERE id=?)",
        (now_iso(), sid),
    )
    db.commit()
    row = db.execute("SELECT * FROM shots WHERE id=?", (sid,)).fetchone()
    db.close()
    return row_to_dict(row)


@router.delete("/shots/{sid}")
def delete_shot(sid: str):
    db = get_db()
    cur = db.execute("DELETE FROM shots WHERE id=?", (sid,))
    db.commit()
    db.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "镜头不存在")
    return {"deleted": sid}
