# Contributing to MiniMax-H3-lite

Thank you for your interest in contributing to MiniMax-H3-lite — a FastAPI + Jinja2 video generation workbench (T2V / I2V / R2V) built on MiniMax H3.

This document gives a short "10-minute quick start" to get contributors productive, and a concise reference for common contribution tasks.

---

## Quick Start (10 minutes)

1. Clone the repository

```bash
git clone https://github.com/ReSerendipity/MiniMax-H3-lite.git
cd MiniMax-H3-lite
```

2. Run (Windows)

```powershell
start.bat
```

3. Create a branch for your change

```bash
git checkout -b fix/short-description
# make changes, run tests, then push
git commit -m "fix(routers): short description"
git push origin fix/short-description
```

4. Open a Pull Request using the provided template.

---

## Development (local)

Prerequisites
- Python 3.10+ (3.12 recommended)
- NVIDIA GPU (CUDA) 用于模型推理测试
- Git

Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Run tests

```bash
pytest tests/ -v
```

Lint/format

```bash
ruff check backend/ scripts/
ruff format backend/ scripts/
```

---

## How to File Good Issues

- Bug reports: include environment (OS, Python, GPU), steps to reproduce, expected vs actual behavior, and logs.
- Feature requests: describe the use case, proposed solution, and any alternatives.

Use the provided issue templates (bug_report / feature_request).

---

## Pull Request Checklist

- Use a descriptive title and include a short summary in the PR body.
- Link related issues using `Closes #<issue>` when appropriate.
- Add tests for new behavior where feasible.
- Run tests & linters locally before opening the PR.
- Follow Conventional Commits for commit messages (`feat:`, `fix:`, `docs:`, etc.).

---

## 提交前必做（本地门禁）

> 目标：让每一次提交都能顺利通过 CI，而不是反复修。

### 本地门禁（提交前跑）

```bash
python scripts/check_config_refs.py   # config 引用一致性
python scripts/check_spec_refs.py     # 规范文件引用一致性
python scripts/clean_launch.py -h     # 启动自检（含 loopback 强制）
```

> CI 是唯一权威门禁。git push --no-verify 可绕过（不推荐）。

### 编码卫生

- 所有源码/文本文件必须为 UTF-8 无 BOM（.gitattributes 已统一 LF 行尾）
- 禁止用第三方编码转换工具批量改写源文件后直接提交
- 本地检查会自动扫描全部被跟踪文本文件的 UTF-8 合法性

### 新增依赖

- 运行依赖 → requirements.txt；测试/开发依赖 → requirements-dev.txt
- 不要只 pip install 后就不管：CI 从干净环境只装 requirements，漏写必红

### 覆盖率门槛

- 只在 CI 判定（跨平台数值有差异，本地不判）；CI 红在覆盖率时补测试而不是调门槛
- 家族约定：阈值不高于 40%，防止贡献者被门槛劝退

### CI 红了先看什么

| 现象 | 常见根因 | 处理 |
|---|---------|------|
| cancelled | 连续 push 取消旧 run | **不是失败**，看最新 run |
| ruff/black 红 | 没跑本地门禁 | python scripts/check_local.py 修复后重推 |
| mypy 红 | 类型错误 | 本地 python -m mypy backend 先修 |
| pytest 红 | 测试失败/缺依赖 | 本地 --full 复现；缺依赖补 requirements |
| 覆盖率红 | 新代码没测 | 补测试 |
| SyntaxError/乱码 | 编码损坏 | 本地 UTF-8 扫描定位修复 |

---

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).

## 模型许可注意

本仓库不包含模型权重；使用 MiniMax H3 模型须遵守其 Community License Agreement（见 [NOTICE](NOTICE)，含地域/商用门槛限制）。

---

Thank you for contributing — the community makes this project better!