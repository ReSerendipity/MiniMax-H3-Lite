#!/usr/bin/env python3
"""备份 MiniMax-H3-lite 运行时数据（SQLite + settings + checkpoints）。

运维稳定性评估发现：SRE_RUNBOOK §3 声明了 SQLite 定期备份，但 ``scripts/`` 零备份脚本
（连「只备不练」都谈不上）。本脚本把 SLO/DR 表中的备份预案落地为可重复、可审计的命令。

- 备份范围：``data/mmh3.db``、``data/settings.json``、``data/checkpoints/*.json``
- 不触碰 ``model/`` 禁区（权重离线冷备由 SRE_RUNBOOK 另行规定）。
- 每次运行落到 ``backup/<时间戳>/``，默认保留最近 5 份（``--keep`` 调整）。
- ``--dry-run`` 仅列出待备份项，不写盘。

用法：
    python scripts/backup_data.py                 # 默认备份到 ./backup
    python scripts/backup_data.py --keep 10       # 保留最近 10 份
    python scripts/backup_data.py --dest D:/bak   # 自定义目标目录
    python scripts/backup_data.py --dry-run       # 预演
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_DEST = ROOT / "backup"


def collect_sources() -> list[Path]:
    """收集待备份文件（存在才纳入）。"""
    sources: list[Path] = []
    for p in (DATA / "mmh3.db", DATA / "settings.json"):
        if p.exists():
            sources.append(p)
    ckpt = DATA / "checkpoints"
    if ckpt.exists():
        sources.extend(sorted(ckpt.glob("*.json")))
    return sources


def prune_old(dest: Path, keep: int) -> list[Path]:
    """删除超出保留份数的历史备份目录，返回被清理的目录。"""
    if not dest.is_dir():
        return []
    runs = sorted(dest.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    pruned: list[Path] = []
    for old in runs[keep:]:
        shutil.rmtree(old, ignore_errors=True)
        pruned.append(old)
    return pruned


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="备份 MiniMax-H3-lite 运行时数据")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="备份根目录（默认 ./backup）")
    ap.add_argument("--keep", type=int, default=5, help="保留最近 N 份（默认 5）")
    ap.add_argument("--dry-run", action="store_true", help="仅列出待备份项，不写盘")
    args = ap.parse_args(argv)

    sources = collect_sources()
    if not sources:
        print(f"无待备份数据（{DATA} 为空或不存在），跳过。")
        return 0

    if args.dry_run:
        print(f"[dry-run] 目标目录：{args.dest}（保留 {args.keep} 份）")
        for s in sources:
            print(f"  would copy {s} -> {args.dest / datetime.now().strftime('%Y%m%d-%H%M%S') / s.relative_to(DATA)}")
        return 0

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = args.dest / ts
    dest.mkdir(parents=True, exist_ok=True)
    for s in sources:
        target = dest / s.relative_to(DATA)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, target)
        print(f"backed up {s.name} -> {target}")

    pruned = prune_old(args.dest, max(0, args.keep))
    for old in pruned:
        print(f"pruned old backup {old}")
    print(f"完成：{len(sources)} 个文件 -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
