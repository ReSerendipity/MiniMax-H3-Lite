#!/usr/bin/env python3
"""Golden set 质量回归基线：录制 / 比对（MLOps 评估 P1 · 质量回归补给线）。

定位（诚实边界）：
  真机冒烟（`scripts/smoke_real.py`）只证明"能加载权重并跑通一条最短样本"，
  不能发现"能跑但画质/时长/帧率悄悄劣化"。本脚本补的是**低成本、可在 CPU 上跑的
  结构性质量基线**：时长 / 帧率 / 分辨率 / 帧数 / 抽样帧哈希。
  ⚠ 它**不是**语义质量评分（CLIP score / FVD / 人工评分）——那需要真实 GPU 反复
  生成 + 人工标定，单机工具形态下成本不合算，本脚本明确不假装覆盖。

为什么可行：seed 血缘机制落地后（同参数 + 同 seed ⇒ 可复现），抽样帧哈希才有
可比性；没有 seed 时逐帧比对恒失败，只有粗粒度指标（时长/帧率）有意义。

用法:
    python scripts/golden_compare.py record  --name t2v_smoke --video outputs/x.mp4 [--params '{"seed":42}']
    python scripts/golden_compare.py compare --name t2v_smoke --video outputs/x.mp4
    python scripts/golden_compare.py compare --name t2v_smoke --video outputs/x.mp4 --update  # 人工确认后刷新基线

退出码:
    0 = 与基线一致（或未检出超差项）
    1 = 检出回归（超差 / 基线不一致）
    2 = 跳过（无基线、无 ffprobe、视频不存在）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # nosec B404: 仅用于 ffprobe/ffmpeg 固定参数调用
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLES = 5
# 容差：容器/编码器层面的微小抖动不判回归
TOLERANCE = {
    "duration": 0.20,   # 秒
    "fps": 0.50,        # fps
    "size_ratio": 0.15,  # 文件体积相对差 15%
}


def _run(cmd: list[str], timeout: int = 60) -> str:
    """执行命令并返回 stdout（失败抛 RuntimeError）。测试可 monkeypatch 本函数。"""
    try:
        out = subprocess.run(  # nosec B603: ffprobe/ffmpeg 固定可执行名，参数全部由本脚本构造，无不可信输入
            cmd, capture_output=True, timeout=timeout, check=True)
    except FileNotFoundError as e:
        raise RuntimeError(f"缺少可执行程序：{cmd[0]}（ffmpeg/ffprobe 未安装）") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"{cmd[0]} 执行超时（{timeout}s）") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{cmd[0]} 执行失败：{(e.stderr or b'').decode('utf-8', 'ignore')[:200]}") from e
    return out.stdout.decode("utf-8", "ignore")


def probe(video: Path) -> dict:
    """ffprobe 取结构性元数据（duration / fps / width / height / nb_frames）。"""
    raw = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_frames,avg_frame_rate,duration",
        "-of", "json", str(video),
    ])
    data = json.loads(raw or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError(f"ffprobe 未解析出视频流：{video}")
    s = streams[0]
    fps = _parse_fps(s.get("avg_frame_rate"))
    duration = _to_float(s.get("duration"))
    nb_frames = _to_float(s.get("nb_frames"))
    if duration in (None, 0.0) and nb_frames and fps:
        duration = round(nb_frames / fps, 3)
    return {
        "width": int(s.get("width") or 0),
        "height": int(s.get("height") or 0),
        "fps": fps,
        "duration": duration,
        "nb_frames": int(nb_frames) if nb_frames else None,
    }


def _parse_fps(rate: str | None) -> float | None:
    """'24/1' → 24.0。"""
    if not rate or rate == "0/0":
        return None
    try:
        num, den = rate.split("/")
        return round(float(num) / float(den), 3) if float(den) else None
    except (ValueError, ZeroDivisionError):
        return None


def _to_float(v) -> float | None:
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def sample_frame_hashes(video: Path, samples: int = DEFAULT_SAMPLES, nb_frames: int | None = None) -> list[str]:
    """等距抽取 N 帧并逐帧 SHA-256（帧内容级指纹，捕捉画质/构图劣化）。

    步长由总帧数推导：``step = max(1, nb_frames // samples)``，保证样本铺满
    整条视频（固定每 100 帧取一帧会让样本全挤在片头，短片甚至取不满）。
    """
    step = max(1, (nb_frames or samples * 100) // max(1, samples))
    with tempfile.TemporaryDirectory(prefix="golden_") as tmp:
        out_tpl = str(Path(tmp) / "f%03d.png")
        _run([
            "ffmpeg", "-v", "error", "-y", "-i", str(video),
            "-vf", f"select='not(mod(n\\,{step}))'", "-vsync", "vfr",
            "-frames:v", str(samples), out_tpl,
        ], timeout=120)
        files = sorted(Path(tmp).glob("f*.png"))
        return [hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in files]


def fingerprint(video: Path, samples: int = DEFAULT_SAMPLES, params: dict | None = None) -> dict:
    """生成一条基线记录（结构指标 + 帧采样哈希 + 可选参数/seed）。"""
    meta = probe(video)
    fp = {
        "video": str(video),
        "size_bytes": video.stat().st_size,
        "width": meta["width"],
        "height": meta["height"],
        "fps": meta["fps"],
        "duration": meta["duration"],
        "nb_frames": meta["nb_frames"],
        "frame_samples": samples,
        "frame_hashes": sample_frame_hashes(video, samples, meta["nb_frames"]),
        "params": params or {},
    }
    return fp


def golden_dir() -> Path:
    """基线目录固定锚定仓库根 data/golden（脚本可在任意 cwd 调用）。"""
    return REPO_ROOT / "data" / "golden"


def baseline_path(name: str) -> Path:
    return golden_dir() / f"{name}.json"


def diff(current: dict, baseline: dict) -> list[str]:
    """比对并返回超差项描述（空列表 = 一致）。"""
    problems = []

    if baseline.get("frame_hashes") and current.get("frame_hashes"):
        if len(baseline["frame_hashes"]) != len(current["frame_hashes"]):
            problems.append(
                f"帧采样数量不一致：基线 {len(baseline['frame_hashes'])} vs 当前 {len(current['frame_hashes'])}"
            )
        else:
            for i, (b, c) in enumerate(zip(baseline["frame_hashes"], current["frame_hashes"])):
                if b != c:
                    problems.append(f"第 {i + 1} 个采样帧内容不一致（基线 {b} vs 当前 {c}）")
    elif baseline.get("frame_hashes") and not current.get("frame_hashes"):
        problems.append("当前视频未取到采样帧（ffmpeg 抽帧失败？）")

    for key, tol in (("duration", TOLERANCE["duration"]), ("fps", TOLERANCE["fps"])):
        b, c = baseline.get(key), current.get(key)
        if b is None or c is None:
            continue
        if abs(float(b) - float(c)) > tol:
            problems.append(f"{key} 超差：基线 {b} vs 当前 {c}（容差 ±{tol}）")

    for key in ("width", "height"):
        if baseline.get(key) and current.get(key) and baseline[key] != current[key]:
            problems.append(f"{key} 变化：基线 {baseline[key]} vs 当前 {current[key]}")

    b_size, c_size = baseline.get("size_bytes"), current.get("size_bytes")
    if b_size and c_size:
        ratio = abs(c_size - b_size) / b_size
        if ratio > TOLERANCE["size_ratio"]:
            problems.append(
                f"文件体积偏离基线 {ratio:.1%}（基线 {b_size}B vs 当前 {c_size}B，容差 {TOLERANCE['size_ratio']:.0%}）"
            )

    b_seed = (baseline.get("params") or {}).get("seed")
    c_seed = (current.get("params") or {}).get("seed")
    if b_seed is not None and c_seed is not None and b_seed != c_seed:
        problems.append(f"seed 不同（基线 {b_seed} vs 当前 {c_seed}）——逐帧比对在此前提下无意义")

    return problems


def cmd_record(args) -> int:
    video = Path(args.video)
    if not video.exists():
        print(f"[SKIP] 视频不存在：{video}")
        return 2
    try:
        fp = fingerprint(video, args.samples, json.loads(args.params) if args.params else None)
    except RuntimeError as e:
        print(f"[SKIP] 无法生成指纹（{e}）——golden 基线需要 ffprobe/ffmpeg")
        return 2
    baseline_path(args.name).parent.mkdir(parents=True, exist_ok=True)
    baseline_path(args.name).write_text(json.dumps(fp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 基线已录制：{baseline_path(args.name)}")
    print(f"     {fp['width']}x{fp['height']} @ {fp['fps']}fps / {fp['duration']}s / {fp['size_bytes']}B / {len(fp['frame_hashes'])} 帧采样")
    return 0


def cmd_compare(args) -> int:
    bp = baseline_path(args.name)
    if not bp.exists():
        print(f"[SKIP] 无基线：{bp}（先跑 record 录制，或显式 --update 以当前产物作为新基线）")
        return 2
    video = Path(args.video)
    if not video.exists():
        print(f"[SKIP] 视频不存在：{video}")
        return 2

    baseline = json.loads(bp.read_text(encoding="utf-8"))
    try:
        current = fingerprint(video, args.samples, json.loads(args.params) if args.params else None)
    except RuntimeError as e:
        print(f"[SKIP] 无法生成指纹（{e}）")
        return 2

    problems = diff(current, baseline)
    if not problems:
        print(f"[PASS] 与基线一致：{args.name}（{video}）")
        return 0

    if args.update:
        bp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] 已按当前产物刷新基线（人工确认后操作）：{bp}")
        return 0

    print(f"[FAIL] 检出 {len(problems)} 项偏离基线：{args.name}")
    for p in problems:
        print(f"   - {p}")
    print("       若为预期升级 → 人工确认后加 --update 刷新基线；否则按项排查依赖/权重/参数")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="MiniMax-H3 golden set 质量回归基线")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, help_text in (("record", "录制基线"), ("compare", "与基线比对")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("--name", required=True, help="基线名（data/golden/<name>.json）")
        s.add_argument("--video", required=True, help="待录制/比对的视频路径")
        s.add_argument("--samples", type=int, default=DEFAULT_SAMPLES, help=f"抽样帧数（默认 {DEFAULT_SAMPLES}）")
        s.add_argument("--params", default=None, help="生成参数 JSON（含 seed 时启用逐帧比对前提校验）")
        if name == "compare":
            s.add_argument("--update", action="store_true", help="人工确认后以当前产物刷新基线")

    args = ap.parse_args()
    return cmd_record(args) if args.cmd == "record" else cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
