"""版本口径一致性测试（发布版本管理评估 P0 防回归）。

断言：
- ``backend.__version__`` 等于 ``.release-please-manifest.json`` 的根包版本（单一事实来源）
- FastAPI ``app.version`` 与 ``backend.__version__`` 一致（不再硬编码 0.1.0）
- ``backend/main.py`` 内不存在硬编码的 ``version="x.y.z"`` 字面量
- manifest 缺失时回退到 ``-dev`` 后缀，而不是崩溃

注：AGENTS.md / docs/ 属 .gitignore 忽略的本地文档，文件不存在时跳过对应断言，
保证在干净 CI checkout 中依然可运行。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend import __version__ as pkg_version
from backend.version import FALLBACK_VERSION, MANIFEST_NAME, read_manifest_version

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def manifest_version() -> str:
    data = json.loads((PROJECT_ROOT / MANIFEST_NAME).read_text(encoding="utf-8"))
    return data["."]


def read_text(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """去掉 YAML 注释行，避免注释里出现的关键词造成误判。"""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_manifest_is_single_source_of_truth():
    assert pkg_version == manifest_version()
    assert pkg_version != FALLBACK_VERSION


def test_read_manifest_version_falls_back_when_missing(tmp_path):
    assert read_manifest_version(tmp_path) == FALLBACK_VERSION
    assert FALLBACK_VERSION.endswith("-dev")


def test_read_manifest_version_tolerates_corrupt_file(tmp_path):
    (tmp_path / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    assert read_manifest_version(tmp_path) == FALLBACK_VERSION


def test_app_version_tracks_manifest():
    from backend.main import app

    assert app.version == manifest_version()
    assert app.version == pkg_version


def test_main_py_has_no_hardcoded_version():
    src = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert re.search(r'version\s*=\s*["\']\d+\.\d+\.\d+', src) is None


def test_ci_does_not_hardcode_stale_version():
    workflows = sorted((PROJECT_ROOT / ".github" / "workflows").glob("*.yml"))
    offenders = [
        wf.name
        for wf in workflows
        if re.search(r"VERSION\s*=\s*0\.1\.0|version\s*=\s*[\"']0\.1\.0", wf.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_package_json_version_tracks_manifest():
    pkg = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == manifest_version()


def test_release_please_keeps_package_json_in_sync():
    cfg = json.loads((PROJECT_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    extra = cfg["packages"]["."].get("extra-files", [])
    assert {"type": "json", "path": "package.json", "jsonpath": "$.version"} in extra


def test_release_pipeline_gates_are_not_weakened():
    """发布链路不得用 continue-on-error / skip-github-pull-request 绕过审查。"""
    rp = _strip_comments(read_text(".github/workflows/release-please.yml"))
    assert "continue-on-error" not in rp
    assert re.search(r"skip-github-pull-request:\s*false", rp)

    test_wf_lines = _strip_comments(read_text(".github/workflows/test.yml")).splitlines()
    assert "continue-on-error" not in "\n".join(test_wf_lines)
    pytest_line = next(line for line in test_wf_lines if "pytest tests/" in line)
    assert "|| true" not in pytest_line
    smoke_line = next(line for line in test_wf_lines if "test:frontend" in line)
    assert "|| true" not in smoke_line


def test_coverage_gate_matches_pytest_ini():
    test_wf = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    ini = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")
    ci_threshold = re.search(r"--cov-fail-under=(\d+)", test_wf)
    ini_threshold = re.search(r"--cov-fail-under=(\d+)", ini)
    assert ci_threshold and ini_threshold
    assert ci_threshold.group(1) == ini_threshold.group(1)


@pytest.mark.skipif(
    not (PROJECT_ROOT / "AGENTS.md").exists(),
    reason="AGENTS.md 为 .gitignore 忽略的本地文档，CI checkout 中不存在",
)
def test_local_agents_md_announces_release_version():
    src = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert manifest_version() in src
