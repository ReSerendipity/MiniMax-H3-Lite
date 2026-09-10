#!/usr/bin/env python3
"""生成清单签名密钥对（任务书 R10：签发机私钥 / 发布包内置公钥）。

私钥（Ed25519 PKCS8 PEM）→ data/.manifest_signing_key（gitignore，不入库）
公钥 → backend/security/manifest_signing_public_key.pem（随代码入库，公开无害）

用法:
    python scripts/generate_manifest_signing_key.py            # 首次生成
    python scripts/generate_manifest_signing_key.py --force    # 轮换签发身份

密钥分发（任务书 §4 避坑 #1，先定密钥分发再开 enforce）：
  1. 私钥本机保留（签发机）；
  2. 设置 GitHub Secret：gh secret set MMH3_MANIFEST_SIGNING_KEY_B64 -b
     "$(python -c "import base64,pathlib;print(base64.b64encode(pathlib.Path('data/.manifest_signing_key').read_bytes()).decode())")"
  3. 离线备份私钥（保险库/加密介质，报告2 SOP-17），备份后签发机副本可删除；
  4. 轮换私钥会令旧发布清单验签失败，需同步重签存量清单再发布。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.security.integrity_keys import (  # noqa: E402
    generate_manifest_signing_keypair,
    harden_secret_file_permissions,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成清单签名密钥对（Ed25519）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的私钥（轮换签发身份）")
    args = parser.parse_args()

    try:
        priv_path, pub_path = generate_manifest_signing_keypair(force=args.force)
    except FileExistsError as e:
        print(f"[FAIL] {e}")
        return 1

    harden_secret_file_permissions(priv_path)
    print(f"[OK] 清单签名私钥: {priv_path}（仅签发机持有，绝不入库/入包）")
    print(f"[OK] 内置公钥:     {pub_path}（随代码入库，仅用于验签）")
    print("注意:")
    print("  1. 请设置 GitHub Secret MMH3_MANIFEST_SIGNING_KEY_B64（私钥 base64）;")
    print("  2. 请离线备份私钥（丢失后无法重签旧清单、无法维持后续发布验签链）;")
    print("  3. 轮换私钥会令旧发布清单验签失败，需同步重签存量清单再发布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
