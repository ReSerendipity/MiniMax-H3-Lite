"""参数契约版本测试（AI/ML 评估 P2 · 契约变更留痕）。

与 tests/test_schema_version.py（DB schema 版本）互补：
前者管参数契约（h3.spec），后者管存储结构（database.SCHEMA_VERSION）。
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from h3.spec import SPEC_VERSION, MODELS, RESOLUTION_PRESETS, DURATION_MIN, DURATION_MAX  # noqa: E402


def test_spec_version_exists_and_semver():
    """SPEC_VERSION 必须存在且为 SemVer（x.y.z），供变更留痕与下游消费。"""
    assert isinstance(SPEC_VERSION, str) and SPEC_VERSION
    assert re.fullmatch(r"\d+\.\d+\.\d+", SPEC_VERSION), f"SPEC_VERSION 应为 SemVer: {SPEC_VERSION!r}"


def test_spec_version_key_contracts_present():
    """版本化契约的关键常量必须存在（防误删导致契约静默漂移）。"""
    assert MODELS["clip"].endswith(".safetensors")
    assert "0.98" in RESOLUTION_PRESETS
    assert DURATION_MIN < DURATION_MAX


def test_spec_version_change_requires_revision_note():
    """契约变更必须同步修订记录：SPEC_VERSION 定义旁的注释块应含修订登记入口。"""
    import inspect
    from h3 import spec
    src = inspect.getsource(spec)
    assert "SPEC_VERSION = " in src, "应定义 SPEC_VERSION 常量"
    assert "变更规则" in src, "应声明契约变更规则（何种改动需 +1）"
    assert "修订记录" in src, "应含修订记录登记（变更 +1 时追加条目）"
    # 修订记录应位于 SPEC_VERSION 定义附近（±30 行），确保二者绑定
    idx = src.index("SPEC_VERSION = ")
    window = src[max(0, idx - 1500): idx + 500]
    assert "修订记录" in window, "修订记录须与 SPEC_VERSION 定义同处（防版本号与留痕脱钩）"
