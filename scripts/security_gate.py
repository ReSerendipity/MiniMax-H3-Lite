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

SLA 计时台账 (.ci/vuln_sla_state.json)：
    任一门禁指标 >0 视为存在未修复债务，自首次观测起计时；npm critical 168h /
    npm high 720h / pip-audit（无严重度字段）按 High 档 720h；归零自动清除；
    超时即 exit 1。CI 经 actions/cache 使状态跨 run 持续（cache miss 时钟重置，
    为已记录的降级口径，见 .github/SECURITY.md SLA 节）。
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
# ── 漏洞修复 SLA 计时台账（软件供应链安全评估 P1-2）────────────────────
# 与 .github/SECURITY.md「漏洞修复 SLA」同源：critical→168h、high→720h；
# pip-audit 报告无严重度字段，按 High 档 720h。任一指标 >0 即从首次观测起算，
# 归零自动清除；超时即门禁失败。状态文件 CI 经 actions/cache 跨 run 持续。
SLA_STATE_PATH = os.path.join(".ci", "vuln_sla_state.json")
SLA_HOURS = {"pip_audit_vulns": 720, "npm_critical": 168, "npm_high": 720}


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


def load_sla_state(path: str | None = None) -> dict:
    """读取 SLA 状态文件；缺失返回 {}，损坏判失败（同基线口径：拒绝静默重置）。"""
    p = path or SLA_STATE_PATH
    data = _load_json(p)
    if data is None:
        return {}
    if not isinstance(data, dict):
        print(f"[FAIL] SLA 状态文件 {p} 格式非法（应为 JSON 对象）。")
        sys.exit(1)
    return data


def judge_sla(current: dict[str, int], state: dict, now: Any = None) -> tuple[bool, dict, list[str]]:
    """SLA 判定：债务>0 从首次观测起算、归零清除；返回 (无超时, 新状态, 违规消息)。"""
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc)
    new_state = dict(state)
    violations: list[str] = []
    for metric in GATED_METRICS:
        debt = current.get(metric, 0) > 0
        if debt:
            entry = new_state.get(metric)
            since_str = entry.get("since") if isinstance(entry, dict) else None
            if not since_str:
                # 首次观测：开始计时，本次不判超时（否则每个新漏洞立刻红）
                new_state[metric] = {
                    "since": now.isoformat(timespec="seconds"),
                    "last_seen": now.isoformat(timespec="seconds"),
                    "count": current[metric],
                }
                continue
            try:
                since = datetime.fromisoformat(since_str)
            except ValueError:
                print(f"[WARN] {metric} 的 since 时间戳不可解析（{since_str!r}），时钟重置。")
                new_state[metric] = {
                    "since": now.isoformat(timespec="seconds"),
                    "last_seen": now.isoformat(timespec="seconds"),
                    "count": current[metric],
                }
                continue
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            elapsed_h = (now - since).total_seconds() / 3600
            sla = SLA_HOURS[metric]
            new_state[metric]["last_seen"] = now.isoformat(timespec="seconds")
            new_state[metric]["count"] = current[metric]
            if elapsed_h > sla:
                violations.append(
                    f"{metric}: 首次观测 {since_str}，已持续 {elapsed_h:.1f}h > SLA {sla}h —— 高危漏洞超时限未修复"
                )
        else:
            new_state.pop(metric, None)
    return (not violations), new_state, violations


def persist_sla_state(state: dict, path: str | None = None) -> None:
    p = path or SLA_STATE_PATH
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


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
    # ── SLA 计时台账（软件供应链安全评估 P1-2）：债务存量有时限，超时即阻断 ──
    sla_ok, new_state, sla_violations = judge_sla(current, load_sla_state())
    persist_sla_state(new_state)
    for metric in GATED_METRICS:
        entry = new_state.get(metric)
        if entry:
            print(
                f"  SLA {metric}: 债务 {entry.get('count', 0)} 项，"
                f"首次观测 {entry.get('since')}（SLA {SLA_HOURS[metric]}h）"
            )

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

    if sla_violations:
        print("[FAIL] 高危漏洞修复超时限（SLA 台账）：")
        for item in sla_violations:
            print(f"      - {item}")
        print("      债务归零即自动清除计时；确需延期请人工评估并修订 .github/SECURITY.md 时限政策。")
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
