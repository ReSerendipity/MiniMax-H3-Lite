"""来源标识验证工具（开发者使用）。

用法:
    python scripts/verify_watermark.py <video.mp4>
    python scripts/verify_watermark.py --embed <video.mp4> --payload "shot-abc"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from watermark import embed_video, extract_video  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="视频来源标识嵌入/验证（开发者工具）")
    ap.add_argument("video", help="视频文件路径")
    ap.add_argument("--embed", action="store_true", help="嵌入模式（默认提取验证）")
    ap.add_argument("--payload", default="manual-verify", help="嵌入的载荷文本")
    args = ap.parse_args()

    if args.embed:
        out = Path(args.video).with_name(Path(args.video).stem + "_marked.mp4")
        ok = embed_video(args.video, str(out), payload=args.payload)
        print(f"嵌入完成: {out}" if ok else "嵌入失败（详见 debug 日志）")
        return 0 if ok else 1

    res = extract_video(args.video)
    if res:
        print(f"来源标识: {res}")
        return 0
    print("未检测到来源标识（或文件不支持）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
