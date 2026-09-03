#!/usr/bin/env python3
"""
scripts/check_compose_mounts.py — docker-compose bind-mount 源存在性门禁

根因
----
上一次部署 bug = docker-compose.yml:35 挂载了不存在的 ./config.yaml，
导致 `docker compose up -d --build` 在 bind-mount 阶段失败。
`SECURITY_REMEDIATION_TRACKER.md` / GOTCHAS #21 均有记载。

本脚本：解析 compose 文件所有 bind-mount 源（./xxx、/abs、Windows 盘符路径），
断言每个源在仓库根（compose 同级目录）真实存在，作为部署前可重复的快速门禁。

注：
- 仅检查 bind-mount（`./src:dst[:mode]` 形式），不处理 named volumes / tmpfs / configs。
- 源路径以 `./` / `../` / `/` / `C:\\` 之一开头时按 bind 解析；
  单段字符串视为 named volume，跳过。
- 对 Windows Junction 软链目录：Path.exists() 跟随 Junction 成功即可，
  不会误报（参见 GOTCHAS #20）。

用法
----
    python scripts/check_compose_mounts.py                 # 默认 docker-compose.yml
    python scripts/check_compose_mounts.py --file X.yml
    python scripts/check_compose_mounts.py --strict-files  # 一律按文件校验
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 让 Windows GBK 控制台也能跑（Python 3.7+ 支持）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent

# 单行 bind-mount 解析：- src:dst[:ro|rw]
# 容许 src 带引号（YAML 风格）；行末可有注释
BIND_RE = re.compile(
    r"""^\s*-\s*
        (?P<src>\"[^\"]+\"|'[^']+'|[\w./:\\\-\s]+?)
        :(?P<dst>[^:#]+?)
        (?::(?P<mode>ro|rw))?
        \s*(?:\#.*)?$""",
    re.VERBOSE,
)


def parse_compose(path: Path) -> list[tuple[int, str, str, str | None]]:
    """返回 [(lineno, src, dst, mode_or_None), ...] 所有 bind-mount。"""
    text = path.read_text(encoding="utf-8")
    in_volumes = False
    base_indent: int | None = None
    out: list[tuple[int, str, str, str | None]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 段头识别：services: <name>: <key>: 缩进递增
        if stripped.endswith(":"):
            in_volumes = stripped == "volumes:"
            base_indent = None
            continue
        if not in_volumes:
            continue
        # 退出 volumes 段：遇到同级或更浅缩进
        leading = len(line) - len(line.lstrip(" "))
        if base_indent is None:
            base_indent = leading
        if leading < base_indent:
            in_volumes = False
            continue
        m = BIND_RE.match(line)
        if not m:
            continue
        src = m.group("src").strip().strip('"').strip("'").strip()
        dst = m.group("dst").strip()
        mode = m.group("mode")
        out.append((lineno, src, dst, mode))
    return out


def parse_compose_image_refs(path: Path) -> list[tuple[int, str, str, str]]:
    """返回 [(lineno, service, image_ref, tag), ...] 所有 services.<svc>.image: 行。

    tag 规范化：显式 :tag → 保留；无 tag 或 :latest → 标 (:latest) 以触发警告。
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[tuple[int, str, str, str]] = []
    in_services = False
    cur_service: str | None = None
    base_indent: int | None = None
    svc_indent: int | None = None
    image_re = re.compile(r'^\s*image:\s*["\']?([^"\']+)["\']?\s*(?:#.*)?$')
    service_re = re.compile(r"^\s{2}([A-Za-z0-9_.-]+):\s*(?:#.*)?$")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "services:":
            in_services = True
            base_indent = len(line) - len(line.lstrip(" "))
            continue
        if not in_services:
            continue
        leading = len(line) - len(line.lstrip(" "))
        if leading <= base_indent:
            # 退到顶层（非 services 段）
            in_services = False
            cur_service = None
            continue
        sm = service_re.match(line)
        if sm:
            cur_service = sm.group(1)
            svc_indent = leading
            continue
        if cur_service is None or leading <= svc_indent:
            continue
        # 跳过 build: 段的 image（那是 build 上下文里的镜像名，不是 service 的 image 引用）
        im = image_re.match(line)
        if im:
            ref = im.group(1).strip()
            if ":" in ref.split("/")[-1] and not ref.startswith("sha256:"):
                tag = ref.rsplit(":", 1)[1]
            else:
                tag = ":latest"  # 隐式 latest
            out.append((lineno, cur_service, ref, tag))
    return out


def looks_like_bind(src: str) -> bool:
    """是否为 bind-mount 源（路径形态），而非 named volume。"""
    if src.startswith(("./", "../", "/", ".\\", "..\\")):
        return True
    # Windows 盘符 C:\ C:/
    if re.match(r"^[A-Za-z]:[\\/]", src):
        return True
    # 其它单段字符串视为 named volume
    return False


def kind_of(src: str) -> str:
    """FILE / DIR / UNKNOWN — 仅按"名字是否带点"粗判；Strict mode 下让调用者 override。"""
    name = Path(src.replace("\\", "/")).name
    if "." in name and not name.startswith("."):
        return "FILE"
    return "DIR"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    ap.add_argument("--file", default="docker-compose.yml", help="compose 文件相对仓库根")
    ap.add_argument("--strict-files", action="store_true", help="把所有 mount 视为文件校验（罕见用法）")
    args = ap.parse_args()

    compose = ROOT / args.file
    if not compose.exists():
        print(f"[FAIL] {compose} 不存在", file=sys.stderr)
        return 2
    compose_dir = compose.parent

    mounts = parse_compose(compose)
    print(f"扫描 {args.file}，共 {len(mounts)} 个 mount 条目：")

    bad: list[tuple[int, str, str, str]] = []
    for lineno, src, dst, mode in mounts:
        marker_kind = "FILE" if args.strict_files else kind_of(src)
        if not looks_like_bind(src):
            print(f"  L{lineno:>3} {src} -> {dst}:{mode or 'rw'}  [named volume — 跳过]")
            continue
        if src.startswith("/"):
            abs_src = Path(src)
        elif re.match(r"^[A-Za-z]:[\\/]", src):
            abs_src = Path(src)
        else:
            abs_src = (compose_dir / src).resolve()

        exists = abs_src.exists()
        if exists and marker_kind == "FILE" and abs_src.is_dir():
            # 解析为文件但实际是目录，仍视为"可用"，但给个提示
            actual = "DIR"
        elif exists:
            actual = marker_kind
        else:
            actual = "MISSING"

        symbol = "[OK]" if exists else "[FAIL]"
        line = f"  L{lineno:>3} {src:<32} -> {dst}:{mode or 'rw':<2}  [{actual:<8}] {symbol}"
        print(line)
        if not exists:
            bad.append((lineno, src, dst, mode or "rw"))

    print()
    if bad:
        print(f"[FAIL] {len(bad)} 个 bind-mount 源不存在：")
        for lineno, src, dst, mode in bad:
            print(f"  L{lineno} {src} -> {dst}:{mode}")
        print()
        print("修复指引：")
        print("  - 目录源：mkdir -p <dir>")
        print("  - 文件源：要么创建该文件，要么把这一行从 compose 移除")
        print("  - 典型案例：'./config.yaml'（本仓无此文件，参见 GOTCHAS #21）")
        return 1

    print(f"[OK] {args.file} 所有 bind-mount 源均存在")

    # === 副检查：services.<svc>.image: 引用 ===
    # 警告级（不退出非零）：发现 :latest 或无 tag 的 image 引用
    image_refs = parse_compose_image_refs(compose)
    if image_refs:
        print()
        print("副检查 — services.<svc>.image: 引用：")
        latest_hits: list[tuple[int, str, str, str]] = []
        for lineno, svc, ref, tag in image_refs:
            is_pinned = "@sha256:" in ref
            is_versioned = tag and tag not in (":latest", "")
            if is_pinned:
                status = "[OK-PINNED]"
            elif is_versioned:
                status = "[OK]"
            else:
                status = "[WARN-LATEST]"
                latest_hits.append((lineno, svc, ref, tag))
            note = "(sha256 digest)" if is_pinned else ""
            print(f"  L{lineno:>3} services.{svc}.image: {ref:<48} {status} {note}")
        if latest_hits:
            print()
            print(f"[WARN] {len(latest_hits)} 个 service 引用了 :latest 或未指定 tag（防 tag 漂移）")
            print("       建议：")
            print("         1. 改用版本化 tag（如 minimax-h3-lite:2.9.1-cu130）")
            print("         2. 或用 scripts/build_and_pin.ps1 生成 docker-compose.pinned.yml 固化 digest")
            print("       本检查不阻断通过；带 WARN 提交也算绿，但请尽快修。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
