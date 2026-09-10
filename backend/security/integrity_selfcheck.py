#!/usr/bin/env python3
"""backend/security/integrity_selfcheck.py — 启动时代码完整性自检（任务书 R10）。

防线（报告2 §二防线2）：清单哈希（SHA256）+ Ed25519 签名 + 启动自检 enforce。
- 验签优先 Ed25519（发布链），无私钥环境回退 HMAC（开发机自验）；
- 逐文件哈希比对采用**行尾归一化**（删除 \\r）：Windows 工作区 CRLF 与
  Linux CI LF 得到同一哈希，杜绝「本地绿 CI 红」（GOTCHAS #97 家族教训，
  实现移植自 Image_MultiModel integrity_selfcheck.py）；
- enforce=true（默认）：清单缺失 / 签名无效 / 任一受护文件哈希失配 →
  抛 RuntimeError 拒绝启动（fail-closed，不是只写日志）。

执行域（comfy_kernel，与既有 comfy-kernel-guard 三态一致）：
comfy_kernel/ 为 vendored 目录、不入版本控制（.gitignore），CI checkout
无此目录 → 其清单条目在「内核目录整体缺失」时跳过（SKIP），backend 条目
必须全部通过；本地（有内核）则逐条校验，篡改即失败。这是既有架构决策的
延续，不是削弱防线。

用法（backend/main.py startup 事件）：
    from security.integrity_selfcheck import run_startup_selfcheck
    run_startup_selfcheck(enforce=settings.INTEGRITY_ENFORCE)
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import NamedTuple

try:  # backend 顶层导入（uvicorn/运行时，main.py 已把 backend 加入 sys.path）
    from security.integrity_keys import (
        verify_manifest_signature_ed25519,
        verify_manifest_signature_hmac,
    )
except ImportError:  # 包导入（pytest/scripts，项目根在 sys.path）
    from backend.security.integrity_keys import (
        verify_manifest_signature_ed25519,
        verify_manifest_signature_hmac,
    )

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "integrity_manifest.json"
_COMFY_PREFIX = "comfy_kernel/"


class SelfCheckResult(NamedTuple):
    total: int
    passed: int
    failed: int
    skipped: int
    failed_files: list[str]
    signature_valid: bool | None


def get_manifest_path() -> Path:
    """清单文件路径（与自检模块同目录）。"""
    return Path(__file__).resolve().parent / _MANIFEST_FILENAME


def compute_file_sha256(filepath: Path) -> str:
    """计算文件 SHA256（行尾归一化：删除 \\r，CRLF/CR 折算为 LF）。

    WHY：清单首次在 Windows 工作区生成（core.autocrlf 使 .py 为 CRLF），
    Linux CI checkout 得到 LF。直接对原始字节哈希会让同一份源码在两地
    得到不同 SHA256 —— 本地自检全绿、CI 必红。删除 \\r 消除的只有行尾
    差异，任何实质内容改动（含增删空行）仍会改变哈希。
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk.translate(None, b"\r"))
    return sha256.hexdigest()


def _load_manifest(manifest_path: Path) -> dict | None:
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[SELF-CHECK] 清单文件读取失败: %s", e)
        return None


def _signature_valid(manifest_path: Path) -> bool | None:
    """清单签名有效性：Ed25519 优先，HMAC 回退；均不可用返回 None。"""
    try:
        if verify_manifest_signature_ed25519(manifest_path):
            return True
        if verify_manifest_signature_hmac(manifest_path):
            return True
    except Exception as e:  # noqa: BLE001 - 验签任何异常视为无效
        logger.debug("[SELF-CHECK] 验签异常: %r", e)
        return False
    return False


def run_startup_selfcheck(
    manifest_path: Path | None = None,
    root_dir: Path | None = None,
    enforce: bool = True,
    require_signature: bool = True,
) -> SelfCheckResult:
    """执行启动时代码完整性自检。

    Args:
        manifest_path: 清单路径；默认与模块同目录。
        root_dir: 条目解析根目录（清单条目相对仓库根）；默认仓库根。
        enforce: True 时校验失败抛 RuntimeError（拒绝启动，fail-closed）。
        require_signature: True 时清单必须带有效签名，否则视为失败。

    Returns:
        SelfCheckResult(total, passed, failed, skipped, failed_files, signature_valid)。

    Raises:
        RuntimeError: enforce=True 且 failed > 0。
    """
    manifest_path = manifest_path or get_manifest_path()
    root_dir = (root_dir or Path(__file__).resolve().parents[2]).resolve()
    kernel_present = (root_dir / "comfy_kernel").is_dir()

    manifest = _load_manifest(manifest_path)
    if manifest is None:
        msg = (
            "[SELF-CHECK] 完整性清单不存在，无法启动（fail-closed）。"
            " 请运行 `python scripts/generate_integrity_manifest.py` + "
            "`python scripts/sign_integrity_manifest.py` 生成并签名后重启。"
        )
        if enforce:
            logger.error(msg)
            raise RuntimeError(msg)
        logger.warning(msg)
        return SelfCheckResult(0, 0, 0, 0, [], None)

    sig_ok = None
    if require_signature:
        sig_ok = _signature_valid(manifest_path)
        if not sig_ok:
            msg = (
                "[SELF-CHECK] 清单签名无效（缺失/内容变更/密钥不配套），"
                "拒绝启动（fail-closed）。请检查 .sig.ed25519 与内置公钥是否配套。"
            )
            if enforce:
                logger.error(msg)
                raise RuntimeError(msg)
            logger.warning(msg)
            return SelfCheckResult(0, 0, 0, 0, [manifest_path.name], sig_ok)

    expected_hashes = manifest.get("files", {})
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        msg = "[SELF-CHECK] 清单格式无效（files 缺失或为空），拒绝启动（fail-closed）。"
        if enforce:
            logger.error(msg)
            raise RuntimeError(msg)
        logger.warning(msg)
        return SelfCheckResult(0, 0, 0, 0, [manifest_path.name], sig_ok)

    total = passed = failed = skipped = 0
    failed_files: list[str] = []
    for rel in sorted(expected_hashes):
        expected = expected_hashes[rel]
        if not isinstance(expected, str) or not expected:
            skipped += 1
            continue
        file_path = root_dir / rel
        # comfy_kernel 执行域：内核目录整体缺失时条目跳过（既有三态语义），
        # backend 条目必须全部校验。
        if rel.startswith(_COMFY_PREFIX) and not kernel_present:
            skipped += 1
            logger.info("[SELF-CHECK] 跳过 %s（comfy_kernel/ 未随 checkout 提供）", rel)
            continue
        if not file_path.exists():
            failed += 1
            failed_files.append(rel)
            logger.error("[SELF-CHECK] 受护文件缺失: %s", rel)
            continue
        total += 1
        try:
            actual = compute_file_sha256(file_path)
        except OSError as e:
            failed += 1
            failed_files.append(rel)
            logger.error("[SELF-CHECK] 无法读取 %s: %s", rel, e)
            continue
        if actual == expected:
            passed += 1
            logger.debug("[SELF-CHECK] OK %s", rel)
        else:
            failed += 1
            failed_files.append(rel)
            logger.error(
                "[SECURITY] 核心模块完整性校验失败（可能被篡改）: %s\n"
                "    期望 SHA256: %s\n    实际 SHA256: %s",
                rel, expected, actual,
            )

    result = SelfCheckResult(total, passed, failed, skipped, failed_files, sig_ok)
    if failed > 0:
        msg = (
            "[SELF-CHECK] 完整性自检失败：%d/%d 通过，失败 %d，跳过 %d\n"
            "    失败文件: %s\n"
            "    请确认是否被篡改；若为合法更新，请重算并重签清单。"
            % (passed, total, failed, skipped, ", ".join(failed_files))
        )
        if enforce:
            logger.error(msg)
            raise RuntimeError(msg)
        logger.error(msg)
    elif passed > 0:
        logger.info("[SELF-CHECK] 完整性自检通过: %d/%d（跳过 %d）", passed, total, skipped)
    return result
