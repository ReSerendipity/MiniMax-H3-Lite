"""防退化：database.py 引用的 docs/rollback_sop.md 必须存在且含 §4 schema 回滚节。

背景（运维稳定性评估 P1-3）：backend/database.py 两处引用 docs/rollback_sop.md，
但该文件此前不存在（悬空引用）。scripts/check_spec_refs.py 只扫 Markdown 相对链接，
代码注释里的文档路径不在其扫描面 —— 本测试把该引用变成可执行断言（安全合规落地
P2-5 同款 mark 复用）。
"""
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = pytest.mark.security


def test_database_rollback_doc_ref_resolves():
    """database.py 的 docs/rollback_sop.md 引用必须可解析到含 §4 的真实文件。"""
    db_text = (PROJECT_ROOT / "backend" / "database.py").read_text(encoding="utf-8")
    assert re.search(r"docs/rollback_sop\.md", db_text), "database.py 的引用点丢失？请核对 §4 语义是否迁移"

    doc = PROJECT_ROOT / "docs" / "rollback_sop.md"
    assert doc.exists(), "docs/rollback_sop.md 缺失 —— database.py 悬空引用回归"

    text = doc.read_text(encoding="utf-8")
    assert ("§4" in text) or ("## 4" in text), "rollback_sop.md 缺少 §4（数据库 schema 回滚）节"
    # 引用语义锚点：database.py 承诺 §4 承载「先备份 data/mmh3.db 再处理」的步骤
    assert "backup_data.py" in text and "user_version" in text, "§4 未覆盖备份与 user_version 处置"
