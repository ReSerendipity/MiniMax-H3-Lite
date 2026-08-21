"""
render_pages.py — 将 Jinja2 页面模板渲染为 HTML，供前端 smoke 测试读取。

改造后前端由 FastAPI + Jinja2 单端口直出，不再有根目录独立 HTML。
jsdom smoke 测试无法执行 Jinja2，因此先由本脚本把三个页面模板
渲染到 tests/frontend/_rendered/ ，smoke.js 再读取。

用法: python scripts/render_pages.py
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "backend" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "frontend" / "_rendered"

PAGES = ["t2v", "i2v", "r2v"]


def main() -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in PAGES:
        html = env.get_template(f"{name}.html").render()
        (OUTPUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"[OK] 渲染 {name}.html -> tests/frontend/_rendered/")


if __name__ == "__main__":
    main()