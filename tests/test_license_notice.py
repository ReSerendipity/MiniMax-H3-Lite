"""NOTICE / THIRD_PARTY_NOTICES 必须显式声明 vendored 组件的 GPL-3.0 身份。

防退化：AGENTS 与合规文档都要求"分发须履行 GPL 义务"，但这句话此前只写在
gitignored 的 docs/ 里 —— 干净 checkout 拿不到，任何人都能静默删掉 NOTICE
的许可声明而 CI 毫无反应。本测试与 CI 的 license-notice-check 断言同语义，
只覆盖**入库文件**；`docs/GPL_COMPLIANCE.md` 位于 `docs/` 的 gitignore 模式之下、
仅因 `git add -f` 才入库，这种"靠一次强制添加维持"的事实不能当隐式前提，
故由下面的 test_compliance_doc_is_tracked 显式断言。
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def test_notice_declares_kernel_gpl():
    text = _read("NOTICE")
    assert "comfy_kernel" in text
    assert re.search(r"GPL-?3\.0", text), "NOTICE 必须点明内核为 GPL-3.0"


def test_notice_declares_aimdo_gpl():
    assert re.search(r"comfy-?aimdo", _read("NOTICE"), re.I)


def test_third_party_notices_no_unverified_license():
    text = _read("THIRD_PARTY_NOTICES.md")
    for line in text.splitlines():
        if "comfy" in line.lower() and "未核验" in line:
            raise AssertionError(f"许可证不得停留在未核验状态: {line.strip()}")


def test_compliance_doc_is_tracked():
    """docs/GPL_COMPLIANCE.md 必须入库——它是分发物（§2 方式 A 要求随包）。"""
    import subprocess
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "docs/GPL_COMPLIANCE.md"],
        cwd=PROJECT_ROOT, capture_output=True,
    )
    assert r.returncode == 0, "docs/GPL_COMPLIANCE.md 未入库，分发物将缺少它"
