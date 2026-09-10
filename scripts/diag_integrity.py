#!/usr/bin/env python3
"""完整性诊断脚本（任务书阶段三 P1-①：CI 只调脚本，不内联 python -c）。

逐环节打印，支持二分定位：
  1. import   — Python 环境 / cryptography 可用性
  2. manifest — 清单存在 / JSON 可解析 / 模块条目数
  3. sig      — Ed25519 签名文件存在 / 字节数
  4. pub      — 内置公钥存在 / SHA256（与清单声明一致性）
  5. VERIFY   — 清单 Ed25519 验签结果（cryptography 缺失时提示 HMAC 回退）

用法:
    python scripts/diag_integrity.py            # 全环节诊断
    python scripts/diag_integrity.py --quick    # 只做 1/5 环节（CI 冒烟用）
退出码：0 全通过；1 任一环节失败。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "backend" / "security" / "integrity_manifest.json"
PUBKEY = ROOT / "backend" / "security" / "manifest_signing_public_key.pem"
SIG = Path(f"{MANIFEST}.sig.ed25519")


def _crypto_available() -> bool:
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        return False


def check_import() -> tuple[bool, str]:
    py = sys.version.split()[0]
    crypto = _crypto_available()
    return crypto, f"python={py} cryptography={'yes' if crypto else 'NO（HMAC 回退）'}"


def check_manifest() -> tuple[bool, str]:
    if not MANIFEST.exists():
        return False, f"manifest 缺失: {MANIFEST.relative_to(ROOT)}"
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return False, f"manifest JSON 解析失败: {e}"
    files = data.get("files") or {}
    declared = data.get("public_key_sha256", "")
    return bool(files), f"manifest OK：{len(files)} 模块，public_key_sha256={declared[:16]}…"


def check_sig() -> tuple[bool, str]:
    if not SIG.exists():
        return False, f"sig.ed25519 缺失: {SIG.relative_to(ROOT)}"
    n = SIG.stat().st_size
    return n > 0, f"sig.ed25519 OK：{n} 字节"


def check_pub() -> tuple[bool, str]:
    if not PUBKEY.exists():
        return False, f"public_key 缺失: {PUBKEY.relative_to(ROOT)}"
    b = PUBKEY.read_bytes()
    sha = hashlib.sha256(b.translate(None, b"\r")).hexdigest()
    try:
        declared = (json.loads(MANIFEST.read_text(encoding="utf-8"))
                    .get("public_key_sha256", ""))
    except Exception:  # noqa: BLE001 - manifest 解析失败由环节 2 报
        declared = ""
    match = bool(declared) and declared == sha
    state = "一致" if match else "不一致！"
    return match, f"public_key OK：sha256={sha[:16]}… 与清单声明{state}"


def check_verify() -> tuple[bool, str]:
    if not _crypto_available():
        # 开发机回退：HMAC（需 data/.mmh3_secret 存在）
        from backend.security.integrity_keys import verify_manifest_signature_hmac
        ok = verify_manifest_signature_hmac(MANIFEST)
        return ok, f"VERIFY(HMAC 回退)={'PASS' if ok else 'FAIL'}"
    from backend.security.integrity_keys import verify_manifest_signature_ed25519
    ok = verify_manifest_signature_ed25519(MANIFEST)
    return ok, f"VERIFY(Ed25519)={'PASS' if ok else 'FAIL'}"


def main() -> int:
    parser = argparse.ArgumentParser(description="完整性诊断")
    parser.add_argument("--quick", action="store_true", help="只做 import/VERIFY 两环节")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    checks = [("import", check_import)]
    if not args.quick:
        checks += [("manifest", check_manifest), ("sig", check_sig), ("pub", check_pub)]
    checks.append(("VERIFY", check_verify))

    ok_all = True
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001 - 任何异常视为环节失败
            ok, detail = False, f"异常: {e!r}"
        print(f"[{'PASS' if ok else 'FAIL'}] {name:<8} {detail}")
        ok_all = ok_all and ok
    print("DIAG", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
