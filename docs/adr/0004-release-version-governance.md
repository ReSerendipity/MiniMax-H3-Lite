# ADR 0004：发布版本治理（版本单一来源 + 门禁恢复阻断）

- **状态**：Implemented
- **日期**：2026-09-05
- **决策者**：仓库所有者（全权委托执行）
- **来源**：发布版本管理评估（P0 版本口径分裂 / P1 门禁弱化 / P1 版本历史断层）

---

## 背景

评估发现四类问题：

1. **版本口径分裂**：FastAPI `app.version="0.1.0"`、AGENTS.md 与 release-governance.md 自述 v0.1.0，而 manifest/CHANGELOG/tag 为 `2.3.1`；`package.json` 亦为 `0.1.0`，且不在 release-please 同步范围内。
2. **发布门禁被弱化**：`release-please.yml` 带 `continue-on-error: true`，且 `skip-github-pull-request: true` —— 发布失败静默、版本晋升无人工审查。
3. **测试门禁残留弱化**：`test.yml` 覆盖率门槛 40% 与 `pytest.ini` 60% 不一致，前端 smoke 仍带 `continue-on-error` + `|| true`。
4. **版本历史断层**：manifest 自 2.3.0 bootstrap，tag 仅 `v0.1.0/2.3.0/2.3.1`，CHANGELOG 的 `v2.2.0` compare 链接指向不存在的 tag。

本仓为开源社区单机工具（无灰度/多环境/回滚流水线），发布治理的目标是可重复、可追溯、可回滚到 tag。

---

## 决策

### D1 版本单一事实来源 = `.release-please-manifest.json`

- 新增 `backend/version.py`：读 manifest，缺失/损坏回退 `0.0.0-dev`（`-dev` 后缀便于识别未注入）。
- `backend/__init__.py` 导出 `__version__`；`backend/main.py` 的 `app.version` 改为 `APP_VERSION`（try 扁平导入 / except 包形态兜底）。
- `release-please-config.json` 增加 `extra-files`：`package.json:$.version`，发版时自动同步前端包版本。
- `trivy.yml` 镜像 `VERSION` build-arg 由写死 `0.1.0` 改为运行时读 manifest。
- 防回归：`tests/test_version_consistency.py`（11 用例，含「CI 无旧版本号」「门禁未被弱化」「覆盖率门槛与 pytest.ini 一致」）。

**为什么不用 pyproject.toml**：本仓无 `pyproject.toml`，依赖走 `requirements.txt` + `requirements-lock.txt`；为版本引入打包元数据属于过度改造，且与 release-please `simple` 类型（不改任何源文件）不匹配。

### D2 发布门禁恢复阻断，恢复 release PR 审查

- 移除 `release-please.yml` 的 `continue-on-error: true` → 发布失败即红叉，不再静默。
- `skip-github-pull-request: false` → 版本晋升经 release PR 人工审查（版本号、CHANGELOG 分区、package.json 同步）。
- `test.yml`：覆盖率门槛 40 → 60（与 `pytest.ini` 一致，实测 69.25%）；前端 smoke 移除 `continue-on-error` 与 `|| true`（实测 57/57 通过）。
- 依据：`docs/agents/QUALITY_CONTRACT.md` §10.2/§10.4 明确禁止以 `continue-on-error` / `|| true` 掩盖失败。

### D3 保留 2.3.1 基线，断层以文档显式记录

- 不改 manifest、不伪造 1.x/2.0–2.2 的 tag 或 CHANGELOG 条目（避免 tag 冲突与伪造发布史）。
- 新增 `docs/version-baseline.md` 记录断层来源与取舍；`AGENTS.md` 与 `release-governance.md` 同步标注。

### D4 治理文档收敛为一套

`docs/release-governance.md` 原写「手动打 tag + Keep a Changelog `[Unreleased]`」，与实际 release-please 自动化互斥。已重写 §1–3、§8 对齐实际机制（conventional commits → release PR → 自动 tag/Release）。

---

## 影响

- 正面：版本对外一致；发布失败可见；前端包版本不再漂移；覆盖率口径统一。
- 代价：release-please 失败会让 main 变红（需按 `FIX_LOG.md` 流程止损）；CI 覆盖率门槛提高 20 个百分点（当前余量约 9 个百分点，新增代码需同步补测）。
