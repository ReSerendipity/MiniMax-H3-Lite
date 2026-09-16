"""MM·H3 工作台 — 版本单一事实来源。

规则（2026-09-05 · 发布版本管理评估 P0 修复；2026-09-16 修订）：
- release-please 已于 2026-09-16 停用（bbe6996 / dba745e / 37fb127），发布改为
  人工 tag 驱动；版本号以仓库根 ``package.json`` 的 ``version`` 字段为唯一权威
  来源，发版时人工随 tag 同步（原 ``.release-please-manifest.json`` 已删除，
  见 ``docs/adr/0004-release-version-governance.md`` 修订注记）。
- 本仓无 ``pyproject.toml``（依赖走 ``requirements.txt``），因此 package.json
  即唯一权威版本源。
- 代码（FastAPI ``app.version``）、日志一律从此处取值；禁止在任何位置硬编码版本号。
"""
from __future__ import annotations

import json
from pathlib import Path

PACKAGE_JSON_NAME = "package.json"
VERSION_KEY = "version"
FALLBACK_VERSION = "0.0.0-dev"


def package_json_path(root: Path | None = None) -> Path:
    """返回 package.json 的绝对路径（默认取仓库根）。"""
    base = root if root is not None else Path(__file__).resolve().parent.parent
    return base / PACKAGE_JSON_NAME


def read_project_version(root: Path | None = None) -> str:
    """读取 package.json 的 ``version`` 字段；文件缺失或内容损坏时回退 FALLBACK_VERSION。

    回退而不是抛错：本地开发（如从源码树外拷贝运行）不应因读不到 package.json
    而崩溃，但回退值必须以 ``-dev`` 结尾，便于一眼识别「版本未注入」。
    """
    try:
        data = json.loads(package_json_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FALLBACK_VERSION
    value = data.get(VERSION_KEY) if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else FALLBACK_VERSION


__version__ = read_project_version()

__all__ = [
    "__version__",
    "read_project_version",
    "package_json_path",
    "PACKAGE_JSON_NAME",
    "VERSION_KEY",
    "FALLBACK_VERSION",
]
