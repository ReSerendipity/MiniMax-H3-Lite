# 发布 / 回滚 规范（MM·H3 工作台 / MiniMax-H3-Lite）

> **来源与权威**：公共条款见 `ReSerendipity/.github` 的 `REPOSITORY_GUIDELINES.md` §10（发布 / 分发统一规范）；
> 本文件按其模板 `RELEASE_GOVERNANCE_TEMPLATE.md` 的结构落地，只填**本仓特有**内容，**不重写也不抵触 §10 的公共条款**。
> 建立：2026-10-18。文中事实均于当日对 `main`（默认分支）实测取证，取证来源见各条括注。

---

## 0. 远端优先（根原则，不可改写）

发布链的构建、打包、扫描、上传、推送**全部在 GitHub Actions 远端完成**；本地只做三件事：改版本位、落 CHANGELOG、`git tag` + `git push`。本地不执行打包 / 镜像构建 / 发布上传。

本仓落地形态：`release.yml` 在 runner 上组装源码包、两份 SHA256SUMS 与 SBOM 并挂 Release（`release.yml`）；`ghcr.yml` 在 runner 上构建并推送容器镜像（`ghcr.yml`）；本地不做上述任一步。

## 1. 版本号规范

- 遵循 **SemVer** `MAJOR.MINOR.PATCH`；预发布用 `-alpha.N` / `-beta.N` / `-rc.N`。
- **唯一权威版本位**：仓库根 `package.json` 的 `version` 字段（当前 `2.6.0`）。本仓无 `pyproject.toml` / `setup.py`，依赖走 `requirements.txt`，故 `package.json` 即唯一权威版本源（`docs/adr/0004-release-version-governance.md`；`backend/version.py` 头注同此）。
- 必须同步的其它版本位：`desktop/package.json` 的 `version`、`desktop/src-tauri/tauri.conf.json` 的 `version`、`desktop/src-tauri/Cargo.toml` 的 `[package].version`（三件套当前均 `2.6.0`）；运行时位 FastAPI `app.version`（由 `backend/version.py` 读取 `package.json`，禁止硬编码）；发版位 git tag `v<X.Y.Z>` 与 Release 标题；`CHANGELOG.md` 的版本二级标题。
- 版本位漂移由 `tests/test_version_consistency.py` 钉住——**漂一处即判红**（覆盖 `package.json` ↔ `backend.__version__` ↔ `app.version`、桌面壳版本三件套、`main.py` 无硬编码版本、CI 无旧版本号 `0.1.0`、覆盖率门槛与 `pytest.ini` 一致等断言；`AGENTS.md` 相关断言仅在本地存在该文件时执行，干净 CI checkout 中跳过）。
- 自动化方式：**手动 tag（人工）**。release-please 已于 2026-09-16 停用（工作流 `release-please.yml` 删除，`.release-please-manifest.json` / `release-please-config.json` 一并清理），**无任何自动 bump**；发版由人改 `package.json` 后打 tag。`release.yml` 与 `ghcr.yml` 均在动手前比对「tag 版本 == `package.json` 的 `version`」，不一致直接失败。

## 2. CHANGELOG 管理

- `CHANGELOG.md` **已存在**（仓库根）。
- 现行形态：顶部 `## [Unreleased]`，其下按 conventional 分区（`### Features` / `### Bug Fixes` / `### CI/CD` / `### AI/ML 工程` 等）；发版小节为 GitHub 释放式标题 `## [X.Y.Z](…/compare/vX.Y.Z...vA.B.C) (YYYY-MM-DD)`。`release.yml` 的 `publish-release` 会从对应二级标题节抽取发版说明（抽不到则回退 `--generate-notes`）。
- 每次合并 `main` 在 `[Unreleased]` 追加条目；发版时把 `[Unreleased]` 内容归入新的 `[VERSION] - YYYY-MM-DD` 小节。
- **命名差异（记录，待收敛）**：本仓分区名为 conventional 语义（`Features` / `Bug Fixes`），与 §10.2 的 Keep a Changelog 类别名（Added / Changed / Fixed）**命名不一致**，语义可一一对应（feat→Features/Added、fix→Bug Fixes/Fixed、refactor→Changed）。本仓尚未按 Keep a Changelog 类别名收敛。

## 3. 发布流程（远端）

1. 确认 `[Unreleased]` 条目完整
2. 同步版本位（见 §1 清单）——改根 `package.json`，再让桌面三件套跟随
3. 本地打 tag 并推送：`git tag v<X.Y.Z>` → `git push origin v<X.Y.Z>`（tag 版本必须等于 `package.json` 的 `version`，否则 `release.yml` / `ghcr.yml` 立刻红）
4. 远端凭 tag 触发两条链：`release.yml` 组装源码包 + `SHA256SUMS` + `SHA256SUMS.scripts` + SBOM；`ghcr.yml` 构建并推送容器镜像
5. `release.yml` 的 `publish-release` 建 Release 并挂资产（`gh release create --verify-tag`；tag 已有 Release 时改为 `gh release upload --clobber` 补 / 覆盖资产）
6. 盯到终态：`gh run list` 确认绿；红了当场修或 `git revert` 止损

- **dry-run 边界（结构保证）**：`release.yml` 的 `workflow_dispatch` **恒为 dry-run**（只构建并上传为 workflow artifact，不建 Release、不推 tag）；其 `pull_request` 触发只跑只读构建侧（`publish-release` 由 `dry_run` 门控，PR 永不到达）。**真发版只能由人推 `v<数字>` 形状的 tag 触发**。

## 4. 分发产物与完整性

| 产物 | 构建位置 | 标签 / 命名 | 完整性手段 |
|---|---|---|---|
| 源码包 | **远端**（`release.yml`） | `MiniMax-H3-lite-<X.Y.Z>.tar.gz` / `.zip`（`git archive`，只含已跟踪文件） | `SHA256SUMS` + `SHA256SUMS.scripts`（关键入口清单单独校验） |
| SBOM | **远端**（`release.yml`） | `sbom-python.cdx.json` / `sbom-npm.cdx.json`（CycloneDX） | 随 Release 资产归档 |
| 容器镜像 | **远端**（`ghcr.yml`） | `ghcr.io/reserendipity/minimax-h3-lite:<X.Y.Z>` | 见下方扫描口径 |
| 桌面安装包（Tauri/NSIS） | **本地**（`scripts/assemble_desktop_staging.ps1` + `scripts/make_desktop_volumes.ps1` + `scripts/installer/setup.nsi`） | `MMH3Workbench` 安装器 | `SHA256SUMS.desktop` 哈希 |

- **不产 wheel / sdist**：本仓无 `pyproject.toml` / `setup.py`，是应用非库（`release.yml` 内注释明确，姊妹仓 TTS 因有 `pyproject.toml` 才出 wheel）。
- **前端无独立可分发静态站**：页面由 FastAPI + Jinja2 单端口服务端渲染（`backend/templates/`），无 Pages / 静态站部署 workflow。
- 容器镜像：推 `ghcr.io`，`permissions: packages: write`，用 `GITHUB_TOKEN` 登录；tag 取**不可变版本号** `:${{ version }}`，**无 floating `latest`**（`ghcr.yml` 实测仅此一个 tag）。
  - **差异（记录）**：镜像 tag **仅有 semver、未附 `sha` 后缀**（§10.3 建议 semver + `sha`）；且 `ghcr.yml` 未显式设置 `provenance:` / `sbom:` —— 即**镜像链未开 provenance / sbom**。SBOM 只在 `release.yml` 的 Release 资产层产出，不随镜像推送。
- **Trivy 扫描口径（如实记录，含两条链，取值不同）**：
  - `trivy.yml`（Trivy Container Scan）：**阻断**，`exit-code: '1'`，`severity: HIGH,CRITICAL`，`ignore-unfixed: true`；扫 `rootfs`（`docker export` 合并视图）并上传 SARIF；触发 `push main` / `pull_request` / `workflow_dispatch`。
  - `docker-scan.yml`（Container Image Scan (Trivy)）：**报告（observe）**，`exit-code 0`（image 步与 fs 步皆为 `0`），仅 `schedule`（周一 03:00 UTC）与 `workflow_dispatch` 触发，只出报告不阻断。
  - **差异（记录）**：**镜像发布链 `ghcr.yml` 自身不跑 Trivy**，即「发布前扫描」未串在推镜像之前（`docker-gate.yml` 是发布**完整性**五步门禁，属另一类，非漏洞扫描）。
- **不使用 GPG 分离签名**：本仓 `gpg-signed-release.yml` 已于 PR #95（commit `f9c7174`「删除已裁决撤掉的 GPG 签名 workflow」）删除；经 API 核对，`main` 上该文件已 404 不存在。完整性由 `SHA256SUMS` 承担。
- 桌面壳完整性补充（记录现状）：`desktop/src-tauri/tauri.conf.json` 当前**未配置 updater 插件**，故桌面安装包**暂无 Tauri ed25519 更新器签名**，以 `SHA256SUMS.desktop` 哈希为主。另有仓内**代码**完整性防线（`release-signing-public-key.asc` 为公钥，私钥在本机 `data/.manifest_signing_key`、不入库；`scripts/verify_release_integrity.py` 走五步门禁），属启动自检范畴，非 Release 资产分发手段。

## 5. 回滚

- **判定**（满足任一即触发）：**待定（负责人 + 触发条件）**——本仓为开源单机工具，无线上监控告警，现状以「发版产物坏 / 启动自检拒启 / 用户报告阻断性问题」为人工触发信号；具体阈值、责任人与观察窗口待定。
- **执行**：以 `git revert <bad-commit>` 为主（保历史、可再 forward）。应用 / 安装包 / 镜像 / SQLite 数据 / schema 的分步操作见 `docs/rollback_sop.md`：坏版本回退到上一 git tag、上一 `<X.Y.Z>-cu130` 镜像 tag 或上一 Release 资产；代码回滚后须**重算并重签**完整性清单（`INTEGRITY_ENFORCE=True` 下代码与清单不一致会拒启）。
- **破坏性动作**：重指向 / 删除 tag、移动任何远端 ref → **须仓库所有者单独授权**（`release.yml` 由 `push: tags` 触发，移动已发布 tag 会当场重跑发布链）。
- **回滚后验证**：`GET /api/health` 返回 ok 且 `backend` 引擎字段符合预期；`git status --short` 干净；完整性清单已重签；数据形态按 `docs/rollback_sop.md` §3 / §4 复核。

## 6. SLA / 错误预算

- 本仓为**开源单机工具**（本地部署：裸机 uvicorn / Docker compose / 桌面壳 NSIS），**无托管线上服务，不适用可用性 SLA**。
- 目标可用性 / 错误预算：**待定（负责人 + 触发条件）**——如未来引入托管形态，再按 §10 口径补 `99.5%/月 ⇒ ≈3.6h/月`，并绑定「超出即冻结非紧急发布并复盘」规则。

## 7. 发布前检查清单

- [ ] 版本位全部同步（见 §1 清单；根 `package.json` 与桌面三件套一致）
- [ ] `tests/test_version_consistency.py` 通过（漂一处即判红）
- [ ] `CHANGELOG.md` 已有本版二级标题 + 日期（否则发版说明退化为自动生成）
- [ ] 分支保护登记的必需检查全绿：`lock-consistency`、`integrity-freshness`、`python-test (ubuntu-latest)`、`python-test (windows-latest)`、`Typecheck (mypy ratchet)`、`frontend-smoke`、`security-scan`、`lint`（来源：`docs/ci/branch-protection.json`）
- [ ] 镜像类：`trivy.yml` 阻断已过（HIGH/CRITICAL）
- [ ] **本地未产出任何发布交付物**（源码包 / 镜像 / SBOM 全部远端构建）；**桌面安装包属已知本地例外，见 §4 差异**
- [ ] 冒烟 / 测试与 lint 门禁按各 workflow 实际命令通过（`test.yml`、`lint` 等）

---

## 禁止事项

- 不得重写 §10 的公共条款（远端优先、tag 驱动、版本位一致、不可变标签、扫描阻断、无 GPG）。
- 不得引入 `latest` 作发布基线；不得保留或新建 GPG 签名流程。
- 不得留空占位符，不得编造阈值。
