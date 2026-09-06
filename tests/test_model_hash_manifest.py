"""权重 SHA-256 manifest 工具单测（MLOps 评估 P1 · 防篡改补位）。

覆盖：
  * --generate：生成 manifest，格式稳定、按相对路径排序、跳过非模型后缀
  * --verify：一致 → 0；内容篡改 → 1；文件缺失 → 1；无 manifest → 2（跳过语义）
  * 权重目录未配置 → 2（不把"没配置"误判成"校验失败"）
全部用 tmp_path 造小文件，不触碰真实权重。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import verify_model_hashes as vmh


@pytest.fixture
def model_tree(tmp_path):
    """造一棵最小权重树：两个模型文件 + 一个应被忽略的日志。"""
    root = tmp_path / "model"
    (root / "diffusion_models").mkdir(parents=True)
    (root / "diffusion_models" / "a.safetensors").write_bytes(b"weights-a")
    (root / "config.json").write_text('{"model": "h3"}')
    (root / "noise.log").write_text("should be ignored")
    return root


def _run(capsys, monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["verify_model_hashes.py"] + args)
    code = vmh.main()
    return code, capsys.readouterr().out


def test_generate_then_verify_ok(capsys, monkeypatch, model_tree, tmp_path):
    """生成 → 校验：一致退出 0，且忽略非模型后缀文件。"""
    manifest = tmp_path / "m.sha256"
    code, out = _run(capsys, monkeypatch, ["--generate", "--model-dir", str(model_tree), "--manifest", str(manifest), "--quiet"])
    assert code == 0, out

    entries = vmh.parse_manifest(manifest.read_text(encoding="utf-8"))
    assert set(entries) == {"config.json", "diffusion_models/a.safetensors"}
    assert "noise.log" not in entries

    code, out = _run(capsys, monkeypatch, ["--verify", "--model-dir", str(model_tree), "--manifest", str(manifest), "--quiet"])
    assert code == 0, out
    assert "PASS" in out


def test_verify_detects_tampering(capsys, monkeypatch, model_tree, tmp_path):
    """权重被篡改 → 退出 1，报 CHANGED。"""
    manifest = tmp_path / "m.sha256"
    _run(capsys, monkeypatch, ["--generate", "--model-dir", str(model_tree), "--manifest", str(manifest), "--quiet"])
    (model_tree / "diffusion_models" / "a.safetensors").write_bytes(b"tampered!!")

    code, out = _run(capsys, monkeypatch, ["--verify", "--model-dir", str(model_tree), "--manifest", str(manifest), "--quiet"])
    assert code == 1
    assert "CHANGED" in out


def test_verify_detects_missing(capsys, monkeypatch, model_tree, tmp_path):
    """权重文件缺失 → 退出 1，报 MISSING。"""
    manifest = tmp_path / "m.sha256"
    _run(capsys, monkeypatch, ["--generate", "--model-dir", str(model_tree), "--manifest", str(manifest), "--quiet"])
    (model_tree / "config.json").unlink()

    code, out = _run(capsys, monkeypatch, ["--verify", "--model-dir", str(model_tree), "--manifest", str(manifest), "--quiet"])
    assert code == 1
    assert "MISSING" in out


def test_verify_without_manifest_skips(capsys, monkeypatch, model_tree, tmp_path):
    """未生成基线 → 退出 2（跳过），不把"没有基线"当失败。"""
    code, out = _run(capsys, monkeypatch, ["--verify", "--model-dir", str(model_tree), "--manifest", str(tmp_path / "nope.sha256")])
    assert code == 2
    assert "SKIP" in out


def test_model_dir_missing_skips(capsys, monkeypatch, tmp_path):
    """权重目录不可用 → 退出 2。"""
    code, out = _run(capsys, monkeypatch, ["--generate", "--model-dir", str(tmp_path / "not-exist"), "--manifest", str(tmp_path / "m.sha256")])
    assert code == 2
    assert "SKIP" in out


def test_generate_on_empty_dir_skips(capsys, monkeypatch, tmp_path):
    """空目录不生成空 manifest（避免"空基线=校验通过"的假绿）。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out = _run(capsys, monkeypatch, ["--generate", "--model-dir", str(empty), "--manifest", str(tmp_path / "m.sha256")])
    assert code == 2
    assert not (tmp_path / "m.sha256").exists()
