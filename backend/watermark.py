"""
MM·H3 工作台 — 内容来源标识模块（开发者内部功能，对用户完全无感）

设计目标：
- 在生成视频的帧（RGB→Y 通道）嵌入不可感知的 DCT 频域来源标识；
- 载荷含 magic、版本、source_id 与时间戳，可选 HMAC 签名（.watermark_key）；
- 嵌入失败绝不影响正常输出（调用方 try/except 兜底）；
- 所有日志均为 debug 级（默认不输出），任何用户可见面（页面/README/终端）
  均不出现"水印"字样。

失败策略（任务书 2026-09-10 阶段二，报告2 §六）：
- 无签名密钥（R9 默认取舍）：单次尝试、失败仅 debug 日志——保持既有
  「缺省不签名、对用户完全无感」的知情决策；
- 签名密钥启用（MMH3_SIGN_KEY/.watermark_key）：embed_video_with_policy
  执行三档失败策略——重试 1 次 → 写 .provenance.json 侧车审计（默认放行）
  → block 档直接阻断产出。禁止 fail-open 静默跳过（早期合规缺口）。
用法（开发者）：
    from backend.watermark import embed_video, extract_video
    embed_video("in.mp4", "out.mp4", payload="shot-123")
    print(extract_video("out.mp4"))
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import struct
import subprocess  # nosec B404
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MAGIC = b"MMH3"
VERSION = 1
SOURCE_ID = "mmh3-workbench"

BLOCK = 8
DELTA = 4.0
_FRAME_INTERVAL = 2          # 每 N 帧嵌入一次（解码开销折中）


# --------------------------------------------------------------------------
# 密钥与载荷
# --------------------------------------------------------------------------

def _key() -> bytes | None:
    env = os.environ.get("MMH3_SIGN_KEY")
    if env:
        return env.encode("utf-8")
    key_path = Path(__file__).resolve().parent.parent / ".watermark_key"
    if key_path.exists():
        try:
            return key_path.read_bytes().strip()
        except Exception as e:  # pragma: no cover
            logger.debug("读取签名密钥失败: %s", e)
    return None


def _build_payload(source_id: str, payload: str, ts: int) -> bytes:
    head = struct.pack(">4sB", MAGIC, VERSION)
    body = zlib.compress(f"{source_id}|{payload}|{ts}".encode("utf-8"))
    raw = head + struct.pack(">I", len(body)) + body
    crc = struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    signed = raw + crc
    key = _key()
    if key:
        signed += hmac.new(key, signed, hashlib.sha256).digest()[:16]
    return signed


def _bits(payload: bytes) -> list[int]:
    return [int(b) for byte in payload for b in f"{byte:08b}"]


# --------------------------------------------------------------------------
# DCT（8x8，手工基函数，避免额外依赖）
# --------------------------------------------------------------------------

def _dct_1d(a: np.ndarray) -> np.ndarray:
    n = a.shape[0]
    x = np.arange(n).reshape(1, -1)
    basis = np.cos(np.pi * (2 * x + 1) * x.T / (2 * n))
    return basis @ a


def _idct_1d(a: np.ndarray) -> np.ndarray:
    n = a.shape[0]
    x = np.arange(n).reshape(1, -1)
    basis = np.cos(np.pi * (2 * x + 1) * x.T / (2 * n))
    return (basis.T @ a) / (n / 2)


def _dct2(a: np.ndarray) -> np.ndarray:
    return _dct_1d(_dct_1d(a.T).T)


def _idct2(a: np.ndarray) -> np.ndarray:
    return _idct_1d(_idct_1d(a.T).T)


def _y_channel(rgb: np.ndarray) -> np.ndarray:
    return (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)


# --------------------------------------------------------------------------
# 帧级嵌入 / 提取
# --------------------------------------------------------------------------

def embed_frame_rgb(rgb: np.ndarray, payload_bytes: bytes) -> np.ndarray:
    """在单帧 RGB ndarray (H, W, 3) 中嵌入载荷，返回新数组（不改输入）。"""
    y = _y_channel(rgb).astype(np.float32)
    bits = _bits(payload_bytes)
    h, w = y.shape
    bi = 0
    for by in range(0, h - BLOCK + 1, BLOCK):
        for bx in range(0, w - BLOCK + 1, BLOCK):
            if bi >= len(bits):
                break
            dct = _dct2(y[by:by + BLOCK, bx:bx + BLOCK])
            a, b = dct[2, 3], dct[3, 2]
            if bits[bi]:
                if a <= b + DELTA:
                    a, b = b + DELTA + 1, a - DELTA - 1
            else:
                if b <= a + DELTA:
                    b, a = a + DELTA + 1, b - DELTA - 1
            dct[2, 3], dct[3, 2] = a, b
            y[by:by + BLOCK, bx:bx + BLOCK] = _idct2(dct)
            bi += 1
        if bi >= len(bits):
            break
    y = np.clip(y, 0, 255).astype(np.uint8).astype(np.float32)
    y_orig = _y_channel(rgb).astype(np.float32)
    out = rgb.astype(np.float32).copy()
    delta_y = y - y_orig
    for c in range(3):
        out[:, :, c] = np.clip(out[:, :, c] + delta_y * 0.5, 0, 255)
    return out.astype(np.uint8)


def extract_frame_rgb(rgb: np.ndarray, max_bits: int = 4096) -> str | None:
    """从单帧 RGB ndarray 中提取并校验载荷文本；失败返回 None。"""
    y = _y_channel(rgb).astype(np.float32)
    h, w = y.shape
    bits: list[int] = []
    for by in range(0, h - BLOCK + 1, BLOCK):
        for bx in range(0, w - BLOCK + 1, BLOCK):
            if len(bits) >= max_bits:
                break
            dct = _dct2(y[by:by + BLOCK, bx:bx + BLOCK])
            bits.append(1 if dct[2, 3] > dct[3, 2] else 0)
        if len(bits) >= max_bits:
            break
    if len(bits) < 64:
        return None
    raw = bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits) - 7, 8))
    return _validate(raw)


def _validate(raw: bytes) -> str | None:
    if len(raw) < 14 or raw[:4] != MAGIC or raw[4] != VERSION:
        return None
    ln = struct.unpack(">I", raw[5:9])[0]
    end = 9 + ln
    if len(raw) < end + 4:
        return None
    if zlib.crc32(raw[:end]) & 0xFFFFFFFF != struct.unpack(">I", raw[end:end + 4])[0]:
        return None
    key = _key()
    if key:
        if len(raw) < end + 20:
            return None
        if not hmac.compare_digest(raw[end + 4:end + 20],
                                   hmac.new(key, raw[:end + 4], hashlib.sha256).digest()[:16]):
            return None
    try:
        return zlib.decompress(raw[9:end]).decode("utf-8")
    except Exception:
        return None


# --------------------------------------------------------------------------
# 视频级（ffmpeg 原始流往返）
# --------------------------------------------------------------------------

def _probe(p: Path) -> tuple[int, int, float]:
    """返回 (width, height, fps)。"""
    out = subprocess.run(  # nosec
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    try:
        w, h, fr = out.split(",")
        num, den = fr.split("/")
        return int(w), int(h), float(num) / max(float(den), 1e-9)
    except Exception:
        return 0, 0, 0.0


def _has_audio(p: Path) -> bool:
    out = subprocess.run(  # nosec
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    return out == "audio"


def embed_video(src: str, dst: str, payload: str, source_id: str = SOURCE_ID) -> bool:
    """对视频嵌入帧级来源标识（解码→逐帧嵌入→重编码，保留音轨）。失败返回 False，不抛异常。"""
    src_p, dst_p = Path(src), Path(dst)
    if not src_p.exists():
        return False
    w, h, fps = _probe(src_p)
    if w <= 0 or h <= 0 or fps <= 0:
        return False
    pbytes = _build_payload(source_id, payload, int(time.time()))
    tmp_v = dst_p.with_name(dst_p.stem + "_wm_tmp.mp4")
    tmp_a = dst_p.with_name(dst_p.stem + "_wm_audio.m4a")
    try:
        dec = subprocess.run(  # nosec
            ["ffmpeg", "-v", "error", "-i", str(src_p), "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-"],
            capture_output=True, timeout=1800,
        )
        if dec.returncode != 0:
            return False
        raw = dec.stdout
        frame_bytes = w * h * 3
        total = len(raw) // frame_bytes
        enc = subprocess.Popen(  # nosec
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-an", str(tmp_v)],
            stdin=subprocess.PIPE,
        )
        assert enc.stdin is not None  # nosec B101
        for i in range(total):
            frame = np.frombuffer(raw, dtype=np.uint8, count=frame_bytes,
                                  offset=i * frame_bytes).reshape(h, w, 3)
            if i % _FRAME_INTERVAL == 0:
                frame = embed_frame_rgb(frame, pbytes)
            enc.stdin.write(frame.tobytes())
        enc.stdin.close()
        if enc.wait() != 0 or not tmp_v.exists():
            return False
        if _has_audio(src_p):
            r = subprocess.run(  # nosec
                ["ffmpeg", "-v", "error", "-y", "-i", str(src_p), "-vn",
                 "-c:a", "copy", str(tmp_a)],
                capture_output=True, timeout=600,
            )
            if r.returncode == 0 and tmp_a.exists():
                r2 = subprocess.run(  # nosec
                    ["ffmpeg", "-v", "error", "-y", "-i", str(tmp_v), "-i", str(tmp_a),
                     "-c", "copy", "-movflags", "+faststart", str(dst_p)],
                    capture_output=True, timeout=600,
                )
                if r2.returncode == 0 and dst_p.exists():
                    return True
                return False
        tmp_v.replace(dst_p)
        return dst_p.exists()
    except Exception as e:  # pragma: no cover
        logger.debug("视频来源标识嵌入异常（已忽略）: %s", e)
        return False
    finally:
        for f in (tmp_v, tmp_a):
            if f.exists():
                try:
                    f.unlink(missing_ok=True)
                except Exception:  # nosec B110 - 容忍性清理（extract 失败仅记录）
                    pass


def extract_video(src: str, max_bits: int = 4096) -> str | None:
    """从视频提取来源标识文本；无/损坏返回 None。"""
    p = Path(src)
    if not p.exists():
        return None
    try:
        w, h, _ = _probe(p)
        if w <= 0 or h <= 0:
            return None
        r = subprocess.run(  # nosec
            ["ffmpeg", "-v", "error", "-i", str(p), "-vframes", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, timeout=300,
        )
        if r.returncode != 0 or len(r.stdout) < w * h * 3:
            return None
        arr = np.frombuffer(r.stdout, dtype=np.uint8, count=w * h * 3).reshape(h, w, 3)
        return extract_frame_rgb(arr, max_bits)
    except Exception as e:  # pragma: no cover
        logger.debug("来源标识提取异常: %s", e)
        return None

# --------------------------------------------------------------------------
# 失败策略三档（任务书 2026-09-10 阶段二 / 报告2 §六：重试 → 侧车 → block）
# --------------------------------------------------------------------------


def key_enabled() -> bool:
    """签名密钥是否启用（MMH3_SIGN_KEY 或 .watermark_key 存在）。"""
    return _key() is not None


def provenance_sidecar_path(dst: Path) -> Path:
    """水印失败侧车审计文件路径（与产出同目录，<stem>.provenance.json）。"""
    return dst.with_name(dst.stem + ".provenance.json")


def write_provenance_sidecar(dst: Path, payload: str, reason: str, attempts: int) -> Path:
    """写 .provenance.json 侧车元数据（水印失败审计事件落盘）。"""
    meta = {
        "schema": 1,
        "kind": "watermark-embed-failure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": str(dst),
        "payload": payload,
        "attempts": attempts,
        "reason": reason,
        "signing_key_present": key_enabled(),
    }
    sidecar = provenance_sidecar_path(dst)
    sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sidecar


def embed_video_with_policy(
    src: str,
    dst: str,
    payload: str,
    source_id: str = SOURCE_ID,
    *,
    retries: int = 1,
    block_on_fail: bool = False,
) -> str:
    """带失败策略的来源标识嵌入（任务书阶段二）。

    无签名密钥（R9 默认）：单次尝试，返回 "ok" 或 "no_key"——不重试、不侧车、
    不阻断，保持既有「缺省不签名、对用户完全无感」的知情取舍。

    签名密钥启用：三档失败策略——
      1) 重试 retries 次（默认 1）；
      2) 仍失败：写 .provenance.json 侧车审计（默认放行，返回 "sidecar"）；
      3) block_on_fail=True（block 档）：抛 RuntimeError 阻断产出。

    返回值: "ok" | "no_key" | "sidecar"
    """
    if not key_enabled():
        return "ok" if embed_video(src, dst, payload, source_id) else "no_key"
    attempts = 0
    for _ in range(1 + retries):
        attempts += 1
        if embed_video(src, dst, payload, source_id):
            return "ok"
    reason = "embed_failed"
    if block_on_fail:
        logger.warning("来源标识嵌入失败 %d 次（block 档），阻断产出: %s", attempts, dst)
        raise RuntimeError(f"来源标识嵌入失败（block 档）：{dst}")
    sidecar = write_provenance_sidecar(Path(dst), payload, reason, attempts)
    logger.warning("来源标识嵌入失败 %d 次，已写侧车审计: %s", attempts, sidecar)
    return "sidecar"
