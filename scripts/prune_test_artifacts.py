"""测试副产物滚动清理：pytest_tmp 会话残留 + .benchmarks autosave 留档。

背景（2026-09-25 实测）：pytest 9 对显式 `--basetemp=pytest_tmp` 目录不在会话结束
清理（内置 `tmp_path_retention_*` 也只管辖自动生成的 `pytest-of-<user>` 目录），
每轮全量跑在仓库根留下 ~220 个函数级目录；下一会话虽会 rm_rf 全清，但 Windows
下后台队列 worker 持锁时部分删除静默失败（实测存量堆积至 223 个，含上一轮被锁
存留项）；`--benchmark-autosave` 则完全只增不减（.benchmarks 曾积 73 份 JSON）。
本脚本按「AGENTS.md 构建产物滚动清理铁律——只留最近几轮」精神提供 keep-N 回收；
会话末执行时持锁 worker 已退出，删除成功率高，且顺带把「下轮开始时无差别全清」
收敛为「本轮结束时有界保留」：

    python scripts/prune_test_artifacts.py                # 回收（pytest_tmp 留 3 份，.benchmarks 留 5 份）
    python scripts/prune_test_artifacts.py --dry-run      # 只列清单不删（存量盘点）
    python scripts/prune_test_artifacts.py --keep 1 --bench-keep 10

自动化接线：tests/conftest.py 的 pytest_sessionfinish 每次跑完以默认参数调用
prune_path()，把回收变成测试后动作；任何异常静默吞掉，绝不影响 pytest 退出码
（--basetemp 固定在仓库内的原始理由就是保证失败信号可信，见 TEST_COMMANDS.md）。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# .benchmarks 里这些文件名有特殊语义，永不删除：
#   baseline.json / baseline —— 人工留档基线（--benchmark-save=baseline 产物；
#                                benchmark.yml 的 hashFiles 判据同口径）
#   COMMIT Hash.txt          —— pytest-benchmark 记录基线 commit 的索引文件
PROTECTED_NAMES = {"baseline.json", "baseline", "COMMIT Hash.txt"}

# pytest-benchmark --benchmark-autosave 的文件名形如
# 0073_94ef06e7d16d82f7bb37004d99f9e7b0f40f7ea7_20260924_085518[_uncommited-changes].json
_AUTOSAVE_RE = re.compile(r"^\d{4}_")


def _is_autosave_file(p: Path) -> bool:
    return p.is_file() and bool(_AUTOSAVE_RE.match(p.name))


def prune_path(root: Path, keep: int, dry_run: bool = False,
               mode: str = "children") -> tuple[list[Path], int]:
    """按 mtime 只保留最近 keep 份，回收其余。两种盘点模式：

    - ``children``（pytest_tmp 用）：root 的直接子目录/文件各自算一份；
    - ``child-files``（.benchmarks 用）：只把平台子目录（Windows-CPython-3.12-64bit/
      等）内部的 autosave 文件算一份（实测真产物在第二层，平台目录本身不作为
      回收单元，抽空后保留空壳无害）。

    返回 (victims, failed)：victims 为将被（或 --dry-run 下本应被）删除的路径，
    按 mtime 从旧到新排序；failed 为删除时抛 OSError 被跳过、留待下次会话重试的
    条目数（Windows 下后台 worker 短暂持有句柄属常态）。
    symlink/junction 目标、受保护名与非 autosave 文件（child-files 模式）不参与
    回收。keep < 0 或 root 为 None/缺失表示不清理。
    """
    if root is None or keep < 0 or not root.is_dir():
        return [], 0
    entries: list[Path] = []
    if mode == "children":
        candidates: list[Path] = list(root.iterdir())
    else:
        candidates = [f for sub in root.iterdir() if sub.is_dir()
                      and not sub.is_symlink() and not sub.is_junction()
                      for f in sub.iterdir()]
    for p in candidates:
        if p.name in PROTECTED_NAMES:
            continue
        if p.is_symlink() or p.is_junction():
            # 只删链接本身风险不对称（易误伤模型等大目录目标），直接跳过
            continue
        if mode == "child-files" and not _is_autosave_file(p):
            continue
        entries.append(p)
    entries.sort(key=lambda p: p.stat().st_mtime)
    victims = entries[: max(0, len(entries) - keep)]
    if dry_run:
        return victims, 0
    failed = 0
    for p in victims:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError:
            failed += 1
    return victims, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="滚动清理 pytest_tmp 与 .benchmarks 测试副产物（keep-N）")
    parser.add_argument("--repo", default=None,
                        help="仓库根（缺省为脚本所在目录的上级）")
    parser.add_argument("--keep", type=int, default=3,
                        help="pytest_tmp 内保留最近 N 个会话残留（-1 不清理）")
    parser.add_argument("--bench-keep", type=int, default=5,
                        help=".benchmarks 内保留最近 N 份留档（默认 5；-1 不清理；baseline* 永不删）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列将删清单，不实际删除（存量盘点）")
    args = parser.parse_args(argv)

    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parent.parent
    total = 0
    targets = (("pytest_tmp", args.keep, "children"),
               (".benchmarks", args.bench_keep, "child-files"))
    for rel, keep, mode in targets:
        root = repo / rel
        victims, failed = prune_path(root, keep, dry_run=args.dry_run, mode=mode)
        action = "待删" if args.dry_run else "已删"
        print(f"[{rel}] keep={keep} {action}={len(victims)} 跳过(占用)={failed}")
        for p in victims:
            print(f"  - {p.relative_to(repo)}")
        total += len(victims)
    verb = "发现" if args.dry_run else "回收"
    print(f"合计{verb} {total} 项" + ("（--dry-run 未删除）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
