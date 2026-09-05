"""MM·H3 工作台 — 版本单一事实来源。

规则（2026-09-05 · 发布版本管理评估 P0 修复）：
- 版本号以仓库根 ``.release-please-manifest.json`` 为准，由 release-please 自动维护。
- 本仓无 ``pyproject.toml``（依赖走 ``requirements.txt``），因此 manifest 即唯一权威版本源。
- 代码（FastAPI ``app.version``）、日志一律从此处取值；禁止在任何位置硬编码版本号。
"""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST_NAME = ".release-please-manifest.json"
MANIFEST_ROOT_KEY = "."
FALLBACK_VERSION = "0.0.0-dev"


def manifest_path(root: Path | None = None) -> Path:
    """返回 release-please manifest 的绝对路径（默认取仓库根）。"""
    base = root if root is not None else Path(__file__).resolve().parent.parent
    return base / MANIFEST_NAME


def read_manifest_version(root: Path | None = None) -> str:
    """读取 manifest 中根包版本号；文件缺失或内容损坏时回退 FALLBACK_VERSION。

    回退而不是抛错：本地开发（如从源码树外拷贝运行）不应因读不到 manifest 而崩溃，
    但回退值必须以 ``-dev`` 结尾，便于一眼识别「版本未注入」。
    """
    try:
        data = json.loads(manifest_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FALLBACK_VERSION
    value = data.get(MANIFEST_ROOT_KEY) if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else FALLBACK_VERSION


__version__ = read_manifest_version()

__all__ = [
    "__version__",
    "read_manifest_version",
    "manifest_path",
    "MANIFEST_NAME",
    "MANIFEST_ROOT_KEY",
    "FALLBACK_VERSION",
]
