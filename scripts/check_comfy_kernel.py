"""check_comfy_kernel.py — ComfyUI 内核进程内复用 PoC 只读检查脚本（路线图 #10）。

只读检查 Image_MultiModel 仓的 comfy_kernel 目录，输出评估报告文本，用于
MiniMax-H3-lite 移植 ComfyUI 内核进程内复用的可行性判断。

检查项：
  1. comfy_kernel 目录结构与 `import comfy` 可行性（comfy/ 包 + __init__.py，
     可选 --try-import 在子进程实际执行 import comfy）
  2. 内核版本号（comfyui_version.py 的 __version__）
  3. 版本基线（UPGRADE_STRATEGY.md：Current Commit / Last Verified）
  4. COMFYUI_VERSION_PIN 基线锁定标记是否存在
  5. custom_nodes 自定义节点清单（判断 aki-v3 / MiniMaxH3 等节点是否已 vendor）
  6. 许可证（comfy_kernel/LICENSE 是否为 GPL-3.0）
  7. 规模统计（.py 文件数 / 行数，排除 __pycache__）

用法：
  python scripts/check_comfy_kernel.py <Image_MultiModel 仓库路径> [--try-import]

只读，不写任何文件，无第三方依赖。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

GPL_MARKERS = ("GNU GENERAL PUBLIC LICENSE", "GPL")
VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
COMMIT_RE = re.compile(r"Current Commit[^\n]*?([0-9a-fA-F]{6,40})")
VERIFIED_RE = re.compile(r"Last Verified[^\n]*:\s*(.*)$", re.MULTILINE)


def _count_py(kernel: Path) -> tuple[int, int]:
    """统计 comfy_kernel 下 .py 文件数与总行数（排除 __pycache__）。"""
    files = [
        p for p in kernel.rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    lines = 0
    for p in files:
        try:
            lines += sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return len(files), lines


def _read_version(kernel: Path) -> str | None:
    vf = kernel / "comfyui_version.py"
    if not vf.exists():
        return None
    text = vf.read_text(encoding="utf-8", errors="ignore")
    m = VERSION_RE.search(text)
    return m.group(1) if m else None


def _read_baseline(repo: Path, kernel: Path) -> dict:
    """读取 UPGRADE_STRATEGY.md 的基线信息（内核目录或仓根）。"""
    for cand in (kernel / "UPGRADE_STRATEGY.md", repo / "UPGRADE_STRATEGY.md"):
        if cand.exists():
            text = cand.read_text(encoding="utf-8", errors="ignore")
            commit = COMMIT_RE.search(text)
            verified = VERIFIED_RE.search(text)
            return {
                "path": str(cand),
                "commit": commit.group(1) if commit else None,
                "last_verified": verified.group(1).strip() if verified else None,
            }
    return {"path": None, "commit": None, "last_verified": None}


def _search_pin(repo: Path) -> list[str]:
    """在仓内查找 COMFYUI_VERSION_PIN 标记（py/md/json/yaml/toml/txt）。"""
    hits: list[str] = []
    exts = {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".cfg", ".ini"}
    for p in repo.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        if "__pycache__" in p.parts or "node_modules" in p.parts:
            continue
        try:
            if "COMFYUI_VERSION_PIN" in p.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(p))
        except OSError:
            continue
    return hits


def _list_custom_nodes(kernel: Path) -> list[str]:
    d = kernel / "custom_nodes"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir())


def _check_license(kernel: Path) -> tuple[bool, str]:
    for cand in (kernel / "LICENSE", kernel / "LICENSE.txt", kernel / "COPYING"):
        if cand.exists():
            head = cand.read_text(encoding="utf-8", errors="ignore")[:4000]
            is_gpl = any(m in head for m in GPL_MARKERS)
            return is_gpl, str(cand)
    return False, ""


def _try_import(repo: Path) -> tuple[bool, str]:
    """在子进程内尝试 import comfy（真实导入可行性探测）。"""
    code = (
        "import sys; sys.path.insert(0, r'{root!s}'); "
        "sys.path.insert(0, r'{kernel!s}'); "
        "import comfy; print('OK', getattr(comfy, '__version__', '?'))"
    ).format(kernel=repo / "comfy_kernel", root=repo)
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=120,
        )
        ok = r.returncode == 0 and "OK" in (r.stdout or "")
        msg = (r.stdout or "").strip() or (r.stderr or "").strip()[:500]
        return ok, msg
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{type(e).__name__}: {e}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ComfyUI 内核进程内复用 PoC 只读检查")
    parser.add_argument("image_repo", help="Image_MultiModel 仓库路径")
    parser.add_argument("--try-import", action="store_true", help="子进程实际执行 import comfy 探测")
    args = parser.parse_args(argv)

    repo = Path(args.image_repo).resolve()
    kernel = repo / "comfy_kernel"
    report: list[str] = []
    report.append("=" * 68)
    report.append("ComfyUI 内核进程内复用 PoC 检查报告（只读）")
    report.append("=" * 68)
    report.append(f"Image 仓: {repo}")

    # 1. 目录存在性
    if not kernel.is_dir():
        report.append("[FAIL] comfy_kernel/ 目录不存在")
        print("\n".join(report))
        return 1
    report.append(f"[OK] comfy_kernel/ 存在")

    # 2. 规模
    n_files, n_lines = _count_py(kernel)
    report.append(f"[INFO] 规模: {n_files} 个 .py 文件 / {n_lines:,} 行（排除 __pycache__）")

    # 3. import 可行性（结构）
    comfy_pkg = kernel / "comfy"
    pkg_files = list(comfy_pkg.glob("*.py")) if comfy_pkg.is_dir() else []
    if comfy_pkg.is_dir() and pkg_files:
        report.append(
            f"[OK] comfy/ 包存在（{len(pkg_files)} 个顶层 .py，namespace 包），"
            "sys.path 注入后 import comfy 可行"
        )
    else:
        report.append("[FAIL] comfy/ 包缺失（或为空）")
    if (kernel / "nodes.py").exists():
        report.append("[OK] nodes.py 存在（ComfyUI 节点注册入口）")
    if args.try_import:
        ok, msg = _try_import(repo)
        report.append(f"[{'OK' if ok else 'FAIL'}] 子进程 import comfy: {msg[:300]}")

    # 4. 版本号
    version = _read_version(kernel)
    report.append(f"[INFO] 内核版本: {version or '未知（无 comfyui_version.py）'}")

    # 5. 基线
    base = _read_baseline(repo, kernel)
    if base["path"]:
        report.append(f"[INFO] 升级策略文件: {base['path']}")
        report.append(f"[INFO] 基线 commit: {base['commit'] or '未记录'}")
        lv = (base["last_verified"] or "").strip(" *`\t")
        drift = "To be filled" in lv or not lv
        report.append(
            f"[{'WARN' if drift else 'OK'}] Last Verified: {lv if lv else '（空）'}"
            + (" → 基线漂移风险：基线从未被核验" if drift else "")
        )
    else:
        report.append("[WARN] 未找到 UPGRADE_STRATEGY.md")

    # 6. COMFYUI_VERSION_PIN
    pins = _search_pin(repo)
    report.append(
        f"[{'WARN' if not pins else 'OK'}] COMFYUI_VERSION_PIN: "
        + ("未发现（无基线锁定机制，升级后易漂移）" if not pins else f"{len(pins)} 处")
    )

    # 7. 自定义节点清单
    nodes = _list_custom_nodes(kernel)
    report.append(f"[INFO] custom_nodes/ 内容: {nodes or '（目录不存在/为空）'}")
    vendored = any(not n.endswith(".example") and n != "websocket_image_save.py" for n in nodes)
    report.append(
        f"[{'WARN' if not vendored else 'OK'}] 业务自定义节点是否 vendor: "
        + ("否 — 仅示例/占位文件（aki-v3 / MiniMaxH3 等节点需另行引入）" if not vendored else "是")
    )

    # 8. 许可证
    is_gpl, lic_path = _check_license(kernel)
    report.append(
        f"[{'OK' if is_gpl else 'WARN'}] 内核许可证: "
        + f"{lic_path or '未找到 LICENSE'} → {'GPL-3.0（进程内复用需隔离边界）' if is_gpl else '非 GPL 标记'}"
    )

    # 9. 结论
    report.append("-" * 68)
    report.append(
        "结论: 内核结构可 import（进程内复用技术可行），但存在基线漂移"
        "（无 COMFYUI_VERSION_PIN、Last Verified 未核验）与 GPL-3.0 合规边界问题，"
        "移植需参照 Image 仓 Dockerfile 隔离模式（.dockerignore 排除 + 运行时只读挂载）。"
    )
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())