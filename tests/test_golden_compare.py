"""golden set 质量回归基线单测（MLOps 评估 P1）。

ffprobe/ffmpeg 以桩替换（monkeypatch `golden_compare._run`），不依赖真实多媒体
工具链，也不产生真实视频。覆盖：
  * record → compare 一致：退出 0
  * 帧采样内容变化（模拟画质/构图劣化）→ 退出 1
  * 时长 / 帧率 / 分辨率 超差 → 退出 1
  * seed 不同 → 提示逐帧比对无意义（仍判 1）
  * 无基线 / 视频不存在 / ffmpeg 缺失 → 退出 2（跳过，不假绿）
  * --update：人工确认后刷新基线
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import golden_compare as gc


PROBE_JSON = json.dumps({
    "streams": [{
        "width": 1344, "height": 768, "nb_frames": "121",
        "avg_frame_rate": "24/1", "duration": "5.042",
    }]
})


@pytest.fixture
def fake_ff(monkeypatch, tmp_path):
    """桩：ffprobe 返回固定元数据；ffmpeg 按 frame_hashes 影响写出可哈希的帧文件。"""
    state = {"frames": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "cccccccccccccccc"]}

    def _run(cmd, timeout=60):
        if cmd[0] == "ffprobe":
            return PROBE_JSON
        if cmd[0] == "ffmpeg":
            out_tpl = cmd[-1]
            base = Path(out_tpl).parent
            for i, h in enumerate(state["frames"], 1):
                (base / f"f{i:03d}.png").write_text(h)
            return ""
        raise AssertionError(f"unexpected cmd: {cmd}")

    monkeypatch.setattr(gc, "_run", _run)
    monkeypatch.setattr(gc, "golden_dir", lambda: tmp_path / "golden")
    return state


@pytest.fixture
def video(tmp_path):
    p = tmp_path / "out.mp4"
    p.write_bytes(b"fake-video")
    return p


def _run_cli(capsys, monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["golden_compare.py"] + args)
    code = gc.main()
    return code, capsys.readouterr().out


def test_record_then_compare_matches(capsys, monkeypatch, fake_ff, video):
    """录制基线后，同产物比对一致 → 0。"""
    code, out = _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(video), "--samples", "3", "--params", '{"seed": 42}'])
    assert code == 0, out
    assert "基线已录制" in out

    code, out = _run_cli(capsys, monkeypatch, ["compare", "--name", "t2v", "--video", str(video), "--samples", "3", "--params", '{"seed": 42}'])
    assert code == 0, out
    assert "PASS" in out


def test_frame_content_regression_detected(capsys, monkeypatch, fake_ff, video):
    """采样帧内容变化（画质劣化）→ 1。"""
    _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(video), "--samples", "3"])
    fake_ff["frames"][1] = "dddddddddddddddd"

    code, out = _run_cli(capsys, monkeypatch, ["compare", "--name", "t2v", "--video", str(video), "--samples", "3"])
    assert code == 1
    assert "采样帧内容不一致" in out


def test_seed_mismatch_is_flagged(capsys, monkeypatch, fake_ff, video):
    """seed 不同 → 逐帧比对前提不成立，明确提示。"""
    _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(video), "--samples", "3", "--params", '{"seed": 1}'])
    code, out = _run_cli(capsys, monkeypatch, ["compare", "--name", "t2v", "--video", str(video), "--samples", "3", "--params", '{"seed": 2}'])
    assert "seed 不同" in out


def test_duration_regression_detected(capsys, monkeypatch, fake_ff, video):
    """时长超差 → 1（改 ffprobe 返回值模拟，帧内容保持不变以隔离变量）。"""
    _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(video), "--samples", "3"])

    def _stub(cmd, timeout=60):
        if cmd[0] == "ffprobe":
            return json.dumps({"streams": [{"width": 1344, "height": 768, "nb_frames": "121",
                                            "avg_frame_rate": "24/1", "duration": "9.000"}]})
        base = Path(cmd[-1]).parent
        for i, h in enumerate(fake_ff["frames"], 1):
            (base / f"f{i:03d}.png").write_text(h)
        return ""
    monkeypatch.setattr(gc, "_run", _stub)

    code, out = _run_cli(capsys, monkeypatch, ["compare", "--name", "t2v", "--video", str(video), "--samples", "3"])
    assert code == 1
    assert "duration 超差" in out


def test_no_baseline_skips(capsys, monkeypatch, fake_ff, video):
    """无基线 → 2（跳过），不把"没基线"当通过。"""
    code, out = _run_cli(capsys, monkeypatch, ["compare", "--name", "nope", "--video", str(video)])
    assert code == 2
    assert "无基线" in out


def test_video_missing_skips(capsys, monkeypatch, fake_ff, tmp_path):
    """视频不存在 → 2。"""
    code, out = _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(tmp_path / "nope.mp4")])
    assert code == 2
    assert "视频不存在" in out


def test_missing_ffprobe_skips(capsys, monkeypatch, fake_ff, video):
    """ffmpeg/ffprobe 缺失 → 2（环境跳过），不误判为质量回归失败。"""
    def _boom(cmd, timeout=60):
        raise RuntimeError("缺少可执行程序：ffprobe（ffmpeg/ffprobe 未安装）")
    monkeypatch.setattr(gc, "_run", _boom)
    code, out = _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(video)])
    assert code == 2
    assert "SKIP" in out


def test_update_refreshes_baseline(capsys, monkeypatch, fake_ff, video):
    """--update：人工确认后以当前产物刷新基线 → 0 且基线被改写。"""
    _run_cli(capsys, monkeypatch, ["record", "--name", "t2v", "--video", str(video), "--samples", "3"])
    bp = gc.golden_dir() / "t2v.json"  # golden_dir 已被 fake_ff 指向 tmp_path/golden
    fake_ff["frames"][0] = "eeeeeeeeeeeeeeee"

    code, out = _run_cli(capsys, monkeypatch, ["compare", "--name", "t2v", "--video", str(video), "--samples", "3", "--update"])
    assert code == 0, out

    import hashlib
    expect = hashlib.sha256(fake_ff["frames"][0].encode()).hexdigest()[:16]
    assert json.loads(bp.read_text(encoding="utf-8"))["frame_hashes"][0] == expect
