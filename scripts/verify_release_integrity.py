#!/usr/bin/env python3
"""发布门禁五步 — 完整性防线（任务书阶段三 P1-②）。

五步（对齐报告2 §3.2 SOP-19 门禁 + 本仓库分发形态=Docker 镜像）：
  ① 构建验证     compileall backend/ + scripts/（字节码编译，语法/编码门禁）
  ② 拆包验证     自检 full：清单条目逐一哈希比对 + Ed25519 验签
  ③ 负向断言     分发内容不含 data/.manifest_signing_key、.watermark_key；
                 打包环境未注入 MMH3_SIGN_KEY
  ④ 篡改模拟     临时副本篡改 1 字节 → 自检 failed + enforce 拒绝启动
  ⑤ 冒烟启动     真实 FastAPI 启动（health=200），自检在 startup 事件执行

执行域：
- 本机无 docker CLI → 默认走本地 venv + 真实启动路径（降级已在《执行对照表》
  留痕）；有 docker 时加 --docker 走 docker build + docker run 内验证（容器内
  执行 diag_integrity.py --quick + 自检）。
- CI 只调脚本路径（不内联 python -c）；退出码 0 全通过 / 1 任一失败。

用法:
    python scripts/verify_release_integrity.py [--docker]
"""
from __future__ import annotations

import argparse
import compileall
import os
import shutil
import subprocess  # nosec B404 - 发布门禁主动调用 docker CLI，list 形参无 shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<6} {detail}")
    return ok


def step_build() -> bool:
    ok = compileall.compile_dir(str(ROOT / "backend"), quiet=1, force=True)
    ok2 = compileall.compile_dir(str(ROOT / "scripts"), quiet=1, force=True)
    return step("build", ok and ok2, "compileall backend/ + scripts/")


def step_unpack() -> bool:
    from backend.security.integrity_selfcheck import run_startup_selfcheck
    try:
        r = run_startup_selfcheck(root_dir=ROOT, enforce=False)
    except Exception as e:  # noqa: BLE001
        return step("unpack", False, f"自检异常: {e!r}")
    ok = r.failed == 0 and r.signature_valid is True
    detail = f"清单 {r.passed}/{r.total} 通过，失败 {r.failed}，跳过 {r.skipped}，签名 {'PASS' if r.signature_valid else 'FAIL'}"
    return step("unpack", ok, detail)


def _dockerignore_patterns() -> list[str]:
    """读取 .dockerignore 规则（忽略注释/空行）。"""
    path = ROOT / ".dockerignore"
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def _dockerignore_match(patterns: list[str], rel: str) -> bool:
    """模拟 .dockerignore 语义：pattern 无前导 / 时匹配任意深度；目录 pattern 匹配整棵子树。"""
    import fnmatch
    parts = Path(rel).parts
    for pat in patterns:
        p = pat.rstrip("/")
        if "/" not in p and p not in ("*", "**"):
            # 无路径分隔符 → 匹配任意深度的同名段
            if p in parts or fnmatch.fnmatch(rel, f"**/{p}/**") or fnmatch.fnmatch(rel, f"**/{p}"):
                return True
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p + "/*") or rel.startswith(p + "/"):
            return True
    return False


def _release_context_files() -> list[Path]:
    """按 .dockerignore 语义列出「会 COPY 进镜像」的构建上下文文件。"""
    patterns = _dockerignore_patterns()
    out: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(".git/") or rel.startswith(".venv/") or rel.startswith("docs/agents/"):
            continue
        if not _dockerignore_match(patterns, rel):
            out.append(p)
    return out


def step_negative() -> bool:
    problems: list[str] = []
    # 入包范围（= docker 构建上下文）内不得出现私钥/水印密钥/secret/缓存
    for p in _release_context_files():
        rel = p.relative_to(ROOT).as_posix()
        low = rel.lower()
        if any(k in low for k in (".manifest_signing_key", ".watermark_key", ".env", "secret")):
            problems.append(f"敏感文件将随镜像分发: {rel}")
        if "__pycache__" in low or low.endswith(".pyc"):
            problems.append(f"字节码缓存将随镜像分发: {rel}")
    if os.environ.get("MMH3_SIGN_KEY"):
        problems.append("打包环境注入了 MMH3_SIGN_KEY（不得随发布配置导出）")
    return step("negative", not problems, "; ".join(problems) if problems else "入包内容无私钥/水印密钥/缓存/secret 泄露")


def step_tamper() -> bool:
    from backend.security.integrity_selfcheck import run_startup_selfcheck
    tmp = Path(tempfile.mkdtemp(prefix="mmh3-release-tamper-"))
    try:
        shutil.copytree(ROOT / "backend", tmp / "backend")
        target = tmp / "backend" / "config.py"
        b = target.read_bytes()
        target.write_bytes(b + b" ")
        r = run_startup_selfcheck(root_dir=tmp, enforce=False)
        blocked = False
        try:
            run_startup_selfcheck(root_dir=tmp, enforce=True)
        except RuntimeError:
            blocked = True
        ok = r.failed == 1 and "backend/config.py" in r.failed_files and blocked
        detail = f"篡改 1 字节被检出（failed={r.failed}）→ enforce 拒绝启动={'是' if blocked else '否！'}"
        return step("tamper", ok, detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def step_smoke() -> bool:
    os.environ.setdefault("MMH3_DB_PATH", ":memory:")
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        with client:
            r = client.get("/api/health")
        return step("smoke", r.status_code == 200, f"启动自检通过，health={r.status_code}")
    except RuntimeError as e:
        return step("smoke", False, f"启动被自检拒绝: {str(e)[:120]}")
    except Exception as e:  # noqa: BLE001
        return step("smoke", False, f"启动异常: {e!r}")


def step_docker() -> tuple[bool, str]:
    """Docker 路径（本机有 docker 时）；构建 + 容器内诊断。"""
    if shutil.which("docker") is None:
        return True, "SKIP：本机无 docker CLI——门禁走本地降级路径（对照表已留痕）"
    # docker 固定参数、list 形参无 shell；B603 对显式 ID nosec 不响应（bandit 1.7.7），故用无 ID
    build = subprocess.run(  # nosec
        ["docker", "build", "-t", "mmh3-release-check", "."],
        capture_output=True, text=True, timeout=600)
    if build.returncode != 0:
        return False, f"docker build 失败: {build.stderr.strip()[-300:]}"
    # docker 固定参数、list 形参无 shell；B603 对显式 ID nosec 不响应（bandit 1.7.7），故用无 ID
    run = subprocess.run(  # nosec
        ["docker", "run", "--rm", "--entrypoint", "python", "mmh3-release-check",
         "scripts/diag_integrity.py", "--quick"],
        capture_output=True, text=True, timeout=300,
    )
    if run.returncode != 0:
        return False, f"容器内诊断失败: {(run.stdout or run.stderr).strip()[-300:]}"
    return True, f"docker build + 容器内诊断 PASS（{run.stdout.strip().splitlines()[-1]}）"


def main() -> int:
    parser = argparse.ArgumentParser(description="发布门禁五步（完整性）")
    parser.add_argument("--docker", action="store_true", help="额外执行 docker build + 容器内验证")
    args = parser.parse_args()

    ok = True
    ok &= step_build()
    ok &= step_unpack()
    ok &= step_negative()
    ok &= step_tamper()
    ok &= step_smoke()
    if args.docker:
        d_ok, d_detail = step_docker()
        ok &= d_ok
        RESULTS.append(("docker", d_ok, d_detail))

    print("─" * 40)
    for name, passed, detail in RESULTS:
        print(f"[{'PASS' if passed else 'FAIL'}] {name:<6} {detail}")
    print("RELEASE GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
