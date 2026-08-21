#!/usr/bin/env python3
"""MM·H3 工作台 — Comfy 内核（B 方案）真实推理冒烟。

在同一进程内复用 ComfyUI 内核，跑通「加载单文件权重 → CLIP 编码 → 采样 → 视频/音频
解码 → ffmpeg 合成 mp4」全链路。用于在真实 GPU + 7 个单文件权重下验证 comfy 后端。

用法:
    python scripts/smoke_comfy.py                            # 默认 t2va，4s，768×768
    python scripts/smoke_comfy.py --task fl2va --seconds 4
    python scripts/smoke_comfy.py --task ref2va

产物:
    outputs/smoke_comfy.log   完整输出（含 traceback，避免被采样刷屏淹没）
    outputs/smoke_comfy.mp4   生成的带音轨视频

退出码: 0 = 通过；1 = 失败（详见日志）。
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from h3 import spec as h3  # noqa: E402
from routers.comfy_engine import run as comfy_run  # noqa: E402

OUT_DIR = PROJECT_ROOT / "outputs"
LOG = OUT_DIR / "smoke_comfy.log"


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMax-H3 Comfy 内核推理冒烟（B 方案）")
    parser.add_argument("--task", default="t2va", choices=["t2va", "fl2va", "ref2va"])
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--seconds", type=int, default=4)
    parser.add_argument("--steps", type=int, default=20)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "w", encoding="utf-8")

    def emit(msg: str) -> None:
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    mode = args.task if args.task != "t2va" else "text"
    params = {
        "task_type": h3.MODE_TO_TASK[mode],
        "mode": mode,
        "prompt": "a small cat walking on a beach at dusk, cinematic, gentle stereo waves",
        "width": args.width,
        "height": args.height,
        "num_frames": h3.frames_for_duration(args.seconds),
        "duration": args.seconds,
        "fps": h3.FPS,
        "audio_sample_rate": h3.AUDIO_SAMPLE_RATE,
        "seed": 42,
        "steps": args.steps,
        "denoise": 1.0,
        "sampler_name": h3.SAMPLER_NAME,
        "refs": [],
        "first_image": None,
        "last_image": None,
        "ref_image_size": "match",
    }
    emit(f"[smoke] task={args.task} {params['width']}x{params['height']} "
         f"num_frames={params['num_frames']} steps={args.steps}")

    t0 = time.time()
    try:
        out = comfy_run(params)
        src = Path(out)
        dst = OUT_DIR / "smoke_comfy.mp4"
        if src.exists():
            dst.write_bytes(src.read_bytes())
            emit(f"[OK] 产物: {dst} ({dst.stat().st_size} bytes)")
        else:
            emit(f"[WARN] run 返回路径不存在: {out}")
        emit(f"[OK] 冒烟通过，耗时 {time.time() - t0:.1f}s")
        return 0
    except Exception:
        traceback.print_exc(file=log)
        traceback.print_exc()
        emit(f"[FAIL] 冒烟失败，耗时 {time.time() - t0:.1f}s，详见 {LOG}")
        return 1
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
