#!/usr/bin/env python3
"""Semgrep SAST 基线门禁（棘轮：只降不升）。

背景
----
sast.yml 原先整体 `continue-on-error: true`，且扫描步骤以 `|| true` 结尾，
注释里更直白写着"为保持首页绿色，此处改为 `|| true` 仅上报不阻断"——
这是把门禁主动关掉换来的绿，属于典型的假绿。

本脚本把"扫描"与"判定"分离：扫描照旧产出 JSON 与 SARIF（允许工具自身非零退出），
判定由本脚本基于 `.ci/semgrep_baseline.json` 做棘轮：
  * ERROR 数高于基线 → 失败（exit 1），并列出新增规则的 check_id 与位置
  * 低于基线 → 通过，并提示回写基线以收紧棘轮
  * 基线或报告缺失/结构异常 → 失败，不做"首次自动放行"

当前基线说明
------------
error = 1：`backend/routers/shots.py` 的 `UPDATE shots SET {set_clause} ...`。
列名已由 SHOT_UPDATABLE_COLUMNS 白名单在运行期校验（越界直接 400），
值一律走 `?` 占位符，不构成实际注入；semgrep 的 taint 规则无法证明这一点。
该基线由人工确认后入库，后续任何**新增** ERROR 都会让 CI 变红。

用法
----
    python scripts/sast_gate.py                    # 校验模式（CI 用）
    python scripts/sast_gate.py --update-baseline  # 回写基线（人工确认后用）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

BASELINE_PATH = os.path.join(".ci", "semgrep_baseline.json")
REPORT_PATH = "semgrep.json"
GATED_SEVERITIES = ("ERROR",)


def load_report(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        print(f"[FAIL] 缺少 {path} —— semgrep 未成功生成报告，门禁拒绝放行。")
        sys.exit(1)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"[FAIL] 无法解析 {path}: {exc}")
        sys.exit(1)

    # semgrep 因配置/网络失败时会输出 `{}` 或只有 errors 的 JSON。
    # 此时 results 缺失，漏洞数会被误读为 0 —— 必须判失败。
    if not isinstance(data, dict) or "results" not in data:
        print(f"[FAIL] {path} 结构异常（缺少 results 字段）。")
        print("       semgrep 很可能执行失败，结果不可信，门禁拒绝放行。")
        sys.exit(1)
    return data


def count_by_severity(report: dict[str, Any]) -> dict[str, int]:
    counts = {sev: 0 for sev in ("ERROR", "WARNING", "INFO")}
    findings: dict[str, list[str]] = {sev: [] for sev in counts}
    for result in report.get("results", []) or []:
        extra = result.get("extra") or {}
        sev = (extra.get("severity") or "").upper()
        if sev not in counts:
            continue
        counts[sev] += 1
        check_id = extra.get("check_id", "?")
        path = (result.get("path") or "?")
        start = (result.get("start") or {}).get("line", "?")
        findings[sev].append(f"{check_id} @ {path}:{start}")
    return counts, findings  # type: ignore[return-value]


def load_baseline() -> dict[str, int]:
    if not os.path.exists(BASELINE_PATH):
        print(f"[FAIL] 缺少基线文件 {BASELINE_PATH}。")
        print("       基线必须人工确认后入库，本门禁不做首次自动放行（否则仍是假绿）。")
        print("       生成方式：python scripts/sast_gate.py --update-baseline")
        sys.exit(1)
    with open(BASELINE_PATH, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except ValueError as exc:
            print(f"[FAIL] 基线文件 {BASELINE_PATH} 解析失败: {exc}")
            sys.exit(1)
    if not isinstance(data, dict):
        print(f"[FAIL] 基线文件 {BASELINE_PATH} 格式非法（应为 JSON 对象）。")
        sys.exit(1)
    return {sev: int(data.get(sev.lower(), data.get(sev, 0)) or 0) for sev in GATED_SEVERITIES}


def main() -> int:
    parser = argparse.ArgumentParser(description="Semgrep SAST 基线门禁")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="用当前扫描结果回写 .ci/semgrep_baseline.json",
    )
    args = parser.parse_args()

    report = load_report(REPORT_PATH)
    counts, findings = count_by_severity(report)

    print("=== Semgrep SAST 扫描结果 ===")
    for sev in ("ERROR", "WARNING", "INFO"):
        print(f"  {sev:<8}: {counts[sev]}")

    current = {sev: counts[sev] for sev in GATED_SEVERITIES}

    if args.update_baseline:
        os.makedirs(os.path.dirname(BASELINE_PATH) or ".", exist_ok=True)
        with open(BASELINE_PATH, "w", encoding="utf-8") as fh:
            json.dump({k.lower(): v for k, v in current.items()}, fh, indent=2)
            fh.write("\n")
        print(f"[OK] 基线已回写 {BASELINE_PATH}: {current}")
        return 0

    baseline = load_baseline()
    print(f"=== 基线 {BASELINE_PATH}: {baseline} ===")

    regressions, improvements = [], []
    for sev in GATED_SEVERITIES:
        now, base = current[sev], baseline[sev]
        if now > base:
            regressions.append((sev, base, now))
        elif now < base:
            improvements.append((sev, base, now))

    if regressions:
        print("[FAIL] SAST 债务上升，棘轮门禁拒绝放行：")
        for sev, base, now in regressions:
            print(f"      - {sev}: {base} -> {now} (+{now - base})")
            for line in findings[sev][:50]:
                print(f"          {line}")
        print("      若确为误报，请在代码中以 `# nosemgrep: <rule-id>` 注明理由，")
        print("      或人工复核后回写基线：python scripts/sast_gate.py --update-baseline")
        return 1

    if improvements:
        print("[PASS] SAST 债务下降，建议回写基线以收紧棘轮：")
        for sev, base, now in improvements:
            print(f"      - {sev}: {base} -> {now} (-{base - now})")
        print("          python scripts/sast_gate.py --update-baseline")

    print("[PASS] Semgrep SAST 基线门禁通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
