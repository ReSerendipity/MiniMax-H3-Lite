"""scripts/comfy_kernel_baseline.py 的有效性验证。

关键设计约束：comfy_kernel/ 是禁区目录且不入库 —— 对它写入无法用 git 还原。
因此所有"漂移能否被抓到"的断言都在 tmp_path 合成内核上做，绝不触碰真实内核。
本文件即 spec 中 --selftest 的等价物（计划 R1：不加多余 CLI 面）。
"""
import importlib.util
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def mod():
    path = PROJECT_ROOT / "scripts" / "comfy_kernel_baseline.py"
    spec = importlib.util.spec_from_file_location("comfy_kernel_baseline", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def fake_kernel(tmp_path):
    """构造一个最小合成内核：3 个一级目录、若干文件。

    刻意带上 pyproject.toml：真实 vendored 内核有该文件，read_version() 靠它取版本。
    缺了它，--check 读到的版本是 None，会与基线里记录的版本构成"版本号漂移"而误红。
    """
    k = tmp_path / "comfy_kernel"
    for rel in ("comfy/sd.py", "comfy/model_management.py", "nodes.py",
                "custom_nodes/x.py", "folder_paths.py"):
        f = k / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# {rel}\nVALUE = 1\n", encoding="utf-8")
    (k / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\n", encoding="utf-8")
    (k / "pyproject.toml").write_text('[project]\nname = "comfyui"\nversion = "0.33.0"\n',
                                      encoding="utf-8")
    (k / "__pycache__").mkdir()
    (k / "__pycache__" / "junk.pyc").write_bytes(b"\x00")
    return k


def test_scan_skips_pycache(mod, fake_kernel):
    entries = mod.scan(fake_kernel)
    assert "__pycache__/junk.pyc" not in entries
    assert "comfy/sd.py" in entries
    assert len(entries) == 7


def test_baseline_roundtrip_is_stable(mod, fake_kernel):
    a = mod.build_baseline(fake_kernel, kernel_version="0.33.0")
    b = mod.build_baseline(fake_kernel, kernel_version="0.33.0")
    assert a["root_digest"] == b["root_digest"]
    assert a["file_count"] == 7
    assert a["kernel_version"] == "0.33.0"


def test_modified_file_is_detected_with_dir(mod, fake_kernel):
    base = mod.build_baseline(fake_kernel, kernel_version="0.33.0")
    (fake_kernel / "comfy" / "sd.py").write_text("# patched\nVALUE = 2\n", encoding="utf-8")
    drift = mod.diff(base, mod.build_baseline(fake_kernel, kernel_version="0.33.0"))
    assert drift != []
    assert any(d["dir"] == "comfy" for d in drift)


def test_added_and_removed_files_detected(mod, fake_kernel):
    base = mod.build_baseline(fake_kernel, kernel_version="0.33.0")
    (fake_kernel / "nodes.py").unlink()
    (fake_kernel / "new_dir" / "y.py").parent.mkdir(parents=True)
    (fake_kernel / "new_dir" / "y.py").write_text("x\n", encoding="utf-8")
    drift = mod.diff(base, mod.build_baseline(fake_kernel, kernel_version="0.33.0"))
    dirs = {d["dir"] for d in drift}
    assert "." in dirs        # nodes.py 位于内核根
    assert "new_dir" in dirs


def test_clean_kernel_has_no_drift(mod, fake_kernel):
    base = mod.build_baseline(fake_kernel, kernel_version="0.33.0")
    assert mod.diff(base, mod.build_baseline(fake_kernel, kernel_version="0.33.0")) == []


def test_verdict_is_fail_when_baseline_file_absent(mod, tmp_path):
    # 基线文件入库；它缺失等于门禁被拆掉 → FAIL，不可 SKIP
    assert mod.decide(baseline_present=False, kernel_present=True) == "FAIL"


def test_verdict_is_skip_when_kernel_absent(mod, tmp_path):
    # 内核不入库，托管 runner 上必然缺失 → SKIP（对齐 comfy-kernel-guard 既有语义）
    assert mod.decide(baseline_present=True, kernel_present=False) == "SKIP"


def test_verdict_is_check_when_both_present(mod):
    # 第三态：两者均在 → 进入实际摘要比对（与 classify_mount 的 OK 分支同位）
    assert mod.decide(baseline_present=True, kernel_present=True) == "CHECK"


def test_cli_writes_parseable_json(mod, fake_kernel, tmp_path):
    out = tmp_path / "base.json"
    rc = mod.main(["--root", str(fake_kernel), "--generate", "--out", str(out),
                   "--version", "0.33.0"])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["kernel_version"] == "0.33.0"
    assert data["file_count"] == 7
    rc2 = mod.main(["--root", str(fake_kernel), "--check", "--out", str(out)])
    assert rc2 == 0


def test_cli_check_fails_when_baseline_missing(mod, fake_kernel, tmp_path):
    """基线入库 → 它缺失等于门禁被拆掉，必须红（不可降级为 SKIP）。"""
    rc = mod.main(["--root", str(fake_kernel), "--check",
                   "--out", str(tmp_path / "no_such_baseline.json")])
    assert rc == 1


def test_cli_check_skips_when_kernel_missing(mod, tmp_path):
    """托管 runner 的干净 checkout 无内核 → SKIP 且 exit 0（沿用 guard 既有语义）。"""
    out = tmp_path / "base.json"
    out.write_text(json.dumps({"schema": 1, "kernel_version": "0.33.0",
                               "file_count": 7, "root_digest": "0" * 64, "dirs": {}}),
                   encoding="utf-8")
    rc = mod.main(["--root", str(tmp_path / "no_kernel"), "--check", "--out", str(out)])
    assert rc == 0
