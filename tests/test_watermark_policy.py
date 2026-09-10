"""水印失败策略三档单测（任务书阶段二验收：重试 → 侧车 → block；无 fail-open）。

覆盖：
1. 无签名密钥（R9 默认）：单次尝试、失败不重试不侧车不阻断（知情取舍保持）；
2. 密钥启用 + 首次失败重试成功 → "ok"；
3. 密钥启用 + 全部失败 + 默认档 → "sidecar" + .provenance.json 审计落盘；
4. 密钥启用 + 全部失败 + block 档 → RuntimeError（阻断产出）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import watermark  # noqa: E402


class _FakeEmbed:
    """可编程 embed_video 桩：按 fail_times 前 N 次失败，之后成功。"""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls: list[tuple] = []

    def __call__(self, src, dst, payload, source_id=watermark.SOURCE_ID):
        self.calls.append((src, dst, payload, source_id))
        if len(self.calls) <= self.fail_times:
            return False
        Path(dst).write_bytes(b"fake-video")
        return True


def test_no_key_single_attempt_no_retry(monkeypatch, tmp_path):
    """无密钥：单次尝试，成功返回 ok；失败返回 no_key（不重试、不侧车、不阻断）。"""
    monkeypatch.delenv("MMH3_SIGN_KEY", raising=False)
    fake = _FakeEmbed(fail_times=0)
    monkeypatch.setattr(watermark, "embed_video", fake)
    dst = tmp_path / "out.mp4"
    assert watermark.embed_video_with_policy("in.mp4", str(dst), "p1") == "ok"
    assert len(fake.calls) == 1

    fake2 = _FakeEmbed(fail_times=99)
    monkeypatch.setattr(watermark, "embed_video", fake2)
    assert watermark.embed_video_with_policy("in.mp4", str(tmp_path / "x.mp4"), "p2") == "no_key"
    assert len(fake2.calls) == 1  # 无密钥不重试
    assert not (tmp_path / "x.provenance.json").exists()  # 不写侧车


def test_key_retry_then_ok(monkeypatch, tmp_path):
    """密钥启用：首次失败 → 重试成功 → ok（共 2 次尝试）。"""
    monkeypatch.setenv("MMH3_SIGN_KEY", "test-sign-key")
    fake = _FakeEmbed(fail_times=1)
    monkeypatch.setattr(watermark, "embed_video", fake)
    dst = tmp_path / "out.mp4"
    assert watermark.embed_video_with_policy("in.mp4", str(dst), "p1") == "ok"
    assert len(fake.calls) == 2
    assert not (tmp_path / "out.provenance.json").exists()


def test_key_all_fail_sidecar_default(monkeypatch, tmp_path):
    """密钥启用：全部失败 → 默认侧车档：返回 sidecar 且 .provenance.json 审计落盘。"""
    monkeypatch.setenv("MMH3_SIGN_KEY", "test-sign-key")
    fake = _FakeEmbed(fail_times=99)
    monkeypatch.setattr(watermark, "embed_video", fake)
    dst = tmp_path / "out.mp4"
    assert watermark.embed_video_with_policy("in.mp4", str(dst), "task-42") == "sidecar"
    assert len(fake.calls) == 2  # 1 次 + 重试 1 次
    sidecar = tmp_path / "out.provenance.json"
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["kind"] == "watermark-embed-failure"
    assert meta["payload"] == "task-42"
    assert meta["attempts"] == 2
    assert meta["reason"] == "embed_failed"
    assert meta["signing_key_present"] is True
    assert "generated_at" in meta and "target" in meta


def test_key_all_fail_block(monkeypatch, tmp_path):
    """密钥启用：全部失败 + block 档 → RuntimeError 阻断产出（无 fail-open）。"""
    monkeypatch.setenv("MMH3_SIGN_KEY", "test-sign-key")
    fake = _FakeEmbed(fail_times=99)
    monkeypatch.setattr(watermark, "embed_video", fake)
    dst = tmp_path / "out.mp4"
    try:
        watermark.embed_video_with_policy("in.mp4", str(dst), "task-1", block_on_fail=True)
    except RuntimeError as e:
        assert "block" in str(e)
    else:  # pragma: no cover
        raise AssertionError("block 档应抛 RuntimeError")


def test_config_env_block_flag(monkeypatch):
    """config.WATERMARK_FAIL_BLOCK 可由 MMH3_WATERMARK_FAIL_BLOCK 环境变量覆盖。"""
    import config
    monkeypatch.setenv("MMH3_WATERMARK_FAIL_BLOCK", "1")
    s = config.Settings.from_env()
    assert s.WATERMARK_FAIL_BLOCK is True
    monkeypatch.setenv("MMH3_WATERMARK_FAIL_BLOCK", "false")
    s2 = config.Settings.from_env()
    assert s2.WATERMARK_FAIL_BLOCK is False
