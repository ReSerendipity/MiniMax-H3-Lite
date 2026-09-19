#!/usr/bin/env python3
"""生成核心模块完整性清单（任务书 R10：backend 核心模块 + comfy_kernel 关键入口）。

清单 = { 相对仓库根的模块路径: SHA256 }，哈希采用**行尾归一化**
（删除 \\r，Windows CRLF 与 Linux LF 得到同一哈希——GOTCHAS #97 家族教训，
实现与 backend/security/integrity_selfcheck.py 保持一致）。

覆盖范围（对齐现有测试/安全覆盖 + R3 联动）：
- backend/ 全部核心模块（含 routers/、h3/）；
- comfy_kernel/ 关键入口（内核入口/执行器/节点/HTTP 面/R3 暴露面）——
  防内嵌内核被投毒后绕过 R3 的调用面约束。

用法:
    python scripts/generate_integrity_manifest.py

生成后必须签名：
    python scripts/sign_integrity_manifest.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent

# comfy_kernel 关键入口（R3 联动，防内嵌内核投毒）
_COMFY_CORE = [
    "main.py",
    "execution.py",
    "nodes.py",
    "server.py",
    "folder_paths.py",
    "comfy/cli_args.py",
]

# 跳过目录（缓存/构建产物）
_SKIP_DIR_PARTS = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", "node_modules"}


def compute_sha256_norm(filepath: Path) -> str:
    """SHA256（行尾归一化：删除 \\r，与自检端严格一致）。"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk.translate(None, b"\r"))
    return sha256.hexdigest()


def scan_py_tree(base: Path) -> dict[str, str]:
    """递归扫描 base 下全部 .py（排除 SKIP 目录），返回 {相对posix路径: sha256}。"""
    files: dict[str, str] = {}
    for p in sorted(base.rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if _SKIP_DIR_PARTS & set(Path(rel).parts):
            continue
        files[rel] = compute_sha256_norm(p)
    return files


def scan_comfy_core(kernel: Path) -> dict[str, str]:
    """comfy_kernel 关键入口清单（缺失的条目不写入，由调用方报告）。"""
    files: dict[str, str] = {}
    missing: list[str] = []
    for rel in _COMFY_CORE:
        p = kernel / rel
        if not p.exists():
            missing.append(rel)
            continue
        files[f"comfy_kernel/{rel}"] = compute_sha256_norm(p)
    return files, missing


def check_freshness(manifest_path: Path) -> int:
    """比对已提交清单与 backend/ 实际哈希（只读，不写文件）。

    CI / 本地钩子用它拦住「改了 backend 代码却没重算重签清单」——这类漂移会让
    enforce 模式的启动自检直接拒启。comfy_kernel 是 vendored 不入库，不参与比对。
    """
    if not manifest_path.exists():
        print(f"[FAIL] 清单不存在: {manifest_path.relative_to(ROOT)}")
        return 1
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        committed = payload["files"]
    except (KeyError, ValueError, OSError) as e:
        print(f"[FAIL] 清单无法解析: {e}")
        return 1

    actual = scan_py_tree(ROOT / "backend")
    changed = sorted(k for k, v in actual.items() if k in committed and committed[k] != v)
    unregistered = sorted(set(actual) - set(committed))
    gone = sorted(set(k for k in committed if k.startswith("backend/")) - set(actual))

    if not (changed or unregistered or gone):
        print(f"[OK] 清单新鲜度：{len(actual)} 个 backend 模块哈希一致，无未登记/无失效条目")
        return 0

    print(f"[FAIL] 清单漂移：{len(changed)} 个哈希不一致"
          f"，{len(unregistered)} 个新文件未登记，{len(gone)} 个条目已失效")
    for k in changed:
        print(f"  ~ {k}")
    for k in unregistered:
        print(f"  + {k}")
    for k in gone:
        print(f"  - {k}")
    print(f"清单 generated_at={payload.get('generated_at', '?')}")
    print("修复（签发机，需 data/.manifest_signing_key）：")
    print("  python scripts/generate_integrity_manifest.py --no-comfy")
    print("  python scripts/sign_integrity_manifest.py")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="生成核心模块完整性清单")
    parser.add_argument(
        "--no-comfy", action="store_true",
        help="不扫描 comfy_kernel（本机无 vendored 内核时用；默认缺失条目仅警告）",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="只比对已提交清单与 backend/ 实际哈希，不写文件；漂移时退出码 1",
    )
    args = parser.parse_args()

    out_dir = ROOT / "backend" / "security"
    manifest_path = out_dir / "integrity_manifest.json"

    if args.check:
        return check_freshness(manifest_path)

    out_dir.mkdir(parents=True, exist_ok=True)

    files = scan_py_tree(ROOT / "backend")
    print(f"[OK] backend 核心模块: {len(files)} 个")

    if not args.no_comfy:
        kernel = ROOT / "comfy_kernel"
        if kernel.is_dir():
            comfy_files, missing = scan_comfy_core(kernel)
            files.update(comfy_files)
            print(f"[OK] comfy_kernel 关键入口: {len(comfy_files)} 个")
            for m in missing:
                print(f"[WARN] comfy_kernel 条目缺失（未纳入清单）: {m}")
        else:
            print("[WARN] 本机无 comfy_kernel/（vendored 不入库）——未纳入清单；"
                  "部署机/有内核环境请重跑本脚本")

    pub = ROOT / "backend" / "security" / "manifest_signing_public_key.pem"
    pub_sha = compute_sha256_norm(pub) if pub.exists() else ""

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/generate_integrity_manifest.py",
        "description": "backend 核心模块 + comfy_kernel 关键入口 SHA256 完整性清单（行尾归一化）",
        "public_key_sha256": pub_sha,
        "files": files,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[OK] 已生成: {manifest_path.relative_to(ROOT)} ({len(files)} 个模块)")
    print("     下一步: python scripts/sign_integrity_manifest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
