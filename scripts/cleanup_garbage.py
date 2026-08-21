"""清理 uploads 与 assets 中 4 字节空文件 + 测试项目数据。"""
import sqlite3
import os
import sys
from pathlib import Path

BASE = Path(r"C:\Users\Doro\MiniMax-H3-lite")
DB = BASE / "data" / "mmh3.db"
UPLOADS = BASE / "uploads"
ASSETS = BASE / "assets"

if not DB.exists():
    print(f"DB not found: {DB}")
    sys.exit(0)

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

# 显示当前状态
print("=" * 60)
print("清理前：")
proj_rows = conn.execute("SELECT id, name FROM projects").fetchall()
print(f"  项目数: {len(proj_rows)}")
for r in proj_rows:
    print(f"    - {r['id']}: {r['name']}")

# 删除所有项目（级联删除 shots / refs / history / generation_tasks / assets）
print("\n删除所有项目（含级联）...")
conn.execute("DELETE FROM projects")
conn.execute("DELETE FROM generation_tasks")
conn.execute("DELETE FROM assets")
conn.execute("DELETE FROM shot_refs")
conn.execute("DELETE FROM shots")
conn.commit()

# 清理空文件（≤6 字节：占位空 PNG 等）
def clean_dir(d: Path):
    if not d.exists():
        return
    removed = 0
    for p in d.iterdir():
        if p.is_file() and p.stat().st_size <= 8:
            try:
                p.unlink()
                removed += 1
            except Exception as e:
                print(f"  ! {p.name}: {e}")
    return removed

n1 = clean_dir(UPLOADS)
n2 = clean_dir(ASSETS)
print(f"\n清理 uploads: 删 {n1} 个空文件")
print(f"清理 assets:  删 {n2} 个空文件")

# 重新计
print("\n清理后：")
proj_rows = conn.execute("SELECT id, name FROM projects").fetchall()
print(f"  项目数: {len(proj_rows)}")
asset_count = conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"]
print(f"  资产数: {asset_count}")
task_count = conn.execute("SELECT COUNT(*) AS c FROM generation_tasks").fetchone()["c"]
print(f"  任务数: {task_count}")
conn.close()
print("=" * 60)
