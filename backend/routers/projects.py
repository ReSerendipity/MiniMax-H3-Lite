"""
PRD §8: 项目 CRUD API
POST   /api/projects           新建项目
GET    /api/projects           项目列表
GET    /api/projects/{id}      项目详情（含镜头）
PUT    /api/projects/{id}      重命名
DELETE /api/projects/{id}      删除项目（级联镜头/历史）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db, new_id, row_to_dict, rows_to_dicts, now_iso

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str = "未命名项目"


class ProjectUpdate(BaseModel):
    name: str


@router.post("/projects")
def create_project(body: ProjectCreate):
    db = get_db()
    pid = new_id("proj_")
    db.execute(
        "INSERT INTO projects (id, name) VALUES (?, ?)",
        (pid, body.name),
    )
    db.commit()
    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    return row_to_dict(row)


@router.get("/projects")
def list_projects():
    db = get_db()
    rows = db.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM shots WHERE project_id=p.id) AS shot_count "
        "FROM projects p ORDER BY p.updated_at DESC"
    ).fetchall()
    db.close()
    return rows_to_dicts(rows)


@router.get("/projects/{pid}")
def get_project(pid: str):
    db = get_db()
    proj = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not proj:
        db.close()
        raise HTTPException(404, "项目不存在")
    shots = db.execute(
        "SELECT * FROM shots WHERE project_id=? ORDER BY ord", (pid,)
    ).fetchall()
    db.close()
    result = row_to_dict(proj)
    result["shots"] = rows_to_dicts(shots)
    return result


@router.put("/projects/{pid}")
def update_project(pid: str, body: ProjectUpdate):
    db = get_db()
    cur = db.execute(
        "UPDATE projects SET name=?, updated_at=? WHERE id=?",
        (body.name, now_iso(), pid),
    )
    db.commit()
    if cur.rowcount == 0:
        db.close()
        raise HTTPException(404, "项目不存在")
    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    return row_to_dict(row)


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    db = get_db()
    cur = db.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.commit()
    db.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "项目不存在")
    return {"deleted": pid}
