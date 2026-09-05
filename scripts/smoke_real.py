#!/usr/bin/env python3
"""MM·H3 真实权重推理冒烟脚本。

目的：在真实 GPU + 真实权重环境下，用最小合法配置（最短时长 5 帧）跑通
diffusers ModularPipeline 的「加载 → 采样 → 落盘」全链路，验证：

  1. 依赖组合可用（torch / diffusers==0.39.x / transformers）
  2. CUDA 可用且显存足够（默认开启 cpu offload）
  3. 权重路径正确（MMH3_MODEL_PATH 或 HF MiniMaxAI/MiniMax-H3）
  4. 推理产物为非空 mp4

用法:
    python scripts/smoke_real.py                     # 最小冒烟（5 帧，1:1 768×768）
    python scripts/smoke_real.py --width 768 --height 1344   # 自定义分辨率
    python scripts/smoke_real.py --allow-download    # 权重缺失时允许在线拉取（体积巨大，慎用）

退出码:
    0 = 冒烟通过
    2 = 环境跳过（无 CUDA / 无权重且未授权下载）
    1 = 冒烟失败（依赖缺失或推理报错）
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import settings  # noqa: E402
from h3 import spec as h3  # noqa: E402

SMOKE_OUTPUT = Path(__file__).resolve().parent.parent / "outputs" / "smoke_real.mp4"


def check_environment() -> int:
    """依赖与硬件自检，返回 2 表示跳过、1 表示失败、0 表示继续。"""
    try:
        import torch
        import diffusers  # noqa: F401
    except ImportError as e:
        print(f"[FAIL] 推理依赖缺失: {e}\n       请先安装: pip install -r requirements.txt")
        return 1

    print(f"[OK] torch {torch.__version__} / diffusers {__import__('diffusers').__version__}")
    if not torch.cuda.is_available():
        print("[SKIP] CUDA 不可用，真实推理需要 NVIDIA GPU（CPU 推理不在支持范围）")
        return 2
    props = torch.cuda.get_device_properties(0)
    print(f"[OK] CUDA 可用: {props.name} ({props.total_memory / 1024**3:.1f} GB)")
    return 0


def resolve_model_source(allow_download: bool) -> tuple[str, bool]:
    """确定权重来源。返回 (model_id 或本地路径, is_local)。"""
    local = settings.MODEL_PATH
    if local and Path(local).exists():
        return local, True
    if local:
        print(f"[FAIL] MMH3_MODEL_PATH 指向的路径不存在: {local}")
        raise SystemExit(1)

    model_id = settings.MODEL_NAME
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.utils import LocalEntryNotFoundError

        path = snapshot_download(
            repo_id=model_id, local_files_only=True, allow_patterns=["*.json", "*.txt"]
        )
        print(f"[OK] 权重已在本机 HF 缓存: {path}")
        return model_id, False
    except (ImportError, LocalEntryNotFoundError, Exception) as e:  # noqa: B014
        kind = type(e).__name__
        if allow_download:
            print(f"[WARN] 本地缓存未命中（{kind}），--allow-download 已授权在线拉取 {model_id}")
            return model_id, False
        print(
            f"[SKIP] 本地未找到 {model_id} 权重（{kind}）。\n"
            f"       请先下载权重到本地，并用 MMH3_MODEL_PATH 指向目录；"
            f"或显式加 --allow-download 在线拉取（体积巨大）。"
        )
        raise SystemExit(2)


def env_only_snapshot(allow_download: bool) -> int:
    """仅做环境 / CUDA / 权重 / 端口快照，不执行推理；沿用 check_environment 退出码语义。

    退出码：0=环境就绪快照完成；2=无 CUDA / 本地无权重且未授权下载（环境跳过）；
    1=依赖缺失或权重路径无效（失败）。用于「秒级自诊断」而无需拉起真实推理。
    """
    env = check_environment()
    if env != 0:
        return env  # 1=依赖缺失/失败；2=无 CUDA（环境跳过）

    try:
        import socket
        import torch

        props = torch.cuda.get_device_properties(0)
        print(f"[OK] GPU: {props.name} ({props.total_memory / 1024**3:.1f} GB)")
        print(f"[OK] torch {torch.__version__} · CUDA {torch.version.cuda}")
    except Exception as e:
        print(f"[WARN] 读取 GPU/CUDA 属性失败: {e}")

    try:
        model_id, is_local = resolve_model_source(allow_download)
        if is_local:
            print(f"[OK] 权重（本地路径）: {model_id}")
        else:
            print(f"[OK] 权重（HF 缓存 / 在线 id）: {model_id}")
    except SystemExit as e:
        if getattr(e, "code", 0) == 2:
            print("[WARN] 本地未找到权重且未授权下载 —— 权重快照跳过（不影响环境诊断）")
        else:
            raise

    port = int(os.environ.get("MMH3_PORT", "18080"))
    print(f"[INFO] 默认端口 MMH3_PORT={port}（被占用时启动链路自动顺延）")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
        print(f"[OK] 端口 {port} 可用")
    except OSError:
        print(f"[WARN] 端口 {port} 已被占用（启动将自动顺延）")

    print("[DONE] 环境快照完成（未执行推理），退出码 0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMax-H3 真实权重推理冒烟")
    parser.add_argument("--width", type=int, default=None, help="输出宽（默认按 1:1 768P 短边）")
    parser.add_argument("--height", type=int, default=None, help="输出高")
    parser.add_argument("--frames", type=int, default=None, help="帧数（默认最短 5 帧）")
    parser.add_argument("--prompt", default="A cat walking on a beach, cinematic.", help="测试提示词")
    parser.add_argument("--allow-download", action="store_true", help="权重缺失时允许在线拉取")
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="仅做环境/CUDA/权重/端口快照，不执行推理（用于秒级自诊断）",
    )
    args = parser.parse_args()

    if args.env_only:
        return env_only_snapshot(args.allow_download)

    env = check_environment()
    if env != 0:
        return env

    model_id, _ = resolve_model_source(args.allow_download)

    width = args.width
    height = args.height
    if width is None or height is None:
        width, height = h3.resolution_for("1:1", short_side=h3.SHORT_SIDE, multiple=2)
    frames = args.frames or h3.frames_for_duration(4 / 24)  # 最短 5 帧网格
    print(f"[INFO] 冒烟参数: {width}x{height} @ {frames}f, prompt={args.prompt[:40]!r}")

    import torch
    from diffusers import ModularPipeline

    t0 = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    try:
        pipe = ModularPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
        if settings.QUANTIZATION:
            pipe.enable_model_cpu_offload()
        output = pipe(
            prompt=args.prompt,
            width=width,
            height=height,
            num_frames=frames,
            fps=h3.FPS,
            audio_sample_rate=h3.AUDIO_SAMPLE_RATE,
        )
        SMOKE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        output.save(str(SMOKE_OUTPUT))
    except Exception as e:
        print(f"[FAIL] 推理失败: {type(e).__name__}: {e}")
        return 1

    elapsed = time.perf_counter() - t0
    peak_gb = torch.cuda.max_memory_allocated() / 1024**3
    size = SMOKE_OUTPUT.stat().st_size if SMOKE_OUTPUT.exists() else 0
    if size == 0:
        print("[FAIL] 推理完成但产物为空文件")
        return 1

    print(f"[PASS] 冒烟通过: {SMOKE_OUTPUT} ({size / 1024:.0f} KB)")
    print(f"[PASS] 耗时 {elapsed:.1f}s / CUDA 峰值显存 {peak_gb:.2f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
