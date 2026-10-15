"""security_gate SLA 计时台账单测（软件供应链安全评估 P1-2）。

纯标准库路径：不跑真实 pip-audit/npm audit，用合成报告驱动门禁判定。
覆盖：零债务清除、首次观测起算、期内通过、超时阻断（critical/high/pip 双指标）、
状态文件损坏拒判（fail-closed，同基线口径）。
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import security_gate as sg  # noqa: E402


def _setup(tmp_path, monkeypatch, *, critical=0, high=0, pip_vulns=0, state=None, corrupt_state=False, baseline=None):
    monkeypatch.setattr(sg, "PIP_REPORT", str(tmp_path / "pip.json"))
    monkeypatch.setattr(sg, "NPM_REPORT", str(tmp_path / "npm.json"))
    monkeypatch.setattr(sg, "BASELINE_PATH", str(tmp_path / "ci" / "security_baseline.json"))
    monkeypatch.setattr(sg, "SLA_STATE_PATH", str(tmp_path / "ci" / "vuln_sla_state.json"))
    (tmp_path / "ci").mkdir(exist_ok=True)
    (tmp_path / "pip.json").write_text(json.dumps(
        {"dependencies": [{"name": "a", "version": "1.0", "vulns": ([{"id": "GHSA-x"}] if pip_vulns else [])}]},
    ), encoding="utf-8")
    (tmp_path / "npm.json").write_text(json.dumps(
        {"metadata": {"vulnerabilities": {"critical": critical, "high": high, "moderate": 0, "low": 0, "info": 0}}},
    ), encoding="utf-8")
    base = baseline or {"pip_audit_vulns": 0, "npm_critical": 0, "npm_high": 0}
    (tmp_path / "ci" / "security_baseline.json").write_text(json.dumps(base), encoding="utf-8")
    if corrupt_state:
        (tmp_path / "ci" / "vuln_sla_state.json").write_text("{not-json", encoding="utf-8")
    elif state is not None:
        (tmp_path / "ci" / "vuln_sla_state.json").write_text(json.dumps(state), encoding="utf-8")


def _run(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["security_gate.py"])
    return sg.main()


def test_zero_debt_passes_and_state_cleared(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, state={"npm_critical": {"since": "2026-01-01T00:00:00+00:00", "count": 3}})
    assert _run(monkeypatch) == 0
    assert json.loads(Path(sg.SLA_STATE_PATH).read_text(encoding="utf-8")) == {}


def test_fresh_debt_starts_clock_and_passes(tmp_path, monkeypatch):
    # SLA 语义：基线已接受该债务（棘轮不红），台账只管「存量清偿时限」
    _setup(tmp_path, monkeypatch, critical=1, baseline={"pip_audit_vulns": 0, "npm_critical": 1, "npm_high": 0})
    assert _run(monkeypatch) == 0
    state = json.loads(Path(sg.SLA_STATE_PATH).read_text(encoding="utf-8"))
    assert state["npm_critical"]["count"] == 1
    assert "since" in state["npm_critical"]


def test_within_sla_passes(tmp_path, monkeypatch):
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    _setup(tmp_path, monkeypatch, critical=1, baseline={"pip_audit_vulns": 0, "npm_critical": 1, "npm_high": 0}, state={"npm_critical": {"since": since, "count": 1}})
    assert _run(monkeypatch) == 0


def test_aged_critical_fails(tmp_path, monkeypatch):
    since = (datetime.now(timezone.utc) - timedelta(hours=169)).isoformat(timespec="seconds")
    _setup(tmp_path, monkeypatch, critical=1, baseline={"pip_audit_vulns": 0, "npm_critical": 1, "npm_high": 0}, state={"npm_critical": {"since": since, "count": 1}})
    assert _run(monkeypatch) == 1


def test_aged_pip_debt_fails(tmp_path, monkeypatch):
    since = (datetime.now(timezone.utc) - timedelta(hours=721)).isoformat(timespec="seconds")
    _setup(tmp_path, monkeypatch, pip_vulns=1, baseline={"pip_audit_vulns": 1, "npm_critical": 0, "npm_high": 0}, state={"pip_audit_vulns": {"since": since, "count": 1}})
    assert _run(monkeypatch) == 1


def test_corrupt_state_fails_closed(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, critical=1, corrupt_state=True)
    with pytest.raises(SystemExit) as ei:
        _run(monkeypatch)
    assert ei.value.code == 1
