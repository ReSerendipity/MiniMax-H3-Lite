"""
MM·H3 工作台 — 内容来源标识模块（开发者内部功能，对用户完全无感）

设计目标：
- 在生成视频的亮度平面（yuv420p 直连，不经 RGB 往返）嵌入不可感知的
  DCT 频域来源标识；图像/帧级 API 仍为 RGB→Y 通道；
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
_FRAME_INTERVAL = 1          # 每 N 帧嵌入一次；=1 使每帧都携带副本（投票副本数翻倍，
                             # 对消帧间预测对固定空间位置的系统性抹除）  # noqa: E114,E116
_MARGIN_FACTOR = 4.0         # 嵌入后在 uint8 域复核时要求的最小 |D23-D32| 裕度（×DELTA）
_MAX_FIX_ROUNDS = 5          # 单块复核-修正最大轮数（增益逐轮倍增）
_MAX_CHUNK_FRAMES = 64       # 提取端最多累加的已嵌入帧数（多帧分段重建上限）
_MAX_PAYLOAD_BITS = 4096     # 分段方案支持的载荷位上限（决定提取端解码帧数）


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


def _block_grid(h: int, w: int) -> list[tuple[int, int]]:
    """帧内全部可用 8x8 块原点（与 embed/extract 扫描顺序一致）。"""
    return [(by, bx)
            for by in range(0, h - BLOCK + 1, BLOCK)
            for bx in range(0, w - BLOCK + 1, BLOCK)]


def _frame_capacity(h: int, w: int) -> int:
    """单帧可携带的位数（= 可用 8x8 块数，每块 1 bit）。"""
    return len(_block_grid(h, w))


# --------------------------------------------------------------------------
# 帧级嵌入 / 提取
# --------------------------------------------------------------------------

def embed_frame_bits(rgb: np.ndarray, bits: list[int]) -> np.ndarray:
    """在单帧 RGB ndarray (H, W, 3) 中嵌入位序列，返回新数组（不改输入）。

    实现要点（2026-09-18 修复，解码规则 dct[2,3] > dct[3,2] 不变）：
    旧版在 float 域修改 DCT 后把 delta_y 半强度同加三通道再各自 uint8 截断，
    解码端实测 |D23-D32| 在纯色/平坦图像上直接归零（±0.5 量化噪声 ≫ 半强度
    扰动），随机内容下裕度也远低于 DELTA 设计值。新版逐块构造目标 DCT 差值的
    空间图案（同加三通道 → Y 变化即图案值，BT.601 权重和为 1），写入 uint8 帧后
    用与解码端完全同构的 Y 域 DCT **复核符号与裕度**，不达标则按实测差值追加
    修正并逐轮倍增增益（克服 uint8 取整死区），保留历史最优轮。
    对本变换基不严格可逆的残差由复核环自适应补偿。
    """
    out = rgb.astype(np.uint8, copy=True)
    h, w = out.shape[:2]
    min_margin = DELTA * _MARGIN_FACTOR
    target = min_margin * 2.0
    # 单位图案：D(P)[2,3]-D(P)[3,2] = q 当 P = q·(b2⊗b3 - b3⊗b2)/16 且只考 AC 项；
    # 这里合并为 need（希望差值的改变量）→ pat = need·S，S 推导见 GOTCHAS。
    u = np.arange(BLOCK)
    b2 = np.cos(np.pi * (2 * u + 1) * 2 / (2 * BLOCK))
    b3 = np.cos(np.pi * (2 * u + 1) * 3 / (2 * BLOCK))
    S = (np.outer(b2, b3) - np.outer(b3, b2)) / 16.0
    for (by, bx), bit in zip(_block_grid(h, w), bits):
        rows = slice(by, by + BLOCK)
        cols = slice(bx, bx + BLOCK)
        sign = 1.0 if bit else -1.0
        best_rgb, best_score, last_score = out[rows, cols].copy(), -np.inf, None
        for round_no in range(_MAX_FIX_ROUNDS):
            Y = _y_channel(out).astype(np.float64)
            D = _dct2(Y[rows, cols])
            diff = D[2, 3] - D[3, 2]
            last_score = sign * diff
            if last_score > best_score:
                best_score, best_rgb = last_score, out[rows, cols].copy()
            if last_score >= min_margin:
                break
            need = sign * target - diff
            pat = need * S * (2.0 ** round_no)
            t = np.rint(pat).astype(np.int16)
            blk = out[rows, cols, :].astype(np.int16) + t[:, :, None]
            out[rows, cols, :] = np.clip(blk, 0, 255).astype(np.uint8)
        if last_score is not None and last_score < best_score:
            out[rows, cols, :] = best_rgb
    return out


def embed_frame_rgb(rgb: np.ndarray, payload_bytes: bytes) -> np.ndarray:
    """在单帧 RGB ndarray 中嵌入完整载荷字节（公开 API，行为同旧版签名）。"""
    return embed_frame_bits(rgb, _bits(payload_bytes))


def embed_luma_bits(y: np.ndarray, bits: list[int], rot: int = 0,
                    ncap: int | None = None) -> None:
    """在可写的 uint8 亮度平面（H, W）上就地嵌入位序列。

    视频专用主路径（2026-09-18）：编解码改走 yuv420p 直连后，嵌入对象就是
    解码端将读到的那个平面（全分辨率，不受 4:2:0 色度抽样影响）。复核-修正
    环与 RGB 版同构（目标差值 ±32，增益逐轮倍增克服 uint8 取整死区）。
    rot：本帧的块位轮转量——第 i 位写入块 (i+rot) % cap。x264 帧间预测会
    系统性抹掉静止/弱纹理区域**固定空间位置**的图案（多帧同位重复时投票
    无效，实测残余 BER 5-20%）；逐帧轮转后同一空间损伤在不同帧命中不同
    载荷位，投票误差去相关（推导与实测见 GOTCHAS）。
    """
    h, w = y.shape
    grid = _block_grid(h, w)
    cap = len(grid)
    if cap == 0:
        return
    if ncap is None or ncap > cap:
        ncap = cap
    if rot:
        seq: list[int | None] = [None] * cap
        for i, b in enumerate(bits):
            seq[(i + rot) % ncap] = b
    else:
        seq = list(bits[:ncap])
    min_margin = DELTA * _MARGIN_FACTOR
    target = min_margin * 2.0
    u = np.arange(BLOCK)
    b2 = np.cos(np.pi * (2 * u + 1) * 2 / (2 * BLOCK))
    b3 = np.cos(np.pi * (2 * u + 1) * 3 / (2 * BLOCK))
    S = (np.outer(b2, b3) - np.outer(b3, b2)) / 16.0
    for (by, bx), bit in zip(grid, seq):
        if bit is None:
            continue
        rows = slice(by, by + BLOCK)
        cols = slice(bx, bx + BLOCK)
        sign = 1.0 if bit else -1.0
        best_blk, best_score, last_score = y[rows, cols].copy(), -np.inf, None
        for round_no in range(_MAX_FIX_ROUNDS):
            D = _dct2(y[rows, cols].astype(np.float64))
            diff = D[2, 3] - D[3, 2]
            last_score = sign * diff
            if last_score > best_score:
                best_score, best_blk = last_score, y[rows, cols].copy()
            if last_score >= target:
                break
            need = sign * target - diff
            pat = need * S * (2.0 ** round_no)
            y[rows, cols] = np.clip(
                np.rint(y[rows, cols].astype(np.float64) + pat), 0, 255
            ).astype(np.uint8)
        if last_score is not None and last_score < best_score:
            y[rows, cols] = best_blk


def _luma_diffs(y: np.ndarray, ndiffs: int) -> list[float]:
    """按扫描序读亮度平面前 ndiffs 个块的带符号差值 D23-D32（软投票用）。"""
    h, w = y.shape
    diffs: list[float] = []
    yf = y.astype(np.float64)
    for by, bx in _block_grid(h, w):
        if len(diffs) >= ndiffs:
            break
        d = _dct2(yf[by:by + BLOCK, bx:bx + BLOCK])
        diffs.append(float(d[2, 3] - d[3, 2]))
    return diffs[:ndiffs]


def _soft_decode(diffs: list[list[float]], cap: int) -> str | None:
    """对已读到的各已嵌入帧差值序列，尝试分段数 L=1..n 做软投票重建。

    布局约定（与 embed_video 一致）：第 k 个已嵌入帧携带段 k % L，且该段位
    序列按 rot=k 轮转到物理块位（块 q 承载段位 (q-k) % cap）；同一段的各副
    本按载荷位累加带符号差值（软投票）。权重阶梯：先全强度（天然大差值是
    可信信息，LLR 最优），失败时逐级截幅（±64/±32/±16，防少数被预测替换的
    块以天然大差值压垮多数票）；被抹平的副本（差值≈0）自动降权。首个通
    过 CRC/HMAC 校验的组合即返回。
    """
    n = len(diffs)
    if n == 0:
        return None
    darr = np.zeros((n, cap), dtype=np.float64)
    for k, dk in enumerate(diffs):
        darr[k, :len(dk)] = dk
    # 块位 q 承载段位 (q-k) % cap（反轮转映射，对所有候选 L 相同，预计算）
    idx = (np.arange(cap)[None, :] - np.arange(n)[:, None]) % cap
    magic_bits = np.array(_bits(MAGIC + bytes([VERSION])), dtype=np.uint8)
    best_sums, best_pref = None, -1
    for clip in (None, DELTA * _MARGIN_FACTOR * 4.0,
                 DELTA * _MARGIN_FACTOR * 2.0, DELTA * _MARGIN_FACTOR):
        soft = darr if clip is None else np.clip(darr, -clip, clip)
        for L in range(1, n + 1):
            flat = (np.arange(n) % L)[:, None] * cap + idx
            sums = np.bincount(flat.ravel(), weights=soft.ravel(),
                               minlength=L * cap)
            hard = sums > 0
            res = _validate_bits(hard.astype(np.uint8))
            if res is not None:
                return res
            # 追踪“最接近成功”的候选（magic+version 前缀吻合度），兼做翻转搜索底座
            pref = int(np.count_nonzero(
                hard[:len(magic_bits)] == magic_bits.astype(bool)))
            if pref > best_pref:
                best_pref, best_sums = pref, sums
    # 翻转兜底：对最不确定（|票值|最小）的 8 位试全部 2^8 种翻转组合，过 CRC 即采纳；
    # 只兜住“差 1-5 位”的近失败样本，不改变完整载荷的正常路径。仅在 magic
    # 前缀完全吻合（best_pref 满配）时才尝试，避免在完全错位数据上撞库。
    if best_sums is not None and best_pref == len(magic_bits):
        hard = (best_sums > 0).astype(np.uint8)
        # 候选位限定在载荷覆盖范围内（长度字段在前 9 字节里，先试读）；
        # 解析失败则退回全范围。
        limit = len(best_sums)
        if limit >= 72:
            ln = int(struct.unpack(">I", np.packbits(
                hard[40:72]).tobytes())[0])
            est = (13 + ln) * 8
            if 72 <= est <= limit:
                limit = est
        cands = np.argsort(np.abs(best_sums[:limit]))[:8]
        for mask in range(1, 1 << len(cands)):
            trial = hard.copy()
            for i in range(len(cands)):
                if mask >> i & 1:
                    trial[cands[i]] ^= 1
            res = _validate_bits(trial)
            if res is not None:
                return res
    return None


def _validate_bits(bits: list[int] | np.ndarray) -> str | None:
    """把累加的位流（MSB 优先）转成字节并走既有校验；不完整/损坏返回 None。"""
    if len(bits) < 64:
        return None
    arr = np.ascontiguousarray(bits, dtype=np.uint8)
    raw = np.packbits(arr[:(len(arr) // 8) * 8]).tobytes()
    return _validate(raw)


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
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
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
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    ).stdout.strip()
    return out == "audio"


def embed_video(src: str, dst: str, payload: str, source_id: str = SOURCE_ID) -> bool:
    """对视频嵌入帧级来源标识（解码→逐帧亮度面嵌入→重编码，保留音轨）。

    失败返回 False，不抛异常。2026-09-18 起编解码直连 yuv420p（不再经
    rgb24 往返）：避开纯色/暗色像素的通道截断不对称与 4:2:0 色度抽样对
    扰动的破坏，提取端读的正是嵌入写入的那个亮度平面。
    """
    src_p, dst_p = Path(src), Path(dst)
    if not src_p.exists():
        return False
    w, h, fps = _probe(src_p)
    if w <= 0 or h <= 0 or fps <= 0 or w % 2 or h % 2:
        return False
    pbytes = _build_payload(source_id, payload, int(time.time()))
    bits = _bits(pbytes)
    cap = _frame_capacity(h, w)
    if cap < 1 or len(bits) > _MAX_PAYLOAD_BITS:
        return False  # 超出提取端保证覆盖的载荷上限（与 extract_video 对齐）
    # 逻辑容量：大帧只用前 _MAX_PAYLOAD_BITS 个块承载（提取端同参数），
    # 分段与轮转均基于 ncap，保证两端映射一致。
    ncap = min(cap, _MAX_PAYLOAD_BITS)
    if len(bits) > ncap:
        if ncap < 8:
            return False  # 单帧连一字节都装不下，无法分段承载
        segs = [bits[i:i + ncap] for i in range(0, len(bits), ncap)]
    else:
        segs = [bits]  # 单帧方案：载荷整体重复到多个已嵌入帧
    tmp_v = dst_p.with_name(dst_p.stem + "_wm_tmp.mp4")
    tmp_a = dst_p.with_name(dst_p.stem + "_wm_audio.m4a")
    try:
        dec = subprocess.run(  # nosec
            ["ffmpeg", "-v", "error", "-i", str(src_p), "-f", "rawvideo",
             "-pix_fmt", "yuv420p", "-"],
            capture_output=True, timeout=1800,
        )
        if dec.returncode != 0:
            return False
        raw = bytearray(dec.stdout)
        frame_bytes = w * h * 3 // 2
        y_size = w * h
        total = len(raw) // frame_bytes
        embedded_total = (total + _FRAME_INTERVAL - 1) // _FRAME_INTERVAL
        # 分段轮铺：第 e 个已嵌入帧携带 segs[e % L]，自然重复到所有可用帧；
        # x264 会抹掉弱纹理块的图案（实测 crf18 硬判 BER 8-25%，单靠幅度无法
        # 对抗），靠多帧副本的软投票（带符号差值累加）+ mbtree=0 恢复（见 GOTCHAS：
        # mbtree 的跨帧码率传播会系统性压多周期微图案，关掉后残余误码归零）。
        if len(segs) > embedded_total:
            # 视频太短，至少一份完整分段载荷都放不下：显式失败，绝不静默截断
            return False
        enc = subprocess.Popen(  # nosec
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p",
             "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-x264-params", "mbtree=0", "-an", str(tmp_v)],
            stdin=subprocess.PIPE,
        )
        assert enc.stdin is not None  # nosec B101
        e = 0
        for i in range(total):
            base = i * frame_bytes
            if i % _FRAME_INTERVAL == 0:
                y = np.frombuffer(raw, dtype=np.uint8,
                                  count=y_size, offset=base).reshape(h, w)
                embed_luma_bits(y, segs[e % len(segs)], rot=e, ncap=ncap)
                e += 1
            enc.stdin.write(bytes(raw[base:base + frame_bytes]))
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
    """从视频提取来源标识文本；无/损坏返回 None。

    2026-09-18：流式读取已嵌入帧的带符号差值，用 _soft_decode 多帧软投票
    重建载荷（分段数 L 由小到大尝试）；大分辨率单帧方案通常首帧即命中。
    """
    p = Path(src)
    if not p.exists():
        return None
    try:
        w, h, _ = _probe(p)
        if w <= 0 or h <= 0:
            return None
        cap = _frame_capacity(h, w)
        if cap < 1:
            return None
        # 逻辑容量：单帧方案下载荷至多 _MAX_PAYLOAD_BITS 位，只需读前这么多
        # 块；分段方案（cap < 上限）自然等于整帧 cap。
        ncap = min(cap, _MAX_PAYLOAD_BITS)
        # 解码帧数预算：大帧必为单帧方案，16 帧投票足够；小帧靠多副本，
        # 读到上限（实测 96x96 级分段需 ≥32 帧，见 GOTCHAS）。
        e_max = 16 if cap >= _MAX_PAYLOAD_BITS else _MAX_CHUNK_FRAMES
        check_points = {8, 12, 16, 24, 32, 48, e_max}
        proc = subprocess.Popen(  # nosec
            ["ffmpeg", "-v", "error", "-i", str(p), "-f", "rawvideo",
             "-pix_fmt", "yuv420p", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        frame_bytes = w * h * 3 // 2
        y_size = w * h
        diffs: list[list[float]] = []
        idx = 0
        try:
            while len(diffs) < e_max:
                buf = proc.stdout.read(frame_bytes)
                if buf is None or len(buf) < frame_bytes:
                    break
                if idx % _FRAME_INTERVAL == 0:
                    y = np.frombuffer(buf, dtype=np.uint8,
                                      count=y_size).reshape(h, w)
                    diffs.append(_luma_diffs(y, ncap))
                    if len(diffs) in check_points:
                        res = _soft_decode(diffs, ncap)
                        if res is not None:
                            return res
                idx += 1
        finally:
            try:
                proc.stdout.close()
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    proc.kill()
        return None
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
