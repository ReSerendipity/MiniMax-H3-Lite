"""诊断包收集器单测（运维稳定性评估 P1-1）。纯标准库路径，不依赖真实 logs 内容。"""
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import diag_bundle  # noqa: E402


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "logs").mkdir(parents=True)
    (root / "logs" / "backend.log").write_text("hello log", encoding="utf-8")
    (root / "logs" / "backend_faults.log").write_text("fault stack", encoding="utf-8")
    (root / "package.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "mmh3.db").write_bytes(b"secret-db-bytes")
    return root


def test_bundle_contains_expected_and_excludes_user_data(tmp_path):
    root = _make_root(tmp_path)
    zpath, manifest = diag_bundle.make_bundle(root, tmp_path / "out")
    assert zpath.exists()
    with zipfile.ZipFile(zpath) as zf:
        names = set(zf.namelist())
    assert "logs/backend.log" in names
    assert "logs/backend_faults.log" in names
    assert "package.json" in names
    assert not any(n.startswith("data/") for n in names), "用户数据（data/mmh3.db）不得入包"
    assert any(line.startswith("sha256:") for line in manifest)


def test_bundle_empty_root_raises(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(SystemExit):
        diag_bundle.make_bundle(root, tmp_path / "out")


def test_cli_smoke(tmp_path, capsys):
    root = _make_root(tmp_path)
    rc = diag_bundle.main(["--root", str(root), "--out", str(tmp_path / "o2")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[OK] 诊断包" in out
    assert "sha256:" in out
