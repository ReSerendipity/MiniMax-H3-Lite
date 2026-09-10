#!/usr/bin/env python3
"""完整性清单签名 / 校验（任务书 R10：Ed25519 优先，HMAC-SHA256 回退）。

发布链（推荐，报告2 §3.2 SOP-19）：
    python scripts/generate_manifest_signing_key.py     # 签发机一次性
    python scripts/generate_integrity_manifest.py       # 代码更新后重算清单
    python scripts/sign_integrity_manifest.py           # 签名（Ed25519）

校验（CI / 巡检）：
    python scripts/sign_integrity_manifest.py --verify

闸门（GOTCHAS #97）：签名后**立即用内置公钥回验** + 构建期断言
清单内 public_key_sha256 == 仓库公钥文件 SHA256——错配直接 fail，
杜绝「能签名但签出来验不过」的密钥配套事故。

退出码：0 成功；1 校验失败或文件缺失。
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.security.integrity_keys import (  # noqa: E402
    manifest_private_key_path,
    sign_manifest_ed25519,
    sign_manifest_hmac,
    verify_manifest_signature_ed25519,
    verify_manifest_signature_hmac,
)

MANIFEST_PATH = Path("backend/security/integrity_manifest.json")
PUBLIC_KEY_PATH = Path("backend/security/manifest_signing_public_key.pem")


def _sha256(p: Path) -> str:
    # 行尾归一化（删 \r）：与 generate_integrity_manifest.py 的公钥哈希同口径，
    # 避免 Windows CRLF 工作区与 Linux LF CI 算出不同值（GOTCHAS #97）
    return hashlib.sha256(p.read_bytes().translate(None, b"\r")).hexdigest()


def _public_key_gate(manifest_path: Path) -> bool:
    """构建期断言：清单内 public_key_sha256 == 仓库公钥 SHA256（GOTCHAS #97）。"""
    import json

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = payload.get("public_key_sha256", "")
    except (json.JSONDecodeError, OSError):
        return False
    if not PUBLIC_KEY_PATH.exists():
        return False
    actual = _sha256(PUBLIC_KEY_PATH)
    if declared and declared != actual:
        print(f"[FAIL] 公钥一致性闸门：清单声明 {declared} != 仓库公钥 {actual}")
        print("       公钥已轮换但清单未重算，或清单被篡改——请重跑 generate_integrity_manifest.py")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="完整性清单签名 / 校验")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH), help="清单文件路径")
    parser.add_argument("--verify", action="store_true", help="校验模式（默认签名模式）")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[FAIL] 清单文件不存在: {manifest_path}")
        print("       先运行 `python scripts/generate_integrity_manifest.py` 生成")
        return 1

    if args.verify:
        if verify_manifest_signature_ed25519(manifest_path):
            print(f"[PASS] 清单 Ed25519 签名有效: {manifest_path}")
            if not _public_key_gate(manifest_path):
                return 1
            return 0
        if verify_manifest_signature_hmac(manifest_path):
            print(f"[PASS] 清单 HMAC 签名有效（开发机回退档）: {manifest_path}")
            return 0
        sig_ed = Path(f"{manifest_path}.sig.ed25519")
        sig_hmac = Path(f"{manifest_path}.sig")
        if not sig_ed.exists() and not sig_hmac.exists():
            print(f"[FAIL] 缺少签名文件（{sig_ed} 或 {sig_hmac}），请先执行签名")
        else:
            print(f"[FAIL] 清单签名无效（内容已变更或密钥不匹配）: {manifest_path}")
        return 1

    # ── 签名模式：Ed25519 优先（发布链），无私钥回退 HMAC（开发机）──
    if not _public_key_gate(manifest_path):
        return 1

    if manifest_private_key_path().exists():
        sig_path = sign_manifest_ed25519(manifest_path)
        if sig_path is None:
            print("[FAIL] Ed25519 签名写入失败")
            return 1
        # 签名后立即用内置公钥回验——密钥错配在构建期立刻暴露（GOTCHAS #97/#98）
        if not verify_manifest_signature_ed25519(manifest_path):
            print("[FAIL] Ed25519 签名回验失败：私钥与内置公钥不匹配或签名文件异常")
            print("       请检查 data/.manifest_signing_key 与 backend/security/"
                  "manifest_signing_public_key.pem 是否配套")
            return 1
        print(f"[OK] 已签名(Ed25519): {manifest_path} -> {sig_path}")
        print("     签名后回验 PASS；公钥一致性闸门 PASS")
        return 0

    sig_path = sign_manifest_hmac(manifest_path)
    if sig_path is None:
        print("[FAIL] 签名写入失败（Ed25519 私钥与 HMAC 密钥均不可用）")
        return 1
    if not verify_manifest_signature_hmac(manifest_path):
        print("[FAIL] HMAC 签名回验失败")
        return 1
    print(f"[OK] 已签名(HMAC，开发机回退档): {manifest_path} -> {sig_path}")
    print("     提示：发布构建请先生成 Ed25519 密钥对（scripts/generate_manifest_signing_key.py）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
