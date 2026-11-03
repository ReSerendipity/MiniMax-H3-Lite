# 架构 — MiniMax-H3-Lite

> 治理定位：`delivery=release`、`lifecycle=maintenance`（`governance/desired-state.json`）。
> 本文按 2026-11-03 的实际目录结构生成；数据流与边界须由维护者在实现变更时同步复核。

## 1. 定位

**[中文](#中文) | [English](#english)**

## 2. 组件与依赖方向

```text
应用层：desktop/ (26)
服务层：backend/ (47)
工具层：scripts/ (45)
资产层：assets/ (6)
测试层：tests/ (49)
支撑层：docs/ (35)、.github/ (29)
其他层：.githooks/ (10)、.ci/ (6)、workflows/ (6)、logs/ (1)
根级层：根级文件 (24)
```

| 组件 | 目录 | 文件数 | 代表文件 |
|---|---|---|---|
| `tests` | `tests/` | 49 | `tests/capture-screenshots.js`, `tests/conftest.py`, `tests/frontend/e2e/smoke.spec.js` |
| `backend` | `backend/` | 47 | `backend/__init__.py`, `backend/checkpoint.py`, `backend/cleanup.py` |
| `scripts` | `scripts/` | 45 | `scripts/_boot_check.py`, `scripts/_check_venvs.py`, `scripts/apply_branch_protection.py` |
| `docs` | `docs/` | 35 | `docs/CODING_STANDARDS.md`, `docs/EVAL.md`, `docs/GPL_COMPLIANCE.md` |
| `desktop` | `desktop/` | 26 | `desktop/package-lock.json`, `desktop/package.json`, `desktop/src-tauri/Cargo.lock` |
| 根级文件 | `/` | 24 | `.dockerignore`, `.editorconfig`, `.env.example` |
| `.githooks` | `.githooks/` | 10 | `.githooks/README.md`, `.githooks/commit-msg`, `.githooks/install.sh` |
| `.ci` | `.ci/` | 6 | `.ci/comfy_kernel_baseline.json`, `.ci/lock_coverage_allowlist.txt`, `.ci/mypy_baseline.txt` |
| `assets` | `assets/` | 6 | `assets/apple-touch-icon.png`, `assets/css/shared.css`, `assets/favicon-32.png` |
| `workflows` | `workflows/` | 6 | `workflows/api/video_minimax_h3_i2v.api.json`, `workflows/api/video_minimax_h3_r2v.api.json`, `workflows/api/video_minimax_h3_t2v.api.json` |
| `logs` | `logs/` | 1 | `logs/.gitkeep` |

依赖方向：入口层（应用 / 页面）调用领域层（业务模块），领域层依赖基础设施层（脚本、配置、模型资产）；反向引用不允许。

## 3. 数据流

前端提交任务 → 后端调度推理 → 清单签名与完整性校验 → 结果返回。

## 4. 外部依赖

| 依赖 | 用途 | 不可用时 |
|---|---|---|
| Python 依赖 | 推理后端 | 无法生成 |
| Node.js / npm | 桌面壳 | 仅剩 Web 端 |

## 5. 边界与非目标

- 发布链只走 §10：远端优先、tag 驱动、资产附 `SHA256SUMS.txt`。
- 分发产物由 CI 生成，不入库。
- 不入库：密钥 / token / 口令 / 连接串、本机绝对路径、`local/` 与 `AGENTS.md`、构建产物。
- 治理正文只在 `ReSerendipity/.github/governance`，本仓不复制规则正文。

## 6. 变更影响面

| 改什么 | 必须同步 | 由谁校验 |
|---|---|---|
| 目录结构 / 入口 | 本文「组件与依赖方向」与「数据流」 | 维护者 |
| CI 与门禁 | 本仓 `README.md` 的测试命令；治理仓 §20 远端载体口径 | `audit-drift.py` |
| 依赖清单 | 锁文件与 `.github/dependabot.yml` 的生态段 | Dependabot / `lock-consistency` |
| README 展示图 | §8.1 真实性红线（图必须来自真实运行） | 治理仓 `readme-image-provenance` |
