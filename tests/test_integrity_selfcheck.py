"""R10 代码完整性自检单测（任务书阶段一验收 1/2/3）。

覆盖：
1. 篡改任一受护 .py 1 字节 → 自检 failed + enforce 拒绝启动（RuntimeError）；
2. 清单缺失 / 签名无效 → fail-closed 拒绝启动；
3. comfy_kernel 条目在内核目录缺失时 SKIP（不阻断），backend 条目必须全过；
4. 行尾归一化：CRLF 与 LF 内容哈希一致（Windows/Linux 同哈希）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest  # noqa: E402

from security.integrity_keys import (  # noqa: E402
    generate_manifest_signing_keypair,
    sign_manifest_ed25519,
)
from security.integrity_selfcheck import (  # noqa: E402
    compute_file_sha256,
    run_startup_selfcheck,
)


@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    """构造合成仓库：backend/ 两个模块 + comfy_kernel/ 一个入口 + 密钥/清单/签名。"""
    return _build_repo(tmp_path, monkeypatch)


def test_tamper_one_byte_enforce_blocks(tmp_path, monkeypatch):
    """篡改 1 字节 → failed + enforce=True 抛 RuntimeError。"""
    root = _build_repo(tmp_path, monkeypatch, tamper="backend/routers/system.py")
    result = run_startup_selfcheck(
        manifest_path=root / "backend" / "security" / "integrity_manifest.json",
        root_dir=root, enforce=False,
    )
    assert result.failed == 1
    assert "backend/routers/system.py" in result.failed_files
    assert result.signature_valid is True
    with pytest.raises(RuntimeError):
        run_startup_selfcheck(
            manifest_path=root / "backend" / "security" / "integrity_manifest.json",
            root_dir=root, enforce=True,
        )


def test_missing_manifest_fail_closed(tmp_path):
    """清单缺失 → enforce 拒绝启动；enforce=False 返回空结果。"""
    root = tmp_path / "repo"
    (root / "backend").mkdir(parents=True)
    with pytest.raises(RuntimeError):
        run_startup_selfcheck(
            manifest_path=root / "backend" / "security" / "integrity_manifest.json",
            root_dir=root, enforce=True,
        )
    r = run_startup_selfcheck(
        manifest_path=root / "backend" / "security" / "integrity_manifest.json",
        root_dir=root, enforce=False,
    )
    assert r.total == 0 and r.signature_valid is None


def test_invalid_signature_fail_closed(tmp_path, monkeypatch):
    """签名无效（篡改清单内容）→ fail-closed 拒绝启动。"""
    root = _build_repo(tmp_path, monkeypatch)
    manifest_path = root / "backend" / "security" / "integrity_manifest.json"
    # 篡改清单（加一个空格），签名随即失配
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
    result = run_startup_selfcheck(
        manifest_path=manifest_path, root_dir=root, enforce=False,
    )
    assert result.signature_valid is False
    with pytest.raises(RuntimeError):
        run_startup_selfcheck(manifest_path=manifest_path, root_dir=root, enforce=True)


def test_comfy_skipped_when_kernel_missing(tmp_path, monkeypatch):
    """comfy_kernel 目录缺失（CI checkout 情形）→ 条目 SKIP，backend 全过不阻断。"""
    root = _build_repo(tmp_path, monkeypatch)
    # 移除 comfy_kernel 目录（模拟无 vendored 内核的 checkout）
    import shutil
    shutil.rmtree(root / "comfy_kernel")
    result = run_startup_selfcheck(
        manifest_path=root / "backend" / "security" / "integrity_manifest.json",
        root_dir=root, enforce=True,
    )
    assert result.failed == 0
    assert result.skipped == 1
    assert result.passed == 2


def test_crlf_lf_same_hash(tmp_path):
    """行尾归一化：同一内容 CRLF 与 LF 哈希一致（GOTCHAS #97 家族）。"""
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_bytes(b"def f():\n    return 1\n")
    f2.write_bytes(b"def f():\r\n    return 1\r\n")
    assert compute_file_sha256(f1) == compute_file_sha256(f2)
    # 内容实质改动（空格）→ 哈希变化
    f3 = tmp_path / "c.py"
    f3.write_bytes(b"def f():\n    return 1 \n")
    assert compute_file_sha256(f1) != compute_file_sha256(f3)


def _build_repo(tmp_path, monkeypatch, tamper: str | None = None) -> Path:
    """构造合成仓库（复用 fixture 逻辑，支持篡改）。

    注意：必须**先**把 manifest_public_key_path patch 到临时目录再生成密钥对，
    否则 generate_manifest_signing_keypair 会把公钥写到真实仓库 security/，
    覆盖真实公钥（一次教训：测试曾污染真实公钥文件）。
    """
    root = tmp_path / "repo"
    mpath = root / "backend" / "security"
    mpath.mkdir(parents=True)
    monkeypatch.setattr("security.integrity_keys._MMH3_ROOT", tmp_path / "root_marker")
    monkeypatch.setattr("security.integrity_keys._PRIVATE_KEY_NAME", ".manifest_signing_key")
    monkeypatch.setattr("security.integrity_keys._PUBLIC_KEY_NAME", "manifest_signing_public_key.pem")
    monkeypatch.setattr(
        "security.integrity_keys.manifest_public_key_path",
        lambda: mpath / "manifest_signing_public_key.pem",
    )
    (root / "backend" / "routers").mkdir(parents=True)
    (root / "comfy_kernel").mkdir(parents=True)
    (root / "backend" / "main.py").write_text("APP = True\n", encoding="utf-8")
    (root / "backend" / "routers" / "system.py").write_text("X = 1\n", encoding="utf-8")
    (root / "comfy_kernel" / "main.py").write_text("K = 1\n", encoding="utf-8")

    priv, pub = generate_manifest_signing_keypair(force=True)
    pub_sha = compute_file_sha256(pub)

    manifest = {
        "generated_at": "2026-09-10T00:00:00+00:00",
        "public_key_sha256": pub_sha,
        "files": {
            "backend/main.py": compute_file_sha256(root / "backend" / "main.py"),
            "backend/routers/system.py": compute_file_sha256(root / "backend" / "routers" / "system.py"),
            "comfy_kernel/main.py": compute_file_sha256(root / "comfy_kernel" / "main.py"),
        },
    }
    manifest_path = mpath / "integrity_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sign_manifest_ed25519(manifest_path, priv)

    # 篡改必须在清单+签名完成后进行（清单记录的是未篡改哈希）
    if tamper:
        tgt = root / tamper
        tgt.write_bytes(tgt.read_bytes() + b" ")
    return root
