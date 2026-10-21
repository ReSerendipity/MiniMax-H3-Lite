# MiniMax-H3-Lite 安全矩阵

> 本文档列出项目的安全控制措施，供安全审计和合规检查参考。

## 身份与访问控制

| 控制项 | 实现方式 | 状态 |
|---|---|---|
| 分支保护 | GitHub Branch Protection：要求 PR + 1 审批 + **8 项必需状态检查**（`strict=false`）＋ **`enforce_admins=false`** ⇒ 本机 owner/admin 凭据可直推 main（2026-10-17 只读实测）。该豁免的**补偿控制**是 `.githooks/pre-push` 对 `refs/heads/main` 强制 `precheck.ps1 -Full`，并比对 live 与 `docs/ci/branch-protection.json` 判漂移 | ✅ 已接受并记录（2026-09-28 设立·2026-10-17 复核确认保留；见 `AGENTS.md` §main 直推授权） |
| DCO 签名 | .githooks/commit-msg 强制 Signed-off-by | ✅ |
| 代码审查 | PR 需 review | ✅ `.github/CODEOWNERS` 已入库（2026-10-21 复核）；`require_code_owner_reviews=false`，单人仓下只做 review 指派、不阻断合并（见 `docs/ci/branch-protection.json`） |

## 代码安全

| 控制项 | 实现方式 | 状态 |
|---|---|---|
| 密钥扫描 | gitleaks（pre-commit + CI） | ✅ |
| 依赖漏洞扫描 | pip-audit / Dependabot | ✅ |
| SAST | CodeQL / Semgrep | ✅ |
| 静态分析 | flake8 / eslint（2026-10-21 复核：ruff 未接入——`.pre-commit-config.yaml` 为 flake8/bandit/detect-secrets/gitleaks，eslint 见 `package.json` devDependencies） | ✅ |
| 完整性校验 | Ed25519 签名清单 | ✅ |

## 数据安全

| 控制项 | 实现方式 | 状态 |
|---|---|---|
| 敏感配置不入库 | .env.example 模板，真实配置 gitignore | ✅ |
| 路径遍历防护 | 上传落盘用生成 `aid`+扩展名（用户文件名不入盘）+ MIME/扩展名白名单（`backend/services/upload_service.py:123-126`、`27-45`）；SQL 全参数化（`backend/database.py`）。无 `path_guard` / CSRF middleware（2026-10-21 复核：`backend/` 下不存在，`main.py` 仅请求追踪中间件） | ✅ |
| 输入校验 | 参数验证 / schema 校验 | ✅ |

## 发布安全

| 控制项 | 实现方式 | 状态 |
|---|---|---|
| 签名发布 | gpg-signed-release（仅 SeedVR2） | ⚠️ 待推广（**本仓现状 2026-10-21 复核**：`gpg-signed-release.yml` 已删除，改用 `SHA256SUMS` / `SHA256SUMS.scripts` 承担完整性，v2.6.0 Release 资产中无签名文件；见 `docs/release-governance.md` §4） |
| 制品不可变 | Immutable Release Artifacts | ✅ |

---
*最后更新：2026-10-17（分支保护一行按服务端只读实测改为「部分生效」并写明 admin 豁免与本地补偿；依赖漏洞评估见 `.github/SECURITY_MATRIX.md` §4）*
