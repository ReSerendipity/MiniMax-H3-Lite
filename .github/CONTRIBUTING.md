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
- NVIDIA GPU (CUDA) for model inference
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

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0 (see [LICENSE](../LICENSE)).

## 模型许可注意

本仓库不包含模型权重；使用 MiniMax H3 模型须遵守其 Community License Agreement（见 [NOTICE](../NOTICE)，含地域/商用门槛限制）。

---

Thank you for contributing — the community makes this project better!
