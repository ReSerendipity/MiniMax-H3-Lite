#!/usr/bin/env python3
"""权重完整性 manifest：生成 / 校验 SHA-256 清单（MLOps 评估 P1 · 防篡改）。

背景：权重不随仓库分发（NOTICE 控制），`MMH3_MODEL_PATH` 指向外部目录。此前
没有任何防篡改手段 —— 权重被替换/损坏只会表现为"推理结果静默劣化"。

设计取向（单机工具，不做过度工程）：
  * **只读权重**：本脚本绝不写 model/（禁区），manifest 默认落在 data/ 下
    （`--out` 可改），生成/校验均为读操作。
  * **双模式**：--generate 生成快照；--verify 比对。退出码语义对齐家族脚本：
    0=通过 / 1=校验失败（变更·缺失·多余） / 2=跳过（manifest 不存在或无权重目录）。
  * **可控成本**：默认只哈希模型类文件（safetensors/bin/gguf/pt/ckpt/json/txt），
    流式读取（1 MiB 分块），不做全目录无差别哈希。

用法:
    python scripts/verify_model_hashes.py --generate --model-dir D:/models/MiniMax-H3
    python scripts/verify_model_hashes.py --verify                  # 用默认 manifest
    python scripts/verify_model_hashes.py --verify --manifest my.sha256 --quiet

manifest 格式（每行一条，排序稳定）:
    <sha256_hex>  <size_bytes>  <相对路径（正斜杠）>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from config import settings  # noqa: E402

# 默认纳入哈希的文件后缀（模型权重 + 配置文件）；目录级遍历不做无差别扫描
DEFAULT_SUFFIXES = (
    ".safetensors", ".bin", ".gguf", ".pt", ".pth", ".ckpt",
    ".json", ".txt", ".model",
)
CHUNK = 1024 * 1024  # 1 MiB
DEFAULT_MANIFEST = "data/model-manifest.sha256"


def iter_model_files(model_dir: Path, suffixes=DEFAULT_SUFFIXES):
    """遍历权重目录下的目标文件，返回按相对路径排序的 (rel, abs) 序列。"""
    out = []
    for p in model_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in suffixes:
            continue
        out.append((p.relative_to(model_dir).as_posix(), p))
    return sorted(out, key=lambda t: t[0])


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256（大权重不会把内存打满）。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def resolve_model_dir(cli_dir: str | None) -> Path | None:
    """确定权重目录：CLI > settings.MODEL_PATH。不存在返回 None。"""
    raw = cli_dir or settings.MODEL_PATH
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def generate(model_dir: Path, out_path: Path, quiet: bool = False) -> int:
    files = iter_model_files(model_dir)
    if not files:
        print(f"[SKIP] {model_dir} 下没有匹配 {', '.join(DEFAULT_SUFFIXES[:4])}… 的文件，未生成 manifest")
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, (rel, abs_path) in enumerate(files, 1):
        digest = sha256_file(abs_path)
        size = abs_path.stat().st_size
        lines.append(f"{digest}  {size}  {rel}")
        if not quiet and i % 10 == 0:
            print(f"  …已哈希 {i}/{len(files)}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 结论行恒打印（--quiet 只压逐项进度），避免自动化调用时"静默成功"
    print(f"[OK] manifest 已生成: {out_path}（{len(files)} 个文件，来源 {model_dir}）")
    if not quiet:
        print("     提示：权重升级后请重新生成；本文件只记录哈希，不复制、不改动任何权重。")
    return 0


def parse_manifest(text: str) -> dict[str, tuple[str, int]]:
    """解析 manifest 文本 → {rel: (sha256, size)}。"""
    entries: dict[str, tuple[str, int]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        digest, size, rel = parts
        entries[rel] = (digest, int(size))
    return entries


def verify(model_dir: Path, manifest_path: Path, quiet: bool = False) -> int:
    if not manifest_path.exists():
        print(f"[SKIP] 未找到 manifest：{manifest_path}（先跑 --generate 生成基线）")
        return 2

    expected = parse_manifest(manifest_path.read_text(encoding="utf-8"))
    if not expected:
        print(f"[FAIL] manifest 为空或格式不可解析：{manifest_path}")
        return 1

    changed, missing, ok = [], [], 0
    for rel, (exp_hash, exp_size) in expected.items():
        p = model_dir / rel
        if not p.exists():
            missing.append(rel)
            continue
        got_size = p.stat().st_size
        got_hash = sha256_file(p)
        if got_hash != exp_hash or got_size != exp_size:
            changed.append(f"{rel}（期望 {exp_hash[:12]}…/{exp_size}B，实际 {got_hash[:12]}…/{got_size}B）")
        else:
            ok += 1

    if changed or missing:
        print(f"[FAIL] 权重完整性校验未通过：一致 {ok} / 变更 {len(changed)} / 缺失 {len(missing)}")
        for r in changed[:10]:
            print(f"   CHANGED {r}")
        for r in missing[:10]:
            print(f"   MISSING {r}")
        print("       排查：权重被替换/损坏 → 用备份恢复；正常升级 → 重新 --generate 生成基线")
        return 1

    print(f"[PASS] 权重完整性校验通过：{ok} 个文件哈希与 manifest 一致（{manifest_path}）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="MiniMax-H3 权重 SHA-256 完整性 manifest")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate", action="store_true", help="生成 manifest 快照")
    mode.add_argument("--verify", action="store_true", help="比对 manifest 与磁盘权重")
    ap.add_argument("--model-dir", default=None, help="权重目录（默认取 MMH3_MODEL_PATH / settings.MODEL_PATH）")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST, help=f"manifest 路径（默认 {DEFAULT_MANIFEST}）")
    ap.add_argument("--quiet", action="store_true", help="只输出结论，省略逐项进度")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    model_dir = resolve_model_dir(args.model_dir)
    if model_dir is None:
        src = args.model_dir or "settings.MODEL_PATH"
        print(f"[SKIP] 权重目录不可用或未配置：{src}（配置 MMH3_MODEL_PATH 后重试）")
        return 2

    if args.generate:
        return generate(model_dir, manifest_path, args.quiet)
    return verify(model_dir, manifest_path, args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
