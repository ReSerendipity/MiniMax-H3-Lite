#!/usr/bin/env python3
"""依赖锁覆盖门禁：拦住 requirements.txt 与 requirements-lock.txt 的静默分叉。

背景
----
test.yml 的 lock-consistency job 原先只有一条 `pip install --dry-run -r
requirements-lock.txt`，它验证的是"锁自身可解析"，结构上看不到
requirements.txt 新增了一个直接依赖而锁里没有。2026-09-24 实测：requirements.txt
的 33 个直接依赖中有 17 个完全不在锁里，而锁头自称由
`pip-compile ... requirements.txt` 生成——该命令不可能产出缺 17 个直接输入的锁。
这不致红也不丢测试覆盖（见下方 allowlist 说明），但"锁一致性 = 通过"会被下游
读成"两份清单已对账"，而它从未做过这件事。

本脚本补的正是这一条，且做成双向棘轮：
  * requirements.txt 有、锁里没有、且不在 allowlist → 失败（新增漂移）
  * allowlist 有、但当前已不在缺失集里 → 失败（豁免条目已失效，必须回删）
第二条是防豁免名单自己长成新的谎言：把包补进锁的人必须同时删掉它的豁免行，
否则本门禁红。

影响面核验（2026-09-24）
------------------------
被豁免的 17 个包是 Comfy 内核运行集：全仓（排除 .git / node_modules /
comfy_kernel / __pycache__）逐文件正则扫 import，命中 **0 处**；同规则扫未入库
的 comfy_kernel/ 命中 **974 个 .py**。即按 GPL-vendoring 边界本就不该进 CI 测试
环境，故本门禁不改变任何安装行为，只把"有意为之"从口头约定变成入库判据。

用法
----
    python scripts/check_lock_coverage.py            # 校验（CI 用），漂移时退出码 1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ_PATH = ROOT / "requirements.txt"
LOCK_PATH = ROOT / "requirements-lock.txt"
ALLOWLIST_PATH = ROOT / ".ci" / "lock_coverage_allowlist.txt"

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def canonical(name: str) -> str:
    """PEP 503 名称归一：小写，连续 -_. 折叠为单个 -。"""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirement_names(path: Path) -> set[str]:
    """提取 requirements 风格文件里的包名集合（忽略注释/空行/选项行）。"""
    if not path.exists():
        print(f"[FAIL] 清单不存在: {path.relative_to(ROOT)}")
        sys.exit(1)
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        head = line.split("@", 1)[0]
        match = _NAME_RE.match(head)
        if match:
            names.add(canonical(match.group(1)))
    return names


def parse_allowlist(path: Path) -> set[str]:
    if not path.exists():
        print(f"[FAIL] 豁免清单不存在: {path.relative_to(ROOT)}")
        print("       本门禁不做「首次自动放行」——缺失即失败，与 sast_gate.py 同口径。")
        sys.exit(1)
    entries: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            entries.add(canonical(line))
    return entries


def main() -> int:
    req = parse_requirement_names(REQ_PATH)
    lock = parse_requirement_names(LOCK_PATH)
    allowed = parse_allowlist(ALLOWLIST_PATH)

    missing = req - lock
    regressions = sorted(missing - allowed)
    stale = sorted(allowed - missing)

    print(f"=== 依赖锁覆盖 {REQ_PATH.name} -> {LOCK_PATH.name} ===")
    print(f"  requirements.txt 直接依赖 : {len(req)}")
    print(f"  锁内条目（唯一名）        : {len(lock)}")
    print(f"  未出现在锁中              : {len(missing)}")
    print(f"  已显式豁免                : {len(allowed)}")

    rc = 0
    if regressions:
        rc = 1
        print(f"[FAIL] 出现 {len(regressions)} 个未豁免的缺失依赖，门禁拒绝放行：")
        for name in regressions:
            print(f"  - {name}")
        print("  二选一：")
        print(f"    1) 把上述包补进 {LOCK_PATH.name}（常规做法）")
        print(f"    2) 确属有意不入 CI 锁（如 vendored 内核运行集），在 "
              f"{ALLOWLIST_PATH.relative_to(ROOT)} 注明理由后豁免")
    if stale:
        rc = 1
        print(f"[FAIL] 豁免清单里有 {len(stale)} 条已失效（现已不在缺失集）：")
        for name in stale:
            print(f"  - {name}")
        print("  请从豁免清单删掉这些行，别让豁免名单继续虚胖。")

    if rc == 0:
        print("[PASS] 锁覆盖与豁免清单严格一致。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
