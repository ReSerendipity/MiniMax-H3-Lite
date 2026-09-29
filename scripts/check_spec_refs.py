#!/usr/bin/env python3
"""Thin wrapper -> shared family auditor; --minimal for deterministic self-contained audit.

The auditor lives OUTSIDE this repo (a sibling .spec_audit directory next to
the project).  On a developer machine where it is found the check is
authoritative — but ONLY when ``--minimal`` is not passed.  Its console output
is captured and decoded UTF-8 (same convention as _git()) with the child
forced via PYTHONIOENCODING, so a cp936-locale Windows console no longer
crashes the run before a verdict is printed (2026-09-18 harness re-check).

``--minimal`` is a **deterministic mode selector** (2026-09-28 stabilisation):
when present the self-contained dead-link audit ALWAYS runs, regardless of
whether the family auditor exists on disk.  This guarantees identical output
on dev machines and CI — the core predictability requirement.  The audit
scans tracked Markdown plus ``AGENTS.md`` / ``docs/agents/*.md`` from disk
(any relative Markdown link whose target is missing on disk AND not
gitignored fails the build; gitignored targets are allowed by family
convention).  On a clean CI checkout those governance paths simply do not
exist on disk and contribute zero files (2026-09-25 harness fix: 铁律#6 在
CI/干净检出下对契约本身同样可复现).

Without ``--minimal`` the missing auditor is a gate that could not run at
all, so the wrapper prints an explicit error and exits 2 (2026-09-19 harness
fix: anti empty-run green light).
"""
from __future__ import annotations

import json
import os
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
    # check=False：git check-ignore 以退出码 1 表达「未被忽略」，属正常判定而非失败。
    return subprocess.run([GIT, "-C", str(HERE), "check-ignore", "-q", rel],
                          check=False).returncode == 0  # nosec B603 B607（同上）


def _audit_one(rel: str, findings: list[str]) -> int:
    """Audit relative Markdown links in one file; return number of links checked.

    ``rel`` is a repo-root-relative POSIX path.  Same rules apply to tracked
    Markdown and to the on-disk-only governance docs (AGENTS.md / docs/agents/):
    a missing target that is gitignored is treated as an allowed local-only
    reference, not a dead link (family convention).
    """
    src = HERE / rel
    try:
        text = src.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    checked = 0
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
    return checked


def _local_governance_md(tracked: set[str]) -> list[str]:
    """Return repo-relative paths of AGENTS.md and docs/agents/*.md present on
    disk but not already in the tracked set.  On a clean CI checkout these
    paths are gitignored and do not exist, so the list is empty there — the
    audit degrades gracefully rather than failing on missing files.
    """
    candidates: list[Path] = []
    root_agents = HERE / "AGENTS.md"
    if root_agents.is_file():
        candidates.append(root_agents)
    agents_dir = HERE / "docs" / "agents"
    if agents_dir.is_dir():
        candidates.extend(sorted(agents_dir.glob("*.md")))
    extras: list[str] = []
    seen: set[str] = set()
    for p in candidates:
        try:
            rel = p.resolve().relative_to(HERE.resolve()).as_posix()
        except ValueError:
            continue
        if rel in tracked or rel in seen:
            continue
        seen.add(rel)
        extras.append(rel)
    return extras


def minimal_audit() -> int:
    """Self-contained dead-link audit over tracked Markdown plus the on-disk
    AI-development contract (AGENTS.md / docs/agents/) so 铁律#6 证据绑定 复核
    在干净检出/无外部审计器环境下仍对契约本身可复现；gitignored 目标不计为死链。
    """
    try:
        listed = _git("ls-files", "--", "*.md").stdout
    except subprocess.CalledProcessError as exc:
        print(f"git ls-files failed: {exc.stderr}", file=sys.stderr)
        return 2
    md_files = [f for f in listed.splitlines() if f.strip()]
    extra_files = _local_governance_md(set(md_files))
    findings: list[str] = []
    checked = 0
    for rel in md_files:
        checked += _audit_one(rel, findings)
    for rel in extra_files:
        checked += _audit_one(rel, findings)
    print(
        f"minimal dead-link audit: {len(md_files)} tracked md"
        f" + {len(extra_files)} local-only governance md"
        f" (AGENTS.md / docs/agents/*)"
        f" / {checked} relative links / {len(findings)} findings"
    )
    if extra_files:
        print("  governance files audited from disk:")
        for rel in extra_files:
            print(f"    {rel}")
    for f in findings:
        print(f"  {f}")
    return 1 if findings else 0


def _echo(stream, text: str) -> None:
    """向本机可能非 UTF-8 的控制台（如 cp936）安全输出，范围外字符转义而非崩溃。"""
    enc = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(enc, "backslashreplace").decode(enc, "replace"))


def authoritative(auditor: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="spec_audit_") as td:
        out = Path(td) / "current.json"
        out_md = Path(td) / "current.md"
        # 与 _git() 同口径捕获并解码；同时强制子进程 stdout 为 UTF-8，否则仓外审计器
        # 向 cp936 控制台 print 报告会在包装脚本外崩溃，连 verdict 都给不出。
        proc = subprocess.run([sys.executable, str(auditor), "--project", HERE.name,  # nosec B603（审计器路径来自本机探测）
                               "--json", str(out), "--md", str(out_md)],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=False,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if proc.returncode != 0:
            print(f"family auditor exited {proc.returncode} (no verdict produced)",
                  file=sys.stderr)
            tail = "\n".join((proc.stderr or proc.stdout or "").splitlines()[-5:])
            if tail:
                _echo(sys.stderr, tail + "\n")
            return 1
        data = json.loads(out.read_text(encoding="utf-8"))[0]

    hard = [f for f in data["findings"] if f["status"] == "PHANTOM" and f["tier"] == "ASSERTIVE"]
    dl = data["dead_links"]
    wf = data["workflows"]["missing"]
    pc = data["precommit"]["declared_not_configured"]
    print(f"phantom={len(hard)} dead_links={len(dl)} bad_workflow={len(wf)} bad_hook={len(pc)}")
    for x in hard:
        _echo(sys.stdout, f"  PHANTOM {x['ref']}  in {', '.join(x['specs'])}\n")
    for d in dl:
        _echo(sys.stdout, f"  DEAD    {d['spec']}:{d['line']} -> {d['link']}\n")
    return 1 if (hard or dl or wf or pc) else 0


def main() -> int:
    # --minimal is a deterministic mode selector: always run self-contained
    # audit regardless of family auditor presence (2026-09-28 stabilisation).
    # This guarantees identical output on dev machines and CI.
    if "--minimal" in sys.argv:
        return minimal_audit()
    auditor = next((p for p in AUDITORS if p.is_file()), None)
    if auditor is not None:
        return authoritative(auditor)  # 开发机：外部家族审计器存在时仍走权威审计
    # 审计器缺失且未显式选择降级：门禁实际未执行，不得伪装成绿灯（exit 2 = 无法产出判定）。
    print("ERROR: family auditor not found and --minimal not passed; the spec-ref "
          "gate could not run — no verdict, failing loudly instead of CI green.\n"
          "       Run with --minimal for the self-contained dead-link audit "
          "(CI path), or provide the family .spec_audit auditor.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
