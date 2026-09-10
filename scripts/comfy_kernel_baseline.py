#!/usr/bin/env python3
"""scripts/comfy_kernel_baseline.py — vendored ComfyUI 内核的漂移守卫。

为什么需要它
------------
comfy_kernel/ 是 ComfyUI 0.33.0 内核源码的 vendored 副本（GPL-3.0），
但它**不是 git 仓库**、也被 .gitignore 排除。三重后果：

  * 没有任何机制能检测内核被本地修改；
  * 无法声明"上游对应提交"，因此 GPL 的书面源码承诺（方式 B）在本仓不成立；
  * `AGENTS.md` 禁区表要求改动须"记录进 ADR + 保留 patch 文件"，
    但此前并无任何可核对的凭据。

本脚本以"一级目录聚合摘要"建立基线（计划 R2：不用逐文件清单，
4136 文件的 manifest ≈ 200 KB 且每次升级全量 churn），漂移报告到目录粒度。

三态判定（与 check_compose_mounts.py 保持同一套语义）
----------------------------------------------------
  基线文件缺失            → FAIL（它入库，缺失＝门禁被拆）
  内核目录缺失（CI 必然） → SKIP（不入库，由部署机提供）
  两者均在但摘要不符      → FAIL 并列出漂移的一级目录

用法
----
    python scripts/comfy_kernel_baseline.py --generate
    python scripts/comfy_kernel_baseline.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:  # Windows GBK 控制台
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / ".ci" / "comfy_kernel_baseline.json"
SKIP_DIRS = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", "node_modules"}


def scan(kernel: Path) -> dict[str, str]:
    """返回 {相对 posix 路径: 文件 sha256}，排除 SKIP_DIRS 下的内容。"""
    entries: dict[str, str] = {}
    for p in sorted(kernel.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(kernel)
        if SKIP_DIRS & set(rel.parts):
            continue
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        entries[rel.as_posix()] = h.hexdigest()[:16]
    return entries


def _top_dir(rel: str) -> str:
    """一级目录；内核根下的文件记作 '.'。"""
    return rel.split("/", 1)[0] if "/" in rel else "."


def build_baseline(kernel: Path, kernel_version: str | None) -> dict:
    """生成基线：逐一级目录摘要 + 根摘要 + 计数。"""
    entries = scan(kernel)
    per_dir: dict[str, list[str]] = {}
    for rel, digest in entries.items():
        per_dir.setdefault(_top_dir(rel), []).append(f"{rel}:{digest}")
    dirs = {
        d: hashlib.sha256("\n".join(sorted(items)).encode("utf-8")).hexdigest()[:16]
        for d, items in per_dir.items()
    }
    root_digest = hashlib.sha256(
        "\n".join(f"{d}:{dirs[d]}" for d in sorted(dirs)).encode("utf-8")
    ).hexdigest()
    return {
        "schema": 1,
        "kernel_version": kernel_version,
        "file_count": len(entries),
        "root_digest": root_digest,
        "dirs": dict(sorted(dirs.items())),
    }


def read_version(kernel: Path) -> str | None:
    """内核版本：pyproject.toml 的 version 字段（无第三方依赖，故手工解析）。"""
    py = kernel / "pyproject.toml"
    if not py.exists():
        return None
    for line in py.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s.startswith("version"):
            return s.split("=", 1)[1].strip().strip("\"'")
    return None


def diff(baseline: dict, current: dict) -> list[dict]:
    """返回漂移列表，元素含 dir / kind（added|removed|modified）。"""
    old: dict[str, str] = baseline.get("dirs", {})
    new: dict[str, str] = current.get("dirs", {})
    out: list[dict] = []
    for d in sorted(set(old) | set(new)):
        if d not in old:
            out.append({"dir": d, "kind": "added"})
        elif d not in new:
            out.append({"dir": d, "kind": "removed"})
        elif old[d] != new[d]:
            out.append({"dir": d, "kind": "modified"})
    if baseline.get("file_count") != current.get("file_count"):
        out.append({"dir": "*", "kind": "file_count",
                    "detail": f"{baseline.get('file_count')} -> {current.get('file_count')}"})
    return out


def decide(baseline_present: bool, kernel_present: bool) -> str:
    """三态判定的唯一真源（与 check_compose_mounts.classify_mount 同构）。"""
    if not baseline_present:
        return "FAIL"
    if not kernel_present:
        return "SKIP"
    return "CHECK"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="vendored ComfyUI 内核漂移守卫")
    ap.add_argument("--root", default=str(ROOT / "comfy_kernel"), help="内核目录")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="基线 JSON 路径")
    ap.add_argument("--version", default=None, help="内核版本；缺省则从 pyproject 读取")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--generate", action="store_true", help="生成/更新基线")
    g.add_argument("--check", action="store_true", help="与基线比对")
    args = ap.parse_args(argv)

    kernel = Path(args.root).resolve()
    out = Path(args.out).resolve()
    verdict = decide(out.exists(), kernel.is_dir())

    if args.generate:
        if not kernel.is_dir():
            print(f"[FAIL] 内核目录不存在: {kernel}", file=sys.stderr)
            return 1
        base = build_baseline(kernel, args.version or read_version(kernel))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"[OK] 基线已写入 {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
        print(f"     版本={base['kernel_version']} 文件数={base['file_count']} "
              f"一级目录={len(base['dirs'])} 根摘要={base['root_digest'][:12]}")
        return 0

    if verdict == "FAIL":
        print(f"[FAIL] 基线文件缺失: {out}", file=sys.stderr)
        print("       它随仓库入库，缺失等于门禁被拆掉。", file=sys.stderr)
        print("       重建：python scripts/comfy_kernel_baseline.py --generate", file=sys.stderr)
        return 1
    if verdict == "SKIP":
        print(f"[SKIP] 内核目录不存在（{kernel}）——vendored、不入库，"
              "托管 runner 的 checkout 属正常情形；实际强制在部署机 preflight.sh。")
        return 0

    baseline = json.loads(out.read_text(encoding="utf-8"))
    current = build_baseline(kernel, args.version or read_version(kernel))
    drift = diff(baseline, current)
    if drift:
        print("[FAIL] vendored 内核相对基线发生漂移：", file=sys.stderr)
        for d in drift:
            extra = f" ({d.get('detail')})" if "detail" in d else ""
            print(f"  - {d['kind']:<9} {d['dir']}{extra}", file=sys.stderr)
        print()
        print("处置（AGENTS 禁区表：comfy_kernel/ 改动须记录进 ADR + 保留 patch）：",
              file=sys.stderr)
        print("  1. 确认是有意变更 → 在 ADR 记录动机，并 --generate 重算基线")
        print("  2. 非有意 → 还原内核文件；GPL 义务边界以基线为凭")
        print(f"  基线版本={baseline.get('kernel_version')} 当前版本={current.get('kernel_version')}")
        return 1
    if baseline.get("kernel_version") != current.get("kernel_version"):
        print(f"[FAIL] 版本号漂移 {baseline.get('kernel_version')} -> "
              f"{current.get('kernel_version')} 但内容摘要相同 —— 基线元数据过期，"
              "须 --generate 重算", file=sys.stderr)
        return 1
    print(f"[OK] vendored 内核与基线一致：{current['file_count']} 文件 / "
          f"{len(current['dirs'])} 个一级目录 / 版本 {current['kernel_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
