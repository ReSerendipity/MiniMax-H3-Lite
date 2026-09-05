"""MM·H3 工作台后端包。

版本号经 ``backend.version`` 从 release-please manifest 派生（禁止硬编码）。
"""
try:  # 包形态：uvicorn backend.main:app / 测试 from backend.main import app
    from backend.version import __version__
except ImportError:  # pragma: no cover - 扁平形态兜底（backend 目录在 sys.path）
    from version import __version__  # type: ignore[no-redef]

__all__ = ["__version__"]
