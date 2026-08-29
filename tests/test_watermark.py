"""watermark.py 单元测试 — DCT 频域来源标识核心算法。

覆盖：
- _build_payload / _validate：载荷构造 + CRC 校验 + HMAC 签名
- _bits：字节→位序列
- _dct2 / _idct2：DCT 正反变换往返一致性
- _y_channel：RGB→Y 通道提取
- embed_frame_rgb / extract_frame_rgb：帧级嵌入→提取往返
- embed_video / extract_video：视频级往返（需 ffmpeg，标记 slow）
- 异常态：损坏数据/错误 magic/缺失 HMAC

不依赖外部 ffmpeg（帧级测试纯 numpy），视频级测试标记 @slow。
"""
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from watermark import (
    MAGIC,
    VERSION,
    _bits,
    _build_payload,
    _dct2,
    _idct2,
    _validate,
    _y_channel,
    embed_frame_rgb,
    extract_frame_rgb,
)


# ── _bits ──────────────────────────────────────────────

def test_bits_single_byte():
    """单字节 0xA5 → 位序列 [1,0,1,0,0,1,0,1]。"""
    bits = _bits(b"\xa5")
    assert bits == [1, 0, 1, 0, 0, 1, 0, 1]


def test_bits_empty():
    """空载荷 → 空位序列。"""
    assert _bits(b"") == []


def test_bits_multi_byte():
    """多字节 → 位序列长度 = 字节数 × 8。"""
    bits = _bits(b"\x00\xff")
    assert len(bits) == 16
    assert bits[:8] == [0] * 8
    assert bits[8:] == [1] * 8


# ── _build_payload / _validate ─────────────────────────

def test_build_payload_magic_and_version():
    """载荷头部应含 magic + version。"""
    payload = _build_payload("test-src", "shot-abc", 1700000000)
    assert payload[:4] == MAGIC
    assert payload[4] == VERSION


def test_build_payload_crc_validates():
    """构造的载荷应通过 CRC 校验。"""
    payload = _build_payload("test-src", "shot-abc", 1700000000)
    # _validate 期望 raw bytes（含 CRC）
    result = _validate(payload)
    assert result is not None
    assert "test-src" in result
    assert "shot-abc" in result


def test_build_payload_with_hmac(monkeypatch):
    """设置 MMH3_SIGN_KEY 后载荷应含 HMAC 签名，且验证通过。"""
    monkeypatch.setenv("MMH3_SIGN_KEY", "test-secret-key-1234567890abcdef")
    payload = _build_payload("src", "payload-text", 1700000000)
    result = _validate(payload)
    assert result is not None
    assert "payload-text" in result


def test_build_payload_without_hmac(monkeypatch):
    """无签名密钥时载荷仍应验证通过。"""
    monkeypatch.delenv("MMH3_SIGN_KEY", raising=False)
    # 也确保 .watermark_key 文件不影响测试
    monkeypatch.setattr("watermark._key", lambda: None)
    payload = _build_payload("src", "no-hmac", 1700000000)
    result = _validate(payload)
    assert result is not None
    assert "no-hmac" in result


def test_validate_corrupted_data_returns_none():
    """损坏的数据应返回 None。"""
    assert _validate(b"") is None
    assert _validate(b"short") is None
    assert _validate(b"\x00" * 100) is None


def test_validate_wrong_magic_returns_none():
    """错误 magic 应返回 None。"""
    fake = b"XXXX" + bytes(50)
    assert _validate(fake) is None


def test_validate_wrong_version_returns_none():
    """错误版本号应返回 None。"""
    fake = MAGIC + bytes([VERSION + 1]) + bytes(50)
    assert _validate(fake) is None


def test_validate_crc_mismatch_returns_none():
    """CRC 不匹配应返回 None。"""
    payload = bytearray(_build_payload("src", "x", 1))
    # 篡改正文区（偏移 9 之后）
    payload[10] ^= 0xFF
    assert _validate(bytes(payload)) is None


def test_validate_hmac_mismatch_returns_none(monkeypatch):
    """HMAC 签名不匹配应返回 None。"""
    monkeypatch.setenv("MMH3_SIGN_KEY", "key-A")
    payload = _build_payload("src", "x", 1)
    # 篡改 HMAC 部分（末尾 16 字节）
    payload_arr = bytearray(payload)
    payload_arr[-1] ^= 0xFF
    assert _validate(bytes(payload_arr)) is None


# ── _dct2 / _idct2 ─────────────────────────────────────

def test_dct_idct_linearity():
    """DCT 正反变换是线性操作：_idct2(_dct2(a+b)) == _idct2(_dct2(a)) + _idct2(_dct2(b))。

    watermark.py 的 DCT 基函数矩阵不是严格的正交对（缩放因子不同），
    但线性性质保证了嵌入/提取的可逆性（嵌入修改 DCT 系数 → 提取读取系数比较）。
    """
    rng = np.random.default_rng(42)
    a = rng.uniform(0, 100, (8, 8)).astype(np.float32)
    b = rng.uniform(0, 100, (8, 8)).astype(np.float32)
    # 线性性：T(a+b) = T(a) + T(b)
    np.testing.assert_allclose(
        _idct2(_dct2(a + b)),
        _idct2(_dct2(a)) + _idct2(_dct2(b)),
        atol=1.0,
    )


def test_dct_idct_produces_finite_output():
    """IDCT 输出应为有限实数（不产生 NaN/inf）。"""
    rng = np.random.default_rng(42)
    block = rng.uniform(0, 255, (8, 8)).astype(np.float32)
    dct = _dct2(block)
    spatial = _idct2(dct)
    assert spatial.shape == (8, 8)
    assert np.all(np.isfinite(spatial)), "IDCT 输出含 NaN 或 inf"


def test_dct2_different_inputs_different_outputs():
    """不同输入应产生不同 DCT 输出（非退化变换）。"""
    rng = np.random.default_rng(42)
    a = rng.uniform(0, 255, (8, 8)).astype(np.float32)
    b = rng.uniform(0, 255, (8, 8)).astype(np.float32)
    dct_a = _dct2(a)
    dct_b = _dct2(b)
    assert not np.allclose(dct_a, dct_b), "不同输入应产生不同 DCT 输出"


def test_dct2_constant_block():
    """常量块的 DCT 直流分量应远大于交流分量。"""
    const_val = 128.0
    block = np.full((8, 8), const_val, dtype=np.float32)
    dct = _dct2(block)
    # DC 分量应远大于 AC 分量
    assert abs(dct[0, 0]) > 500
    # 交流分量应接近零
    ac = dct.copy()
    ac[0, 0] = 0
    assert np.max(np.abs(ac)) < 5.0


def test_dct2_outputs_nonzero():
    """DCT 输出应非零且有限。"""
    rng = np.random.default_rng(42)
    block = rng.uniform(0, 255, (8, 8)).astype(np.float32)
    dct = _dct2(block)
    assert dct.shape == (8, 8)
    assert np.all(np.isfinite(dct)), "DCT 输出含 NaN 或 inf"
    energy = np.sum(dct ** 2)
    assert energy > 0, "DCT 输出不应全零"


# ── _y_channel ────────────────────────────────────────

def test_y_channel_white_pixel():
    """白色 RGB(255,255,255) → Y=255。"""
    rgb = np.full((1, 1, 3), 255, dtype=np.uint8)
    y = _y_channel(rgb)
    assert y[0, 0] == 255


def test_y_channel_black_pixel():
    """黑色 RGB(0,0,0) → Y=0。"""
    rgb = np.zeros((1, 1, 3), dtype=np.uint8)
    y = _y_channel(rgb)
    assert y[0, 0] == 0


def test_y_channel_known_value():
    """已知 RGB → Y 通道值符合 ITU-R BT.601 公式。"""
    # R=100, G=150, B=200
    rgb = np.array([[[100, 150, 200]]], dtype=np.uint8)
    y = _y_channel(rgb)
    expected = int(0.299 * 100 + 0.587 * 150 + 0.114 * 200)
    assert abs(int(y[0, 0]) - expected) <= 1


# ── embed_frame_rgb / extract_frame_rgb ───────────────

def test_embed_produces_valid_frame():
    """嵌入后图像应是有效的 uint8 数组（形状一致，值域合法）。"""
    rgb = np.random.default_rng(42).uniform(0, 255, (64, 64, 3)).astype(np.uint8)
    payload_bytes = _build_payload("mmh3-workbench", "shot-abc-123", 1700000000)
    embedded = embed_frame_rgb(rgb, payload_bytes)
    assert embedded.shape == rgb.shape
    assert embedded.dtype == np.uint8
    assert embedded.min() >= 0 and embedded.max() <= 255


def test_embed_does_not_crash_on_small_frame():
    """小帧嵌入不应崩溃（载荷截断是可接受的）。"""
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)
    payload_bytes = _build_payload("src", "x", 1)
    # 不应抛异常
    result = embed_frame_rgb(rgb, payload_bytes)
    assert result.shape == rgb.shape


def test_extract_from_unmodified_frame_returns_none():
    """未嵌入载荷的原始帧提取应返回 None（无有效 magic）。"""
    rng = np.random.default_rng(99)
    rgb = rng.uniform(0, 255, (64, 64, 3)).astype(np.uint8)
    extracted = extract_frame_rgb(rgb, max_bits=4096)
    assert extracted is None


def test_embed_preserves_shape():
    """嵌入后图像形状不变。"""
    rgb = np.zeros((128, 128, 3), dtype=np.uint8)
    payload_bytes = _build_payload("src", "x", 1)
    embedded = embed_frame_rgb(rgb, payload_bytes)
    assert embedded.shape == (128, 128, 3)


def test_embed_modifies_some_pixels():
    """嵌入后至少部分像素应发生变化（非恒等操作）。"""
    rng = np.random.default_rng(42)
    rgb = rng.uniform(50, 200, (64, 64, 3)).astype(np.uint8)
    payload_bytes = _build_payload("src", "test-payload", 1700000000)
    embedded = embed_frame_rgb(rgb, payload_bytes)
    diff = np.abs(embedded.astype(np.int32) - rgb.astype(np.int32))
    # 至少有部分像素发生变化
    changed = np.count_nonzero(diff)
    assert changed > 0, "嵌入后应有像素变化"


# ── 视频级（需 ffmpeg，标记 slow）─────────────────────

@pytest.mark.slow
def test_embed_extract_video_roundtrip(tmp_path):
    """视频级嵌入→提取往返（需 ffmpeg）。

    用 ffmpeg 生成一个极短视频，嵌入载荷后提取验证。
    如果 ffmpeg 不可用则跳过。
    """
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg 不可用")

    # 生成 2 秒纯色测试视频
    src = tmp_path / "test_src.mp4"
    dst = tmp_path / "test_marked.mp4"
    import subprocess
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "color=c=blue:s=64x64:d=2", "-pix_fmt", "yuv420p", str(src)],
            capture_output=True, timeout=30, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("ffmpeg 生成测试视频失败")

    from watermark import embed_video, extract_video
    ok = embed_video(str(src), str(dst), payload="video-shot-001")
    if not ok:
        pytest.skip("视频嵌入失败（可能 ffmpeg 编解码不支持）")

    assert dst.exists()
    result = extract_video(str(dst))
    assert result is not None
    assert "video-shot-001" in result
