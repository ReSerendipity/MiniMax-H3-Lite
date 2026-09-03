"""清理 uploads 与 assets 中 4 字节空文件 + 测试项目数据 +（可选）容器。

用法：
    python scripts/cleanup_garbage.py                  # 仅清库 + 空文件
    python scripts/cleanup_garbage.py --container      # 同时停掉并删除 mmh3-workbench 容器
    python scripts/cleanup_garbage.py --container -y   # 跳过确认（CI/脚本场景）

注意：--container 不会删除 volume（./data ./uploads ./outputs 是 bind-mount，挂载源
      在宿主机，本脚本不会动它们）；若要彻底重置，先 `docker compose down -v`。
"""
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE = Path(r"C:\Users\Doro\MiniMax-H3-lite")
DB = BASE / "data" / "mmh3.db"
UPLOADS = BASE / "uploads"
ASSETS = BASE / "assets"
CONTAINER_NAME = "mmh3-workbench"


def parse_args() -> dict:
    """极简 CLI 解析（避免引入 argparse，让脚本风格与项目其它 .py 保持一致）。"""
    return {
        "container": "--container" in sys.argv,
        "yes": any(a in ("-y", "--yes") for a in sys.argv),
    }


def clean_container(yes: bool) -> None:
    """检测 docker + mmh3-workbench 容器，必要时停掉并删除。"""
    if not shutil.which("docker"):
        print("\n[容器清理] docker 命令不在 PATH，跳过（本机未装 Docker Desktop）")
        return
    # 检查容器是否存在（任意状态）
    r = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={CONTAINER_NAME}",
         "--format", "{{.Names}}\t{{.State}}"],
        capture_output=True, text=True, check=False,
    )
    if CONTAINER_NAME not in r.stdout:
        print(f"\n[容器清理] {CONTAINER_NAME} 容器不存在，跳过")
        return
    print(f"\n[容器清理] 发现 {CONTAINER_NAME}：")
    print(r.stdout.rstrip())
    if not yes:
        try:
            resp = input(f"  停掉并删除 {CONTAINER_NAME} 容器? [y/N] ")
        except EOFError:
            resp = "n"
        if resp.strip().lower() != "y":
            print("  跳过容器清理（确认输入非 y）")
            return
    # 优雅 stop（10s 超时）然后 rm
    print(f"  docker stop {CONTAINER_NAME} ...")
    subprocess.run(["docker", "stop", CONTAINER_NAME], check=False)
    print(f"  docker rm {CONTAINER_NAME} ...")
    subprocess.run(["docker", "rm", CONTAINER_NAME], check=False)
    print(f"  [OK] {CONTAINER_NAME} 已停掉并删除")
    print("  提示：volume（./data ./uploads ./outputs）未动；如需彻底重置：")
    print("        docker compose down -v      # 删容器 + 删命名卷（bind-mount 不受影响）")


# === 主体流程 ===
args = parse_args()

if not DB.exists():
    print(f"DB not found: {DB}")
    # 即使没 DB，用户可能就想清容器
    if args.container:
        clean_container(args.yes)
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

# 容器清理（仅在显式 --container 时执行）
if args["container"]:
    clean_container(args["yes"])
