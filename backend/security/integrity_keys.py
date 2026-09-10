#!/usr/bin/env python3
"""backend/security/integrity_keys.py — 代码完整性签名密钥管理（任务书 R10）。

背景（报告2 §二防线2 / GOTCHAS #97/#98）：
- 完整性清单与被校验代码同目录，攻击者若能改代码就能同步改清单——
  签名把信任根外移：签发机持 Ed25519 私钥（data/.manifest_signing_key，
  不入库不入包），发布产物内置公钥（仅可验签、公开无害）；
- HMAC-SHA256 对称回退（data/.mmh3_secret）供无 Ed25519 私钥的开发机
  自验用；发布链强制 Ed25519（报告2 §3.2 SOP-19：CI Secret 注入，
  否掉打包机自签）。

密钥分发决策（任务书 §4 避坑 #1/#2，2026-09-10 定案）：
- 私钥：签发机本地 data/.manifest_signing_key + GitHub Secret
  （MMH3_MANIFEST_SIGNING_KEY_B64，待人工设置）+ 离线备份（SOP-17）；
- 公钥：backend/security/manifest_signing_public_key.pem 随代码入库；
- enforce 开启以「公钥配套闸门」为前提：签名脚本签名后立即用内置公钥
  回验，错配即 fail（GOTCHAS #97）。
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import os
import secrets
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

# 密钥/签名文件命名（与 SeedVR2 家族一致，便于跨项目复用）
_PRIVATE_KEY_NAME = ".manifest_signing_key"
_PUBLIC_KEY_NAME = "manifest_signing_public_key.pem"
_ED25519_SUFFIX = ".sig.ed25519"
_SIGNATURE_SUFFIX = ".sig"
_HMAC_SECRET_NAME = ".mmh3_secret"  # nosec B105 - 密钥文件名常量（gitignore 不入库），非密码字符串
_MMH3_ROOT = Path(__file__).resolve().parents[2]  # 仓库根


def project_root() -> Path:
    return _MMH3_ROOT


def manifest_private_key_path() -> Path:
    """清单签名私钥路径（仓库根 data/，gitignore，绝不入包）。"""
    return _MMH3_ROOT / "data" / _PRIVATE_KEY_NAME


def manifest_public_key_path() -> Path:
    """内置公钥路径（security/ 目录，随代码入库，公开无害仅用于验签）。"""
    return Path(__file__).parent / _PUBLIC_KEY_NAME


def hmac_secret_path() -> Path:
    """HMAC 回退密钥路径（仓库根 data/，gitignore）。"""
    return _MMH3_ROOT / "data" / _HMAC_SECRET_NAME


def harden_secret_file_permissions(path: Path) -> bool:
    """收紧密钥文件权限（POSIX 0600；Windows icacls 去继承仅当前用户）。

    临时目录内跳过 icacls（避免破坏 pytest 临时目录回收，WinError 5）。
    """
    if not path.exists():
        return False
    try:
        if os.name == "nt":
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            temp_env = os.environ.get("TEMP", "") or os.environ.get("TMP", "")
            temp_root = os.path.realpath(temp_env) if temp_env else ""
            if temp_root and os.path.realpath(str(path)).startswith(temp_root):
                return True
            try:
                import subprocess  # nosec B404 - 仅 icacls 固定参数、list 形参无 shell
                subprocess.run(  # nosec
                    ["icacls", str(path), "/inheritance:r", "/grant:r",
                     f"{os.environ.get('USERNAME', '*')}:F"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=10, check=False,
                )
            except Exception as e:  # noqa: BLE001 - 平台能力缺失不阻断
                logger.debug("Windows 密钥权限收紧跳过: %s", e)
            return True
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return True
    except Exception as e:  # noqa: BLE001 - 权限收紧失败不阻断业务
        logger.warning("密钥文件权限收紧失败: %s (%s)", path, e)
        return False


def generate_manifest_signing_keypair(force: bool = False) -> tuple[Path, Path]:
    """生成 Ed25519 清单签名密钥对（签发机运行一次）。

    Returns:
        (私钥路径, 公钥路径)。

    Raises:
        FileExistsError: 私钥已存在且 force=False。
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    priv_path = manifest_private_key_path()
    if priv_path.exists() and not force:
        raise FileExistsError(
            f"清单签名私钥已存在: {priv_path}（如需轮换请用 --force，并重签历史发布清单）"
        )

    private_key = ed25519.Ed25519PrivateKey.generate()
    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_pem)
    harden_secret_file_permissions(priv_path)
    pub_path = manifest_public_key_path()
    pub_path.write_bytes(pub_pem)
    logger.info("清单签名密钥对已生成: 私钥=%s 公钥=%s", priv_path, pub_path)
    return priv_path, pub_path


def _normalize(data: bytes) -> bytes:
    """行尾归一化：删除 \r，使 Windows CRLF 与 Linux LF 得到同一签名输入。"""
    return data.translate(None, b"\r")


def sign_manifest_ed25519(
    manifest_path: str | os.PathLike,
    private_key_path: str | os.PathLike | None = None,
) -> Path | None:
    """用 Ed25519 私钥为清单签名（写入 .sig.ed25519）。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    p = Path(manifest_path)
    if not p.exists():
        return None
    priv_path = manifest_private_key_path() if private_key_path is None else Path(private_key_path)
    if not priv_path.exists():
        logger.warning("清单签名私钥不存在: %s", priv_path)
        return None
    try:
        private_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            logger.warning("清单签名私钥非 Ed25519，拒绝签名")
            return None
        sig = private_key.sign(_normalize(p.read_bytes()))
    except Exception as e:  # noqa: BLE001
        logger.warning("Ed25519 签名失败: %s", e)
        return None
    sig_path = Path(f"{p}{_ED25519_SUFFIX}")
    sig_path.write_bytes(sig)
    return sig_path


def verify_manifest_signature_ed25519(
    manifest_path: str | os.PathLike,
    public_key_path: str | os.PathLike | None = None,
) -> bool:
    """用内置公钥验证清单的 Ed25519 签名（验签失败返回 False，不抛异常）。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    p = Path(manifest_path)
    pub_path = manifest_public_key_path() if public_key_path is None else Path(public_key_path)
    sig_path = Path(f"{p}{_ED25519_SUFFIX}")
    if not p.exists() or not pub_path.exists() or not sig_path.exists():
        return False
    try:
        public_key = serialization.load_pem_public_key(pub_path.read_bytes())
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            return False
        public_key.verify(sig_path.read_bytes(), _normalize(p.read_bytes()))
        return True
    except Exception as e:  # noqa: BLE001 - 任何验签失败都视为无效
        logger.debug("Ed25519 清单验签失败: %s", e)
        return False


# ---------------------------------------------------------------------------
# HMAC-SHA256 对称回退（开发机无 Ed25519 私钥时自验用；发布链不依赖）
# ---------------------------------------------------------------------------

def get_hmac_secret() -> bytes:
    """获取/生成 HMAC 回退密钥（data/.mmh3_secret，32 字节 hex）。"""
    p = hmac_secret_path()
    if p.exists():
        try:
            key = bytes.fromhex(p.read_text(encoding="utf-8").strip())
            if len(key) == 32:
                harden_secret_file_permissions(p)
                return key
        except (OSError, ValueError):
            pass
    key = secrets.token_bytes(32)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(key.hex(), encoding="utf-8")
    harden_secret_file_permissions(p)
    return key


def sign_manifest_hmac(manifest_path: str | os.PathLike) -> Path | None:
    """HMAC-SHA256 签名清单（写入 .sig，开发机回退档）。"""
    p = Path(manifest_path)
    if not p.exists():
        return None
    digest = hmac.new(get_hmac_secret(), _normalize(p.read_bytes()), hashlib.sha256).hexdigest()
    sig_path = Path(f"{p}{_SIGNATURE_SUFFIX}")
    sig_path.write_text(digest + "\n", encoding="utf-8")
    return sig_path


def verify_manifest_signature_hmac(manifest_path: str | os.PathLike) -> bool:
    """HMAC 验签（开发机回退档；密钥缺失返回 False）。"""
    p = Path(manifest_path)
    sig_path = Path(f"{p}{_SIGNATURE_SUFFIX}")
    if not p.exists() or not sig_path.exists():
        return False
    try:
        expected = sig_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not expected:
        return False
    with contextlib.suppress(OSError):
        return hmac.compare_digest(
            hmac.new(get_hmac_secret(), _normalize(p.read_bytes()), hashlib.sha256).hexdigest(),
            expected,
        )
    return False
