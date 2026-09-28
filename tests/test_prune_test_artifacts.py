"""scripts/prune_test_artifacts.py 的回归测试（2026-09-25 副产物滚动清理接线）。

背景：pytest 9 对显式 --basetemp 目录不在会话结束清理（仅下轮开始时 rm_rf 全清，
Windows 持锁项静默存活），仓库根 pytest_tmp/ 曾跨会话积 223 个残留目录进入检索
面；本脚本 + conftest 的 sessionfinish 钩子负责 keep-N 会话末回收。这里锁定
prune_path 的核心语义：留新删旧、受保护名不删、dry-run 不落地、占用（OSError）
计失败并保留、目录缺失/keep<0/None 安全返回。
"""
import importlib.util
import os
import shutil
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def mod():
    path = PROJECT_ROOT / "scripts" / "prune_test_artifacts.py"
    spec = importlib.util.spec_from_file_location("prune_test_artifacts", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_entry(root: Path, name: str, seconds_ago: float) -> Path:
    """建一个目录型残留并把 mtime 拨旧 seconds_ago 秒（模拟历次会话）。"""
    p = root / name
    p.mkdir(parents=True)
    (p / "f.txt").write_text(name, encoding="utf-8")
    t = time.time() - seconds_ago
    os.utime(p, (t, t))
    return p


def test_prune_keeps_newest_and_removes_older(mod, tmp_path):
    root = tmp_path / "runs"
    old = _make_entry(root, "old_session", 300)
    mid = _make_entry(root, "mid_session", 200)
    new = _make_entry(root, "new_session", 100)
    victims, failed = mod.prune_path(root, keep=2)
    assert victims == [old]
    assert failed == 0
    assert not old.exists()
    assert mid.exists() and new.exists()


def test_protected_names_never_pruned(mod, tmp_path):
    root = tmp_path / "bench"
    root.mkdir(parents=True)
    baseline = root / "baseline.json"
    baseline.write_text("{}", encoding="utf-8")
    t = time.time() - 9999
    os.utime(baseline, (t, t))
    old = _make_entry(root, "0001_deadbeef", 300)
    _make_entry(root, "0002_cafebabe", 100)
    victims, _ = mod.prune_path(root, keep=1)
    assert victims == [old]
    assert baseline.exists()


def test_child_files_mode_prunes_autosave_in_platform_subdir(mod, tmp_path):
    """实测布局：.benchmarks/<Windows-CPython-3.12-64bit>/NNNN_*.json（第二层）。
    child-files 模式只回收平台子目录内的 autosave 文件；平台目录本身、非
    autosave 文件（baseline.json / COMMIT Hash.txt）都不得动。"""
    root = tmp_path / ".benchmarks"
    plat = root / "Windows-CPython-3.12-64bit"
    old = plat / "0001_aaa_20260101_000000.json"
    mid = plat / "0002_bbb_20260102_000000.json"
    new = plat / "0003_ccc_20260103_000000.json"
    for p, ago in ((old, 300), (mid, 200), (new, 100)):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")
        t = time.time() - ago
        os.utime(p, (t, t))
    keepers = [plat / "baseline.json", plat / "COMMIT Hash.txt", plat / "notes.md"]
    for k in keepers:
        k.write_text("x", encoding="utf-8")
        os.utime(k, (time.time() - 9999, time.time() - 9999))
    victims, failed = mod.prune_path(root, keep=2, mode="child-files")
    assert victims == [old]
    assert failed == 0
    assert not old.exists()
    assert mid.exists() and new.exists()
    assert all(k.exists() for k in keepers)
    assert plat.exists(), "平台目录本身不作为回收单元"


def test_dry_run_lists_without_deleting(mod, tmp_path):
    root = tmp_path / "dry"
    old = _make_entry(root, "old_one", 300)
    _make_entry(root, "new_one", 100)
    victims, failed = mod.prune_path(root, keep=1, dry_run=True)
    assert victims == [old]
    assert failed == 0
    assert old.exists(), "--dry-run 不得实际删除"


def test_negative_keep_and_missing_dir_are_noop(mod, tmp_path):
    root = tmp_path / "runs"
    kept = _make_entry(root, "only", 100)
    assert mod.prune_path(root, keep=-1) == ([], 0)
    assert kept.exists()
    assert mod.prune_path(tmp_path / "no_such_dir", keep=1) == ([], 0)


def test_locked_entry_counted_failed_and_survives(mod, tmp_path, monkeypatch):
    """Windows 下后台 worker 短暂持有句柄 → rmtree 抛 OSError：计 failed、不抛出、
    条目保留待下次会话重试（清理是尽力而为，绝不能把异常冒到调用方）。"""
    root = tmp_path / "runs"
    old = _make_entry(root, "old_locked", 300)
    _make_entry(root, "new_one", 100)
    real_rmtree = shutil.rmtree

    def fake_rmtree(path, *a, **kw):
        if Path(path).name == "old_locked":
            raise PermissionError("simulated open handle")
        real_rmtree(path, *a, **kw)

    monkeypatch.setattr(mod.shutil, "rmtree", fake_rmtree)
    victims, failed = mod.prune_path(root, keep=1)
    assert victims == [old]
    assert failed == 1
    assert old.exists()


@pytest.mark.skipif(os.name != "nt", reason="junction 仅 Windows 可用")
def test_junction_targets_are_skipped(mod, tmp_path):
    """副产物目录若被做成 junction（本仓 model/ 有此先例），删链接有误伤目标
    的风险，必须整项跳过、不进 victims。"""
    target = tmp_path / "real_model"
    target.mkdir()
    (target / "weight.bin").write_bytes(b"\x00" * 16)
    root = tmp_path / "runs"
    link = root / "old_link"
    os.makedirs(root, exist_ok=True)
    os.system(f'mklink /J "{link}" "{target}" >nul 2>&1')  # nosec B605 测试内建 junction（link 须预先不存在）
    if not link.is_junction():
        pytest.skip("当前环境无法创建 junction")
    _make_entry(root, "new_one", 10)
    victims, _ = mod.prune_path(root, keep=0)
    assert link not in victims
    assert (target / "weight.bin").exists()
