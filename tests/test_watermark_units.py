"""watermark 模块补充单测（测试体系评估 P1-1 · 数据驱动补缺）。

只补纯 numpy 确定性路径（帧级往返 / 亮度平面嵌入 / 位流校验 / 密钥开关 /
侧车路径），不覆盖 ffmpeg 错误分支与 _soft_decode 多帧重建白盒（脆弱且
video 级往返已有 test_embed_extract_video_roundtrip 承接）。

契约口径（与既有 test_watermark.py 保持一致，勿改实现）：
  * _build_payload(source_id, payload_text, ts) 收文本载荷并返回完整结构字节
    （MAGIC+version+len+zlib 正文+CRC[+HMAC]）；
  * embed_frame_rgb(rgb, payload_bytes) 收的是 _build_payload 的**完整载荷字节**
    （bytes，绝不传 str——str 会触发 f"{byte:08b}" 的 ValueError）；
  * extract_frame_rgb / _validate_bits 解码出完整 "source_id|payload|ts" 字符串。
"""
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import watermark  # noqa: E402


def _rng_frame(h=64, w=64, seed=7):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def test_frame_rgb_roundtrip():
    """embed_frame_rgb → extract_frame_rgb 同帧往返还原载荷文本。

    帧级 API 嵌入的是 _build_payload 的完整结构字节：小帧（64×64=64 块=64bit）
    装不下完整载荷（最小 ~46 字节=368bit），故用 256×256（1024 块）保证往返。
    """
    rgb = _rng_frame(h=256, w=256)
    payload = watermark._build_payload(watermark.SOURCE_ID, "hello", 1700000000)
    out = watermark.embed_frame_rgb(rgb, payload)
    assert watermark.extract_frame_rgb(out) == "mmh3-workbench|hello|1700000000"


def test_extract_frame_short_returns_none():
    """小于 64 位的帧（max_bits 截断）→ None，不误报。"""
    rgb = _rng_frame()
    assert watermark.extract_frame_rgb(rgb, max_bits=8) is None


def test_frame_embed_does_not_mutate_input():
    src = _rng_frame()
    before = src.copy()
    payload_bits = watermark._bits(watermark._build_payload(watermark.SOURCE_ID, b"x", 0))
    watermark.embed_frame_bits(src, payload_bits)
    assert np.array_equal(src, before), "embed_frame_bits 不得改动输入帧"


def test_block_grid_and_capacity():
    assert watermark._block_grid(16, 16) == [(0, 0), (0, 8), (8, 0), (8, 8)]
    assert watermark._frame_capacity(16, 16) == 4
    assert watermark._block_grid(7, 7) == [] and watermark._frame_capacity(7, 7) == 0


def test_validate_bits_roundtrip_and_short():
    frame = watermark._build_payload(watermark.SOURCE_ID, "payload-x", 42)
    bits = watermark._bits(frame)
    # _validate 解码的是完整 "source_id|payload|ts" 文本（与 _build_payload 对称）
    assert watermark._validate_bits(bits) == "mmh3-workbench|payload-x|42"
    assert watermark._validate_bits(bits[:63]) is None


def test_embed_luma_signs_match_bits():
    """亮度平面嵌入后，逐块差值符号与载荷位一致且裕度达标。"""
    rng = np.random.default_rng(11)
    y = rng.integers(40, 220, size=(64, 64), dtype=np.uint8)
    bits = [1, 0, 1, 1]
    watermark.embed_luma_bits(y, bits)
    diffs = watermark._luma_diffs(y, len(watermark._block_grid(64, 64)))
    for i, b in enumerate(bits):
        assert (diffs[i] > 0) if b else (diffs[i] < 0), f"块 {i} 符号漂移: {diffs[i]}"
        assert abs(diffs[i]) >= watermark.DELTA, f"块 {i} 裕度不足: {diffs[i]}"


def test_embed_luma_no_capacity_noop():
    y = np.full((7, 7), 128, dtype=np.uint8)
    watermark.embed_luma_bits(y, [1, 0])  # cap=0 早退，不抛错不改写
    assert int(y.min()) == 128 and int(y.max()) == 128


def test_key_enabled_env_toggle(monkeypatch):
    monkeypatch.delenv("MMH3_SIGN_KEY", raising=False)
    assert watermark.key_enabled() is False
    monkeypatch.setenv("MMH3_SIGN_KEY", "k" * 8)
    assert watermark.key_enabled() is True


def test_provenance_sidecar_path_naming(tmp_path):
    p = watermark.provenance_sidecar_path(tmp_path / "out.mp4")
    assert p.name == "out.provenance.json" and p.parent == tmp_path
