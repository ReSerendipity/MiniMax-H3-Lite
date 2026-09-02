#!/usr/bin/env python3
"""依赖安全基线门禁（棘轮：只降不升）。

背景
----
此前 security-scan job 使用 `job.continue-on-error: true`，且两个审计步骤都以
`|| true` 结尾，导致 pip-audit / npm audit 的结果**永远不会阻断 CI**——即使扫出
高危漏洞，commit 状态依然是绿的。这是典型的假绿。

本脚本把"报告生成"与"门禁判定"彻底分离：
  * 报告步骤照旧生成 JSON（允许审计工具自身非零退出，仅影响报告完整性）
  * 本脚本读取报告、统计告警数，与 `.ci/security_baseline.json` 比对：
      - 任一指标 **高于** 基线 → 失败（exit 1），并打印新增项
      - 任一指标 **低于** 基线 → 通过，并提示回写基线（棘轮自动收紧）
      - 基线文件 **缺失** → 失败。刻意不做"首次自动放行"，
        否则又是一次性的假绿；基线必须由人显式确认后入库。

用法
----
    python scripts/security_gate.py                  # 校验模式（CI 用）
    python scripts/security_gate.py --update-baseline # 回写基线（人工确认后用）

基线格式 (.ci/security_baseline.json)：
    {"pip_audit_vulns": 0, "npm_critical": 0, "npm_high": 0}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

BASELINE_PATH = os.path.join(".ci", "security_baseline.json")
PIP_REPORT = "pip-audit-report.json"
NPM_REPORT = "npm-audit-report.json"

# 只有这些指标参与门禁；npm 的 moderate/low 仅打印，不阻断，
# 避免被无法修复的传递依赖噪音长期锁定。
GATED_METRICS = ("pip_audit_vulns", "npm_critical", "npm_high")


def _load_json(path: str) -> Any | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"[FAIL] 无法解析 {path}: {exc}")
        print("       报告损坏等同于门禁失明，拒绝放行。")
        sys.exit(1)


def count_pip_audit(report: Any | None) -> tuple[int, list[str]]:
    """统计 pip-audit 报告中的漏洞总数及 ID 列表。

    pip-audit 的 JSON schema 为 {"dependencies": [{"name","version","vulns":[...]}]}。
    该 schema 不含 severity 字段，因此这里按"漏洞条目总数"计数。
    """
    if report is None:
        print(f"[FAIL] 缺少 {PIP_REPORT} —— pip-audit 未成功生成报告，门禁拒绝放行。")
        sys.exit(1)

    # 报告存在但结构不对（例如 pip-audit 因网络/解析失败输出 `{}`）时必须判失败：
    # 否则漏洞数会被当作 0，门禁静默放行 —— 这正是旧 `|| true` 的假绿形态。
    if "dependencies" not in report:
        print(f"[FAIL] {PIP_REPORT} 结构异常（缺少 dependencies 字段）。")
        print("       pip-audit 很可能执行失败，漏洞数不可信，门禁拒绝放行。")
        sys.exit(1)

    ids: list[str] = []
    for dep in report.get("dependencies", []) or []:
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        for vuln in dep.get("vulns", []) or []:
            vid = vuln.get("id") or ",".join(vuln.get("aliases", []) or []) or "UNKNOWN"
            ids.append(f"{vid} ({name}=={version})")
    return len(ids), ids


def count_npm_audit(report: Any | None) -> dict[str, int]:
    """统计 npm audit 报告的各级别漏洞数。

    兼容两种 schema：
      * npm 7/8/9：`metadata.vulnerabilities.{critical,high,...}`
      * npm 10+：`vulnerabilities` 为扁平映射，每项带 severity 字段
    """
    if report is None:
        print(f"[FAIL] 缺少 {NPM_REPORT} —— npm audit 未成功生成报告，门禁拒绝放行。")
        sys.exit(1)

    counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0}

    meta = (report.get("metadata") or {}).get("vulnerabilities")
    if isinstance(meta, dict):
        for key in counts:
            counts[key] = int(meta.get(key, 0) or 0)
        return counts

    flat = report.get("vulnerabilities") or {}
    if isinstance(flat, dict):
        for item in flat.values():
            if isinstance(item, dict):
                sev = (item.get("severity") or "").lower()
                if sev in counts:
                    counts[sev] += 1
        return counts

    # 两种 schema 都不匹配 → npm audit 多半因 registry 不支持 audit 端点而失败
    # （例如镜像源返回 404）。此时不能当成 0 漏洞放行。
    print(f"[FAIL] {NPM_REPORT} 结构异常（既无 metadata.vulnerabilities 也无 vulnerabilities）。")
    print("       npm audit 很可能执行失败（常见于镜像源不支持 audit 端点），")
    print("       漏洞数不可信，门禁拒绝放行。")
    sys.exit(1)


def load_baseline() -> dict[str, int]:
    if not os.path.exists(BASELINE_PATH):
        print(f"[FAIL] 缺少基线文件 {BASELINE_PATH}。")
        print("       基线必须人工确认后入库，本门禁不做首次自动放行（否则仍是假绿）。")
        print("       生成方式：python scripts/security_gate.py --update-baseline")
        sys.exit(1)
    data = _load_json(BASELINE_PATH)
    if not isinstance(data, dict):
        print(f"[FAIL] 基线文件 {BASELINE_PATH} 格式非法（应为 JSON 对象）。")
        sys.exit(1)
    return {k: int(data.get(k, 0) or 0) for k in GATED_METRICS}


def main() -> int:
    parser = argparse.ArgumentParser(description="依赖安全基线门禁")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="用当前扫描结果回写 .ci/security_baseline.json",
    )
    args = parser.parse_args()

    pip_count, pip_ids = count_pip_audit(_load_json(PIP_REPORT))
    npm_counts = count_npm_audit(_load_json(NPM_REPORT))

    current = {
        "pip_audit_vulns": pip_count,
        "npm_critical": npm_counts["critical"],
        "npm_high": npm_counts["high"],
    }

    print("=== 依赖安全扫描结果 ===")
    print(f"  pip-audit 漏洞数 : {pip_count}")
    for line in pip_ids:
        print(f"      - {line}")
    print(
        "  npm audit        : "
        f"critical={npm_counts['critical']} high={npm_counts['high']} "
        f"moderate={npm_counts['moderate']} low={npm_counts['low']}"
    )

    if args.update_baseline:
        os.makedirs(os.path.dirname(BASELINE_PATH) or ".", exist_ok=True)
        with open(BASELINE_PATH, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"[OK] 基线已回写 {BASELINE_PATH}: {current}")
        return 0

    baseline = load_baseline()
    print(f"=== 基线 {BASELINE_PATH}: {baseline} ===")

    regressions = []
    improvements = []
    for metric in GATED_METRICS:
        now, base = current[metric], baseline[metric]
        if now > base:
            regressions.append(f"{metric}: {base} -> {now} (+{now - base})")
        elif now < base:
            improvements.append(f"{metric}: {base} -> {now} (-{base - now})")

    if regressions:
        print("[FAIL] 依赖安全债务上升，棘轮门禁拒绝放行：")
        for item in regressions:
            print(f"      - {item}")
        print("      若确为可接受风险，请人工复核后回写基线：")
        print("          python scripts/security_gate.py --update-baseline")
        return 1

    if improvements:
        print("[PASS] 安全债务下降，建议回写基线以收紧棘轮：")
        for item in improvements:
            print(f"      - {item}")
        print("          python scripts/security_gate.py --update-baseline")

    print("[PASS] 依赖安全基线门禁通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
