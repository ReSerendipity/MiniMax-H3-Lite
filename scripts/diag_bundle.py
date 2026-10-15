#!/usr/bin/env python3
"""崩溃/故障诊断包收集（运维稳定性评估 P1-1 可落地部分）。

把排障所需的最小现场打包成单个 zip，落到本地诊断目录（默认 diagnostics/）：
  * logs/backend.log(+.1...) 与 logs/backend_faults.log（faulthandler 崩溃栈）
  * logs/mmh3-desktop-shell.log、logs/desktop_python_*.log（桌面壳侧）
  * package.json（版本单一事实源）与 data/settings.json（运行时设置，不含密钥）
不打包：data/mmh3.db（用户数据）、uploads/（用户素材）、model/（权重禁区）。

设计约束：
  * 纯标准库；只读收集 + 本地打包，绝不联网上传。外发由用户自行决定，且外发前
    应人工检查日志内容是否含敏感信息（SRE_RUNBOOK「本地日志与诊断包脱敏」口径）。

用法：
    python scripts/diag_bundle.py                  # 默认输出 <仓库根>/diagnostics/diag_<时间戳>.zip
    python scripts/diag_bundle.py --out <输出目录>  # 自定义输出目录
    python scripts/diag_bundle.py --root <目录>    # 指定收集根（测试/演练用）
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "diagnostics"


def collect_sources(root: Path) -> list[Path]:
    """收集待打包文件（存在才纳入；确定性排序；去重）。"""
    sources: list[Path] = []
    logs = root / "logs"
    if logs.is_dir():
        sources.extend(sorted(p for p in logs.glob("backend.log*")))
        sources.extend(sorted(p for p in logs.glob("backend_faults.log*")))
        sources.extend(sorted(p for p in logs.glob("desktop_python_*.log")))
        shell = logs / "mmh3-desktop-shell.log"
        if shell.exists():
            sources.append(shell)
    for rel in ("package.json", "data/settings.json"):
        p = root / rel
        if p.exists():
            sources.append(p)
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in sources:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def make_bundle(root: Path, out_dir: Path) -> tuple[Path, list[str]]:
    """打包并返回 (zip 路径, manifest 行列表)；无任何可收集源时 SystemExit。"""
    sources = collect_sources(root)
    if not sources:
        raise SystemExit(f"无可收集的诊断源（{root}/logs 为空且无 package.json）—— 先复现一次现场再打包。")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    zpath = out_dir / f"diag_{ts}.zip"
    manifest: list[str] = []
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sources:
            arc = p.relative_to(root).as_posix()
            zf.write(p, arcname=arc)
            manifest.append(f"{arc}  {p.stat().st_size}B")
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    manifest.append(f"sha256: {digest}")
    return zpath, manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="收集崩溃/故障诊断包（本地打包，不上传）")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出目录（默认 <仓库根>/diagnostics/）")
    ap.add_argument("--root", type=Path, default=ROOT, help="收集根目录（默认仓库根；测试/演练用）")
    args = ap.parse_args(argv)
    zpath, manifest = make_bundle(args.root, args.out)
    print(f"[OK] 诊断包：{zpath}")
    for line in manifest:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
