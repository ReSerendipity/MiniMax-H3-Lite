# AI 开发契约 · 本机治理文档指针（stub）

> 本文件是**被版本控制跟踪的最小入口指针**。它本身不承载任何治理规则正文，只声明：
> 本项目的 AI 开发契约（work contract）住在哪里、如何到达、以及它为什么不在仓库里。
> 对应社区约定名 `AGENTS.md`；因本地治理约定（见下）该文件**仅存在于所有者本机**，不入库。

## 1. 契约位置（本机路径，不在仓库中）

以下路径均相对仓库根目录，且被 `.gitignore` 显式排除（`git check-ignore` 可复核）：

| 本机路径 | 角色 | 跟踪状态 |
|---|---|---|
| `AGENTS.md` | AI 辅助开发指南 · 自进化协议主文档（6 条铁律、自检清单入口、文档优先级） | ❌ 本地（`.gitignore` §「AI 规范」） |
| `docs/agents/` | 契约细化子文档 8 件：`ARCH_MAP.md`（模块地图）、`CODE_STYLE.md`（代码风格）、`CONFIG.md`（启动命令与环境变量）、`TEST_COMMANDS.md`（测试约定）、`GOTCHAS.md`（坑点台账）、`SOPS.md`（典型开发 SOP + 自进化自检清单）、`QUALITY_CONTRACT.md`（质量执行契约）、`REVISION_LOG.md`（修订记录表） | ❌ 本地（`.gitignore` §「自进化协议细化文档」） |
| `LOCAL_RULES.md` | 所有者本地管理规则 | ❌ 本地（`.gitignore` §「本地管理规则」） |

路由约定（以本机 `AGENTS.md` 为唯一入口）：项目概览/技术栈 → `docs/agents/ARCH_MAP.md`、`CONFIG.md`；
写码前 → `CODE_STYLE.md`；跑测试 → `TEST_COMMANDS.md`；修 bug 后 → 追加 `GOTCHAS.md`；
完成任务后 → 追加 `SOPS.md`；每次启动 → 执行 `SOPS.md` 尾部「自进化自检清单」。

## 2. 本地属性声明（为什么只有一个 stub）

- **有意决定，非遗漏**：上述治理文档含本机路径、本地环境与家族仓库引用等私人/易变信息，
  所有者选择不上远程（`AGENTS.md` 铁律 #6 亦登记了 `docs/agents/`「运行时产物（非问题）」的口径）。
  因此它们**不参与 CI、对新克隆不可见**——这是本 stub 存在的原因。
- **权威关系**：仓库跟踪文件（代码、`package.json`、`.pre-commit-config.yaml`、本 README、`docs/**`）
  对任何人都是事实源；`AGENTS.md` 系仅对本机 agent 生效的**补充**工作契约。
  冲突时按 `AGENTS.md` §0「文档优先级」处理（代码与配置 > official spec > `AGENTS.md` > README/docs > CHANGELOG）。
- **对 CI 的影响**：本 stub 对上述本机路径一律使用行内代码而非 Markdown 链接，
  故干净检出下 `scripts/check_spec_refs.py --minimal`（死链审计，扫跟踪 `*.md` 的相对链接）不会误报。

## 3. 不同角色的下一步

- **在所有者本机打开 agent（当前环境）**：直接读仓库根 `AGENTS.md`，按其 §0 与索引进入
  `docs/agents/*` 执行；本 stub 只是它的仓库可见门面，不复述规则正文，避免双份漂移。
- **在新克隆 / CI 干净检出上工作**：`AGENTS.md` 与 `docs/agents/` 不存在，属预期状态。
  以 `README.md`（快速开始/测试）、`docs/CODING_STANDARDS.md` §2（本地验证循环、提交规范、
  红线）、`docs/adr/*`（架构决策）为行为依据；贡献流程与 DCO 以组织级贡献指南为准
  （本仓不放根级 `CONTRIBUTING.md`，社区健康文件由 org 默认仓提供）；
  如需自进化契约，须先由所有者把本机治理文档随附，或显式引入公开版本——**agent 不得虚构其内容**。
- **要修改契约本身**：改本机 `AGENTS.md` / `docs/agents/*` 并按其铁律 #5 递增自进化协议版本号、
  在 `docs/agents/REVISION_LOG.md` 追加记录；仅当本 stub 的路径表或本地属性口径变化时才改本文件。

---

*Stub 引入日期：2026-09-19（为 AI 开发契约提供可被 git/CI/新克隆发现的跟踪入口；治理文档保持本地属性不变）。*
