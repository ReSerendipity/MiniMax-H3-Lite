#!/usr/bin/env python3
"""
最小验证脚本 — 编辑后即时反馈（2026-09-28）

在每次涉及源码或测试文件的编辑集完成后，根据变更范围匹配最小验证命令并执行。
设计目标：快速反馈（< 30 s 常见路径），不引入新工具，不改变 CI 管线。

用法：
    # 自动检测未提交变更（git diff HEAD）
    python scripts/minimal_verify.py

    # 显式指定变更文件
    python scripts/minimal_verify.py backend/watermark.py tests/test_watermark.py

    # 仅显示将要执行的命令，不实际运行（dry-run）
    python scripts/minimal_verify.py --dry-run

    # 包含集成测试（默认排除 slow/integration）
    python scripts/minimal_verify.py --full

退出码：
    0 — 验证通过
    1 — 验证失败（附精确失败摘要）
    2 — 脚本自身错误（如 git 不可用）
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"
BACKEND_DIR = PROJECT_ROOT / "backend"

# ---------------------------------------------------------------------------
# 源文件 → 测试文件映射规则
# ---------------------------------------------------------------------------

def _backend_module_tests(changed: list[Path]) -> list[str]:
    """backend/<module>.py → tests/test_<module>.py（若存在）"""
    tests = []
    for p in changed:
        # backend/foo.py → test_foo.py
        # backend/routers/foo.py → test_api_*.py（路由变更影响 API 测试）
        rel = p.relative_to(PROJECT_ROOT)
        parts = rel.parts
        if len(parts) == 2 and parts[0] == "backend" and parts[1] != "__init__.py":
            mod = parts[1].removesuffix(".py")
            candidate = TESTS_DIR / f"test_{mod}.py"
            if candidate.exists():
                tests.append(str(candidate))
        elif len(parts) >= 3 and parts[0] == "backend" and parts[1] == "routers":
            # 路由变更 → 跑全部 API 测试
            for t in sorted(TESTS_DIR.glob("test_api_*.py")):
                tests.append(str(t))
        elif len(parts) >= 3 and parts[0] == "backend" and parts[1] == "h3":
            # H3 模块 → H3 相关测试
            for t in sorted(TESTS_DIR.glob("test_h3_*.py")):
                tests.append(str(t))
            for t in sorted(TESTS_DIR.glob("test_comfy_*.py")):
                tests.append(str(t))
        elif len(parts) >= 3 and parts[0] == "backend" and parts[1] == "security":
            # 安全模块 → 安全相关测试
            for t in sorted(TESTS_DIR.glob("test_*security*.py")):
                tests.append(str(t))
            for t in sorted(TESTS_DIR.glob("test_integrity*.py")):
                tests.append(str(t))
    return tests


def _script_tests(changed: list[Path]) -> list[str]:
    """scripts/<name>.py → tests/test_<name>.py（若存在）"""
    tests = []
    for p in changed:
        rel = p.relative_to(PROJECT_ROOT)
        if rel.parts[0] == "scripts" and p.suffix == ".py":
            mod = p.stem
            candidate = TESTS_DIR / f"test_{mod}.py"
            if candidate.exists():
                tests.append(str(candidate))
    return tests


def _has_frontend_changes(changed: list[Path]) -> bool:
    """检查是否有前端相关变更（templates / assets / package.json）"""
    for p in changed:
        rel = p.relative_to(PROJECT_ROOT)
        if rel.parts[0] in ("assets", "templates"):
            return True
        if rel.parts[0] == "backend" and len(rel.parts) >= 2:
            if rel.parts[1] == "templates":
                return True
        if p.name == "package.json" and rel.parts[0] not in ("tests", "comfy_kernel"):
            return True
    return False


def _has_config_changes(changed: list[Path]) -> bool:
    """检查是否有影响版本/配置的全局变更"""
    config_files = {
        "package.json", "backend/version.py", "backend/config.py",
        "backend/database.py", "pytest.ini",
    }
    for p in changed:
        rel = p.relative_to(PROJECT_ROOT)
        # 统一用 / 分隔符比较（Windows 上 rel 可能是 \\）
        rel_str = rel.as_posix()
        if rel_str in config_files:
            return True
    return False


def _test_file_self_tests(changed: list[Path]) -> list[str]:
    """变更本身就是测试文件 → 直接跑该测试"""
    tests = []
    for p in changed:
        rel = p.relative_to(PROJECT_ROOT)
        if rel.parts[0] == "tests" and p.name.startswith("test_") and p.suffix == ".py":
            tests.append(str(p))
    return tests


# ---------------------------------------------------------------------------
# 变更检测
# ---------------------------------------------------------------------------

def detect_changed_files() -> list[Path]:
    """通过 git diff 检测当前未提交的变更文件（含暂存和未暂存）"""
    # 需要追踪的文件扩展名（Python + 前端 + 配置）
    tracked_suffixes = {
        ".py", ".js", ".html", ".css", ".json", ".yaml", ".yml",
    }
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            # HEAD 可能不存在（空仓库），退而求其次用 --cached
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True, text=True, encoding="utf-8",
                cwd=PROJECT_ROOT,
            )
        files = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line:
                p = PROJECT_ROOT / line
                if p.exists() and p.suffix in tracked_suffixes:
                    files.append(p)
        return files
    except FileNotFoundError:
        print("[minimal_verify] 错误：git 不可用，无法自动检测变更文件", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# 命令构建
# ---------------------------------------------------------------------------

def build_verify_commands(changed: list[Path], full: bool = False) -> list[tuple[str, list[str]]]:
    """
    根据变更文件列表，返回 [(描述, 命令列表), ...]
    每个条目是一个独立的验证步骤。
    """
    if not changed:
        return []

    steps: list[tuple[str, list[str]]] = []

    # 1. 测试文件自身变更 → 直接跑
    self_tests = _test_file_self_tests(changed)
    if self_tests:
        cmd = [sys.executable, "-m", "pytest", "-x", "--no-cov", "--tb=short", "-q"]
        if not full:
            cmd.extend(["-m", "not slow and not integration"])
        cmd.extend(sorted(set(self_tests)))
        steps.append(("测试文件变更 → 直接执行", cmd))

    # 2. backend 源码变更 → 匹配测试
    backend_files = [p for p in changed
                     if p.is_relative_to(BACKEND_DIR) and p.suffix == ".py"]
    if backend_files:
        matched = _backend_module_tests(backend_files)
        if matched:
            cmd = [sys.executable, "-m", "pytest", "-x", "--no-cov", "--tb=short", "-q"]
            if not full:
                cmd.extend(["-m", "not slow and not integration"])
            cmd.extend(sorted(set(matched)))
            steps.append(("backend 源码变更 → 匹配测试", cmd))
        else:
            # 没有精确匹配的测试文件 → 跑冒烟测试
            smoke_tests = sorted(TESTS_DIR.glob("test_api_smoke.py"))
            if smoke_tests:
                cmd = [sys.executable, "-m", "pytest", "-x", "--no-cov", "--tb=short", "-q",
                       "-m", "smoke"]
                steps.append(("backend 变更无精确匹配 → 冒烟测试", cmd))

    # 3. scripts 变更 → 匹配测试
    script_files = [p for p in changed
                    if p.is_relative_to(SCRIPTS_DIR) and p.suffix == ".py"]
    if script_files:
        matched = _script_tests(script_files)
        if matched:
            cmd = [sys.executable, "-m", "pytest", "-x", "--no-cov", "--tb=short", "-q"]
            if not full:
                cmd.extend(["-m", "not slow and not integration"])
            cmd.extend(sorted(set(matched)))
            steps.append(("scripts 变更 → 匹配测试", cmd))

    # 4. 前端变更 → npm test:frontend
    if _has_frontend_changes(changed):
        steps.append(("前端变更 → npm run test:frontend",
                      ["npm", "run", "test:frontend"]))

    # 5. 配置/版本变更 → 版本一致性测试
    if _has_config_changes(changed):
        version_test = str(TESTS_DIR / "test_version_consistency.py")
        if Path(version_test).exists():
            cmd = [sys.executable, "-m", "pytest", "-x", "--no-cov", "--tb=short", "-q",
                   version_test]
            steps.append(("配置/版本变更 → 版本一致性验证", cmd))

    return steps


# ---------------------------------------------------------------------------
# 执行与报告
# ---------------------------------------------------------------------------

def run_command(cmd: list[str], description: str, dry_run: bool = False) -> bool:
    """
    执行单条验证命令。返回 True 表示通过，False 表示失败。
    dry_run=True 时只打印命令不执行。
    """
    cmd_str = " ".join(cmd)
    print(f"\n{'=' * 60}")
    print(f"[步骤] {description}")
    print(f"[命令] {cmd_str}")
    print(f"{'=' * 60}")

    if dry_run:
        print("  (dry-run，跳过执行)")
        return True

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0
    except Exception as exc:
        print(f"\n  ✗ 命令执行异常：{exc}", file=sys.stderr)
        return False


def print_summary(results: list[tuple[str, bool]], dry_run: bool = False) -> None:
    """输出精确的失败摘要"""
    if not results:
        print("\n[minimal_verify] 无可执行的验证步骤（无源码/测试变更）")
        return

    print(f"\n{'=' * 60}")
    print("验证摘要")
    print(f"{'=' * 60}")

    failures = [(desc, ok) for desc, ok in results if not ok]
    passes = [(desc, ok) for desc, ok in results if ok]

    if passes:
        for desc, _ in passes:
            print(f"  ✓ {desc}")

    if failures:
        for desc, _ in failures:
            print(f"  ✗ {desc}")
        print(f"\n失败 {len(failures)}/{len(results)} 项，请检查上方输出。")
    elif not dry_run:
        print(f"\n全部 {len(results)} 项通过。")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="最小验证脚本 — 编辑后即时反馈",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="显式指定变更文件路径（相对或绝对）；不指定则自动 git diff",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅显示将要执行的命令，不实际运行",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="包含 slow/integration 标记的测试（默认排除）",
    )
    args = parser.parse_args()

    # 解析变更文件列表
    if args.files:
        changed = [p.resolve() for p in args.files if p.exists()]
        if not changed:
            print("[minimal_verify] 指定的文件均不存在", file=sys.stderr)
            return 2
    else:
        changed = detect_changed_files()
        if not changed:
            print("[minimal_verify] 未检测到源码/测试文件变更")
            return 0

    # 过滤掉 comfy_kernel（vendored 上游，不在验证范围）
    changed = [p for p in changed if not p.is_relative_to(PROJECT_ROOT / "comfy_kernel")]

    if not changed:
        print("[minimal_verify] 过滤后无有效变更文件（comfy_kernel 已排除）")
        return 0

    print(f"[minimal_verify] 检测到 {len(changed)} 个变更文件：")
    for p in changed:
        print(f"  - {p.relative_to(PROJECT_ROOT)}")

    # 构建验证步骤
    steps = build_verify_commands(changed, full=args.full)
    if not steps:
        print("\n[minimal_verify] 变更无需执行验证（非源码/测试文件）")
        return 0

    # 执行
    results: list[tuple[str, bool]] = []
    for description, cmd in steps:
        passed = run_command(cmd, description, dry_run=args.dry_run)
        results.append((description, passed))
        # 遇到失败立即停止后续步骤（快速反馈）
        if not passed and not args.dry_run:
            break

    # 摘要
    print_summary(results, dry_run=args.dry_run)

    # 退出码
    failures = [ok for _, ok in results if not ok]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
