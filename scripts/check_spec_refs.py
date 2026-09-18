#!/usr/bin/env python3
"""Thin wrapper -> shared family auditor; --minimal fallback for CI.

The auditor lives OUTSIDE this repo (a sibling .spec_audit directory next to
developer machine it is found and the check is authoritative.  In a fresh CI
checkout it is absent: with ``--minimal`` (used by docs-consistency.yml) a
self-contained dead-link audit runs over tracked Markdown instead of silently
skipping — any relative Markdown link whose target is missing on disk AND not
gitignored fails the build (gitignored targets are allowed by family
convention: local-only governance docs may be referenced).  Without the flag
the legacy behaviour (skip, exit 0) is preserved.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404（git 仅以列表参数调用，无 shell 拼接）
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
AUDITORS = [
    HERE / ".spec_audit" / "audit_spec_refs.py",
    HERE.parent / ".spec_audit" / "audit_spec_refs.py",
]
MD_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
ABS = re.compile(r"^(https?://|mailto:|#|[A-Za-z]:[\\/]|/)")


GIT = shutil.which("git") or "git"


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    # 参数为 git 索引给出的仓库内相对路径；列表调用、无 shell（B603/B607 定向豁免）。
    return subprocess.run([GIT, "-C", str(HERE), *args], check=check,  # nosec B603 B607
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def _is_ignored(rel: str) -> bool:
    return subprocess.run([GIT, "-C", str(HERE), "check-ignore", "-q", rel]).returncode == 0  # nosec B603 B607（同上）


def minimal_audit() -> int:
    """Self-contained dead-link audit over tracked Markdown (no family auditor)."""
    try:
        listed = _git("ls-files", "--", "*.md").stdout
    except subprocess.CalledProcessError as exc:
        print(f"git ls-files failed: {exc.stderr}", file=sys.stderr)
        return 2
    md_files = [f for f in listed.splitlines() if f.strip()]
    findings: list[str] = []
    checked = 0
    for rel in md_files:
        src = HERE / rel
        try:
            text = src.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in MD_LINK.finditer(text):
            target = m.group(1).strip().strip("<>").replace("\\", "/")
            if not target or ABS.match(target):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            try:
                dest = (src.parent / target).resolve()
                rel_dest = dest.relative_to(HERE.resolve()).as_posix()
            except ValueError:
                continue  # 指向仓库外的链接不在最小审计范围
            checked += 1
            if dest.exists():
                continue
            if _is_ignored(rel_dest):
                continue  # gitignored 本地文档允许被引用（家族约定）
            findings.append(f"DEAD {rel} -> {target}")
    print(f"minimal dead-link audit: {len(md_files)} tracked md / {checked} relative links / {len(findings)} findings")
    for f in findings:
        print(f"  {f}")
    return 1 if findings else 0


def authoritative(auditor: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="spec_audit_") as td:
        out = Path(td) / "current.json"
        out_md = Path(td) / "current.md"
        subprocess.run([sys.executable, str(auditor), "--project", HERE.name,  # nosec B603（审计器路径来自本机探测）
                        "--json", str(out), "--md", str(out_md)], check=True)
        data = json.loads(out.read_text(encoding="utf-8"))[0]

    hard = [f for f in data["findings"] if f["status"] == "PHANTOM" and f["tier"] == "ASSERTIVE"]
    dl = data["dead_links"]
    wf = data["workflows"]["missing"]
    pc = data["precommit"]["declared_not_configured"]
    print(f"phantom={len(hard)} dead_links={len(dl)} bad_workflow={len(wf)} bad_hook={len(pc)}")
    for x in hard:
        print(f"  PHANTOM {x['ref']}  in {', '.join(x['specs'])}")
    for d in dl:
        print(f"  DEAD    {d['spec']}:{d['line']} -> {d['link']}")
    return 1 if (hard or dl or wf or pc) else 0


def main() -> int:
    auditor = next((p for p in AUDITORS if p.is_file()), None)
    if auditor is not None:
        return authoritative(auditor)  # 开发机：外部家族审计器存在时仍走权威审计
    if "--minimal" in sys.argv:
        return minimal_audit()  # CI/干净 checkout：降级为自包含死链审计，不再静默跳过
    print("family auditor not found; skipping (CI green) — "
          "docs-consistency.yml passes --minimal to run the fallback audit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
