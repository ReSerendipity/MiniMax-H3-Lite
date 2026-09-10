# GPL-3.0 合规说明（vendored `comfy_kernel/` 与相关 pip 组件）

> 本文档是**分发物**，不是内部笔记：§2 方式 A 要求它随包出仓，因此它虽位于
> gitignored 的 `docs/` 下，仍以 `git add -f` 显式入库（`.gitignore:59` 的 `docs/`
> 模式不适用于本文件）。文中每个数字都由 §4 的命令当场可复现，改动内核或基线后须同步。
>
> 最后核验：2026-09-10（`comfy_kernel` 0.33.0 / 基线 `ae711691b124`）。

## 1. 组件事实

| 项 | 值 |
|---|---|
| 组件 | `comfy_kernel/` — vendored ComfyUI 内核源码 |
| 上游 | <https://github.com/Comfy-Org/ComfyUI> |
| 版本 | ComfyUI **0.33.0**（实测 `comfy_kernel/pyproject.toml` L2-3：`name = "ComfyUI"` / `version = "0.33.0"`） |
| 源码对应提交 | **不可得** —— 见下方「取证」块。本仓无法声明上游提交号 |
| 磁盘文件数（口径 A） | **4136** —— `comfy_kernel/` 下**所有**文件，含编译缓存与版本控制痕迹 |
| 纳入基线哈希（口径 B） | **2582** —— `.ci/comfy_kernel_baseline.json` 的 `file_count` |
| 被排除数 | **1554** = 1553 个 `__pycache__` 文件 + 1 个悬空 gitlink（`4136 − 1554 = 2582`） |
| 一级目录数 | **20** |
| 根摘要（前 12 位） | `ae711691b124` |
| 本地改动检测 | `scripts/comfy_kernel_baseline.py` + 入库工件 `.ci/comfy_kernel_baseline.json`；CI 在 `comfy-kernel-guard` job 内跑 `--check` |
| 许可 | GNU GPL-3.0（`comfy_kernel/LICENSE` 首行：`GNU GENERAL PUBLIC LICENSE`） |
| 主项目许可 | Apache-2.0（`LICENSE` 首行：`Apache License`） |
| 引用方式 | **进程内复用**：`sys.path.insert(0, _KERNEL_DIR)`（`backend/routers/comfy_engine.py:341`）→ `nodes.init_extra_nodes(...)`（同文件 L405）→ `execution.PromptExecutor(...)`（同文件 L410），非独立进程、非网络调用 |

⚠️ **口径 A 与口径 B 不得混写**：4136 是"内核目录里有多少文件"，2582 是"基线对多少文件做了哈希"。
把 4136 写进"基线覆盖范围"、或把 2582 当作内核规模，都会与入库工件自相矛盾。

### 取证：为什么"源码对应提交"不可得

三条实测命令与其结果（本文档不记录任何未经此实测的结论）：

1. 内核自身没有 `.git`：`Test-Path comfy_kernel\.git` → `False`
   （`Get-Item` 报 `Cannot find path '...\comfy_kernel\.git' because it does not exist.`）。
2. **把探测限定在内核目录内**，git 明确否认它是仓库（rc=128）：

   ```
   $ git --git-dir=comfy_kernel/.git rev-parse HEAD
   fatal: not a git repository: 'comfy_kernel/.git'
   ```

3. ⚠️ **陷阱**：计划原先给的 `git -C comfy_kernel rev-parse HEAD` **不会失败**，实测 rc=0，
   并打印 `ba2e47ca7fe7efff3c32a1b22e85cd27c3324617`。那**不是**上游 ComfyUI 的提交，
   而是**本主仓自己的 HEAD** —— `git -C` 进入 `comfy_kernel/` 后向上穿透，发现了
   `MiniMax-H3-lite/.git`（`git -C comfy_kernel rev-parse --show-toplevel` 实测打印
   `C:/Users/Doro/MiniMax-H3-lite` 即为佐证）。
   **任何人不得把该 SHA 写成内核的上游对应提交**；要判定"内核不是仓库"，必须用上面第 2 条
   这种无法向上穿透的形式。

后果：既没有上游提交号，也无法把"内核里的哪些字节是上游原样、哪些是本仓改动"精确区分到
提交粒度（基线只到**一级目录**粒度）。§2 方式 B 正因这两点而不成立。

### 1b. 其他 GPL-3.0 组件（pip 依赖）

| 包 | 钉版 | 许可 | 依据（均为本仓当场实测） |
|---|---|---|---|
| `comfy-aimdo` | `==0.4.13`（`requirements.txt:30`） | **GPL-3.0** | 安装副本 `.venv/Lib/site-packages/comfy_aimdo-0.4.13.dist-info/licenses/LICENSE` 前二行：`This project is licensed under the GNU General Public License v3.0.` / `The original author/copyright holder reserves the right to offer the`。上游 GitHub 标 `NOASSERTION` 仅因许可正文前置了那段非标准声明，不改变"按 GPL-3.0 授权"的判定 |
| `comfy-kitchen` | `==0.2.31`（`requirements.txt:29`） | Apache-2.0 | 安装副本 `comfy_kitchen-0.2.31.dist-info/METADATA` 含 `License: Apache-2.0`；上游 `Comfy-Org/comfy-kitchen` LICENSE 一致 |

`comfy-aimdo` 与内核同为**进程内**依赖：它在运行时被直接 import 进本项目的推理路径
（`backend/routers/comfy_engine.py:374` `import comfy_aimdo.control as _ctl`，并在 L391-392
预载 `comfy_aimdo.model_vbar` / `host_buffer` / `vram_buffer` / `torch` 子模块），
承担 DynamicVRAM 分层落盘。**它的 GPL-3.0 义务范围与内核一致，不得按"普通第三方 pip 包"降级处理。**

### 1c. 内核内的第三方版本控制残留

`comfy_kernel/custom_nodes/ComfyUI_UltimateSDUpscale/repositories/ultimate_sd_upscale/.git`
是一个 **gitlink 文件**，内容为 `gitdir: ../../.git/modules/repositories/ultimate_sd_upscale/`，
而目标 gitdir 不存在（实测 `git --git-dir=<该文件> rev-parse HEAD` →
`fatal: not a git repository: ../../.git/modules/repositories/ultimate_sd_upscale/`）。
它就是 §1 里"1 个非 `__pycache__` 排除项"。

它**不影响**"内核本体非 git 仓库"的判定（那是某个 vendored 自定义节点的遗留物），
但溯源时勿把它误读成内核的上游仓库指针。

## 2. 「提供对应源码」的履行方式

**方式 A（本仓唯一可行方式）：源码随包分发。**
任何把内核一并带出的分发形态，都必须附**完整** `comfy_kernel/`（含 `comfy_kernel/LICENSE`）
与本文件，并复核内核目录确实进了产物、且与 `.ci/comfy_kernel_baseline.json` 无漂移。

本仓当前的分发形态是 Docker 镜像（`Dockerfile`，构建与钉版见 `scripts/build_and_pin.ps1`）
与 git 源码归档。**注意**：本仓目前**没有**便携包/整目录复制式打包脚本，
因此"便携包"属于尚未存在的分发形态；一旦引入（无论叫 `pack_portable` 还是别的），
上述复核义务立即适用 —— 这类脚本天然倾向只拷 `app`/`backend`/`web` 而漏掉 vendored 内核。

**方式 B（书面承诺提供源码）在本仓不成立**，两条独立原因（见 §1 取证块）：

1. 书面承诺必须指向一个可兑现、可指认的源码版本，而内核**没有上游提交号**（`.git` 不存在，
   且 git 的 `rev-parse` 会穿透到主仓 HEAD，给出的是无关 SHA）；
2. 基线粒度是**一级目录摘要**（4136 文件的逐文件清单 ≈200 KB 且每次升级全量 churn，
   故未采用），它只能证明"没漂移"，**不足以**证明"完整对应源码"。

若将来必须走方式 B，前置条件是把 `comfy_kernel/` 转为可溯源形态（独立 git 仓库或 submodule），
使其拥有可指认的上游提交。

## 3. 分发形态与许可边界

本节记录的是 2026-09-10 已落地的决策（`build(docker): 镜像不再含 vendored 内核`）。

- **镜像不含内核**：`.dockerignore` 末段显式排除 `comfy_kernel`，
  因此 `Dockerfile:74` 的 `COPY . .` 不再把 ComfyUI 源码打进镜像。
- **改由挂载提供**：`docker-compose.yml:63` 以 `./comfy_kernel:/app/comfy_kernel:ro`
  **只读**挂载，内核由**使用者自备**。
- **效果**：本项目可分发的**镜像**里不含 ComfyUI 代码，从源头规避"组合作品分发"触发的
  GPL 源码义务；改动前内核既被 `COPY . .` 打进镜像、又被同一 compose 以 `:ro` 挂载，
  是双份且两种 GPL 叙事都不自洽的状态。
- **代价（有意取舍，不是缺陷）**：单独 `docker run minimax-h3-lite` 时 native 引擎不可用，
  必须经 `docker compose up` 或显式 `-v ./comfy_kernel:/app/comfy_kernel:ro` 提供内核；
  README「🐳 Docker 部署」段已对此明示。运行时若缺内核，
  `backend/routers/comfy_engine.py:339` 抛 `内置 Comfy 引擎缺失…（comfy_kernel 未随项目分发）`。
- **未实测项（诚实标注）**：排除内核带来的**镜像/构建上下文体积差未实测** —— 本机无 docker，
  无法执行计划 Task 3 Step 1 的 `docker build --progress=plain` 上下文传输量对比。
  本节结论仅基于 `.dockerignore` 语义与 `COPY . .` 的行为推断，**不得**在任何地方引用一个
  编造的体积数字。
- **代码边界**：`app`/`backend` 不拷贝内核源码，仅 `import`（见 §1「引用方式」行）。
- 若某分发形态选择**内嵌**内核（例如未来的便携包），本节不适用，须回到 §2 方式 A。

## 4. 分发前自查清单

每项都给了可当场执行的判据（PowerShell）。**全部为真**才可分发。

- [ ] `comfy_kernel/LICENSE`（GPL-3.0 全文）存在且未删改：
      `Test-Path comfy_kernel\LICENSE` → `True`
- [ ] 随包分发形态下 `comfy_kernel/` 源码完整：
      `python scripts\comfy_kernel_baseline.py --check` → **退出 0**
      （该命令同时覆盖"版本/文件数/目录摘要与基线一致"，即内核相对基线**无漂移**；
      内核目录缺失时它打印 `[SKIP]` 并退出 0，托管 runner 属正常情形，
      但**部署机上必须真实存在**，由 `scripts/preflight.sh` 与本清单的
      `check_compose_mounts.py` 一项兜底）
- [ ] 基线工件本身在库（它入库，缺失等于门禁被拆掉）：
      `git ls-files --error-unmatch .ci/comfy_kernel_baseline.json` → rc=0
- [ ] 本文件确已随分发物出仓（`docs/` 被 `.gitignore:59` 排除，靠 force-add 才入库）：
      `git ls-files --error-unmatch docs/GPL_COMPLIANCE.md` → rc=0
- [ ] 镜像不含内核、compose 挂载未动：
      `Select-String -Path .dockerignore -Pattern '^comfy_kernel$'` 命中，且
      `Select-String -Path docker-compose.yml -Pattern '\./comfy_kernel:/app/comfy_kernel:ro'` 命中
- [ ] bind-mount 门禁在部署机给出绿信号：`python scripts\check_compose_mounts.py` → 退出 0
- [ ] `NOTICE` 与 `THIRD_PARTY_NOTICES.md` 的 `comfy_kernel` / `comfy-aimdo` 条目未被删改。
      **注意两点**：(a) 这类 `git grep` 断言**只覆盖入库文件**，本文件位于 `docs/` 下，
      只有经 `git add -f` 才会随分发物出仓 —— 换言之 CI 的绿**不能**证明本文件在产物里，
      必须用上面第 4 条单独断言；(b) 这一项**自 `0e8dd58` 起不再"只能人工核"**：断言落在
      `.github/workflows/docs-consistency.yml` → job `spec-refs` → 步骤名
      **`license-notice-check`**，它逐条 grep 五项 —— ① `NOTICE` 提及 `comfy_kernel`、
      ② `NOTICE` 声明 `GPL-3.0`、③ `NOTICE` 声明 `comfy-aimdo`、
      ④ `THIRD_PARTY_NOTICES.md` 含 `comfy_kernel` 条目、⑤ 该文件不再出现 `comfy…未核验`；
      同一组语义另有 `tests/test_license_notice.py` 的 4 个用例在任何跑 pytest 的 job 里复算。
      该 workflow 的 `paths` 过滤器亦已补入 `NOTICE` 与 `LICENSE`，改无扩展名的 `NOTICE`
      不再漏触发。判据当场可复现：`python -m pytest tests/test_license_notice.py --no-cov`。
- [ ] 若采用"镜像不含内核"形态：README 部署段已说明必须经 compose/`-v` 提供内核（已落地）

## 5. 版本升级时的义务

替换或升级 `comfy_kernel/` 后，**按顺序**执行：

1. `python scripts\comfy_kernel_baseline.py --generate` 重算基线，并**提交**
   `.ci/comfy_kernel_baseline.json`（不提交等于把门禁留在旧版本上）；
2. 更新本文件 §1 的「版本」「磁盘文件数」「纳入基线哈希」「被排除数」「一级目录数」「根摘要」
   六个字段 —— 它们全部随内核版本变化，任一未改即为文档与工件漂移；
3. 更新 §1b 的 pip 钉版与许可依据（`comfy-aimdo` / `comfy-kitchen` 随内核升级常同步变动）；
4. 若改动了内核代码，按 `AGENTS.md` 禁区表要求记录 ADR 并保留 patch 文件 ——
   基线只能告诉你"哪个一级目录变了"，说不出"为什么"；
5. 复跑 §4 全清单。若新内核带进新的 `__pycache__` 之外的排除项，须把口径 B 的
   排除构成一并写进 §1，勿只改总数。
