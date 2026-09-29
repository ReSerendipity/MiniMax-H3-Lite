#!/usr/bin/env python3
"""scripts/ops.py — 薄管理 CLI（status / health / backup）

把既有运维能力收敛为单入口，便于脚本化巡检与 CI/Agent 调用：

  status  — 离线巡检：端口 + 服务在线探测 + 关键目录磁盘占用 + git 简况（只读）
  health  — 在线健康：GET /api/health，退出码 0=健康 / 1=离线或异常
  backup  — 数据备份：包装 scripts/backup_data.py（复用既有实现，不重造）

设计约束：
  - 只读优先：status/health 不写任何文件；backup 委托 backup_data.py
    （注意：该脚本按 --keep 滚动保留最近 N 份，默认 5，超出部分会被其清退——
    这是备份工具的既定滚动语义；需要零清理时传 --keep 大值）
  - 零第三方依赖：status/health 仅用标准库
  - 端口来源链：MMH3_PORT 环境变量 > backend/config.py PORT 默认 18080
  - 与 LOCAL_RULES 对齐：本 CLI 自身无任何删除子命令

用法：
  python scripts/ops.py status
  python scripts/ops.py health [--json]
  python scripts/ops.py backup [--dest backup] [--keep 5] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # nosec B404 - 运维 CLI 需委托 git 与仓内脚本
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 18080
HEALTH_TIMEOUT = 3.0
# 磁盘占用统计目录（刻意不含 comfy_kernel/model 等禁区大目录）
USAGE_DIRS = ("outputs", "logs", "uploads", "data", "backup")
WALK_FILE_LIMIT = 5000  # 超过则跳过统计，避免大目录拖慢巡检

_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)  # 本机探测必须绕过系统代理（http_proxy 环境变量会把 127.0.0.1 打到代理上，得 502 假象）


def _read_port() -> int:
    """端口来源链：MMH3_PORT 环境变量 > backend/config.py > 18080。"""
    env_port = os.environ.get("MMH3_PORT")
    if env_port and env_port.strip().isdigit():
        return int(env_port.strip())
    cfg = ROOT / "backend" / "config.py"
    try:
        m = re.search(r"^\s*PORT:\s*int\s*=\s*(\d+)\s*$", cfg.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return DEFAULT_PORT


def _probe(base: str) -> tuple[bool, str]:
    """探测服务 /api/health；返回 (在线?, 原始响应或错误摘要)。"""
    url = f"{base}/api/health"
    try:
        with _OPENER.open(url, timeout=HEALTH_TIMEOUT) as resp:
            return True, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError, TimeoutError) as e:  # 连接拒绝/超时等
        return False, f"{type(e).__name__}: {e}"


def _dir_usage(path: Path) -> str:
    """统计目录磁盘占用（人读格式）；文件数超限或不存在时给出说明。"""
    if not path.exists():
        return "（不存在）"
    total = 0
    count = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                count += 1
                if count > WALK_FILE_LIMIT:
                    return "（条目过多，跳过统计）"
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except OSError as e:
        return f"（统计失败: {type(e).__name__}）"
    mb = total / (1024 * 1024)
    return f"{count} 文件 / {mb:.1f} MB"


def _git_brief() -> str:
    """git 简况：最近提交 + 未提交变更数；git 不可用时降级说明。"""
    try:
        head = subprocess.run(  # nosec B603 B607 - git 只读查询，参数固定字面量
            ["git", "log", "-1", "--format=%h %s"],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
        dirty = subprocess.run(  # nosec B603 B607 - git 只读查询，参数固定字面量
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
        if head.returncode != 0:
            return "（非 git 仓库或 git 不可用）"
        n = len([ln for ln in dirty.stdout.splitlines() if ln.strip()])
        return f"{head.stdout.strip()} ｜ 未提交变更 {n} 项"
    except (OSError, subprocess.TimeoutExpired):
        return "（git 调用失败）"


def cmd_status(_args: argparse.Namespace) -> int:
    """离线巡检：端口 / 服务在线 / 目录占用 / git 简况。"""
    port = _read_port()
    base = f"http://127.0.0.1:{port}"
    online, raw = _probe(base)

    print("MiniMax-H3-lite 运维巡检（只读）")
    print(f"  仓库根   : {ROOT}")
    print(f"  服务端口 : {port}（来源 MMH3_PORT env 或 backend/config.py）")
    if online:
        print(f"  服务状态 : ● 在线（{base}）")
        try:
            data = json.loads(raw)
            print(f"  /api/health 顶层键 : {', '.join(sorted(data.keys()))}")
        except json.JSONDecodeError:
            print("  服务状态 : ● 在线（响应非 JSON）")
    else:
        print(f"  服务状态 : ○ 离线（{raw}）——如需在线健康请先 python scripts/clean_launch.py")

    print("  目录占用 :")
    for d in USAGE_DIRS:
        print(f"    {d:<10}: {_dir_usage(ROOT / d)}")
    print(f"  git 简况 : {_git_brief()}")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """在线健康：GET /api/health，退出码 0=健康 / 1=离线或异常。"""
    port = _read_port()
    base = f"http://127.0.0.1:{port}"
    online, raw = _probe(base)
    if not online:
        print(f"[health] 服务不可达：{base}/api/health → {raw}")
        print(f"[health] 排查：服务是否已启动（python scripts/clean_launch.py，默认 127.0.0.1:{port}）")
        return 1
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[health] 服务在线但响应非 JSON：{raw[:120]}")
        return 1

    print(f"[health] {base}/api/health → HTTP 200")
    # 防御式提取：结构演进不致崩（backend/main.py health() 的已知字段）
    for key in ("status", "engine", "model", "backend", "quantization", "max_concurrency"):
        if key in data:
            print(f"  {key}: {data[key]}")
    if "model_loaded" in data:
        print(f"  model_loaded: {data['model_loaded']}" + ("（⚠ 权重未加载）" if not data["model_loaded"] else ""))
    if "queue_depth" in data:
        print(f"  queue_depth: {data['queue_depth']}")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    print("[health] 结论：服务在线" + ("" if data.get("model_loaded") else "（模型未加载，推理前需预热）"))
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    """数据备份：委托 scripts/backup_data.py，透传退出码。"""
    target = ROOT / "scripts" / "backup_data.py"
    if not target.exists():
        print(f"[backup] 找不到 {target}，无法委托备份")
        return 1
    cmd = [sys.executable, str(target), "--dest", args.dest, "--keep", str(args.keep)]
    if args.dry_run:
        cmd.append("--dry-run")
    print(f"[backup] 委托执行：{' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, cwd=ROOT, check=False)  # nosec B603 - 委托仓内 backup_data.py，参数经 argparse 白名单
    except OSError as e:
        print(f"[backup] 启动失败：{e}")
        return 1
    if proc.returncode == 0:
        print(f"[backup] 完成。备份根目录：{args.dest}（保留最近 {args.keep} 份）")
    else:
        print(f"[backup] backup_data.py 退出码 {proc.returncode}（详见上方输出）")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="ops",
        description="MiniMax-H3-lite 薄管理 CLI（status/health/backup，只读优先）",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="离线巡检：端口/服务在线/目录占用/git 简况")

    h = sub.add_parser("health", help="在线健康：GET /api/health（退出码 0/1）")
    h.add_argument("--json", action="store_true", help="追加输出完整 JSON")

    b = sub.add_parser("backup", help="数据备份（委托 backup_data.py，滚动保留 --keep 份）")
    b.add_argument("--dest", default="backup", help="备份根目录（默认 backup）")
    b.add_argument("--keep", type=int, default=5, help="保留最近 N 份（默认 5，与 backup_data.py 一致）")
    b.add_argument("--dry-run", action="store_true", help="仅列出待备份项，不写盘")

    args = ap.parse_args()
    return {"status": cmd_status, "health": cmd_health, "backup": cmd_backup}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
