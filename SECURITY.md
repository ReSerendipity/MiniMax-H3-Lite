# 安全策略与需求矩阵 — MiniMax-H3-lite

> 建立日期：2026-09-05（来源：安全合规评估报告 v2.3.1 配套整改，P2-⑥「无统一安全需求追踪」）
> 单一事实来源优先级：**代码/配置 > SECURITY_AUDIT > LOCAL_RULES > README**。
> 本文件是安全需求的统一追踪入口；与代码冲突时以代码为准并回改本文件。

## 1. 安全报告（漏洞上报）

如发现本仓库安全问题，请**勿**直接开公开 issue（避免细节暴露）：
联系仓库所有者（ReSerendipity），或经私有渠道报告。模型相关问题参考
[MiniMax 官方渠道](https://huggingface.co/MiniMaxAI/MiniMax-H3)。

## 2. 安全需求矩阵

| # | 安全属性 | 设计决策 | 证据路径 | CI 断言 |
|---|---|---|---|---|
| R1 | 监听回环红线 | 仅允许 `127.0.0.1`/`localhost`/`::1`；`MMH3_HOST` 覆盖 fail-fast + 启动层二次校验（双层防御） | `backend/config.py:112-118`、`scripts/clean_launch.py:122-134,198,209` | `security-assertions` 禁 0.0.0.0 扫描 |
| R2 | 幽灵控制（配置-实现一致性） | 每个可 env 覆盖的 Settings 字段必须有真实消费点；非 env 字段必须被消费或在 `_RESERVED_NON_ENV` 显式登记 | `scripts/check_config_refs.py`（AST 门禁，覆盖全部 Settings 字段） | 同上，CI 硬门禁 |
| R3 | vendored comfy_kernel 暴露面 | in-process 模式不启动 HTTP server；`--listen` 裸参回退行棘轮锁定；项目调用面禁止 `--listen` 传参 | `comfy_kernel/comfy/cli_args.py:63`、`backend/routers/comfy_engine.py:346` | `security-assertions` comfy_kernel 棘轮 + 调用面断言 |
| R4 | 凭据管理 | 无硬编码密钥；`MMH3_SIGN_KEY`/`.watermark_key` 缺省不签名（非假安全）；`.gitignore` 忽略 `.env`/`.watermark_key`/`secrets/` | `backend/watermark.py:46-49`、`.gitignore:23,62,101-102` | `security-scan` + pre-commit detect-secrets |
| R5 | 依赖供应链 | `requirements-lock.txt` 全量 pin；报告生成与门禁判定分离，棘轮基线只降不升（全零起步） | `scripts/security_gate.py`、`.ci/security_baseline.json` | `security-scan` 末步 `security_gate.py`；`trivy.yml` HIGH/CRITICAL 阻断 |
| R6 | 路径/注入 | 上传落盘用生成 `aid`+扩展名（无遍历）；SQL 全参数化；subprocess list 形参无 `shell=True` | `backend/routers/uploads.py:130-133,164,190` | Semgrep（`sast.yml`）+ `sast_gate.py` 棘轮 |
| R7 | 许可合规 | 模型许可（区别于仓库代码 Apache-2.0）：本地开发运行时横幅提示（不阻断）；容器化部署入口强制确认（`MMH3_ACK_LICENSE=1`） | `NOTICE`、`scripts/clean_launch.py` 启动横幅、`scripts/preflight.sh` §4 | 部署流程约定（preflight 为人工执行入口） |
| R8 | 权限模型 | 无认证/授权——单机回环单用户**设计如此**（非缺失）；风险由 R1 三层兜底承担（config fail-fast → `_require_loopback` → CI 断言）。不引入本地 token | `LOCAL_RULES.md:11`、SECURITY_AUDIT §网络暴露 | R1 断言间接覆盖 |
| R9 | 取证策略 | 见 §3 | `backend/watermark.py` | — |

## 3. 取证策略决策（2026-09-05）

**决策：维持「缺省不签名 + debug 级日志」，不做默认开启。**

- 依据：`LOCAL_RULES.md` 第 5 条为家族铁律——内容来源标识对用户**完全无感**，
  用户可见面（页面/README/终端）不得出现相关字样；默认签名或 info 级日志会破坏该约束。
- 默认产物无 HMAC 签名、运行时无审计 trail，属**知情接受**的取舍：本项目是
  单机回环个人工具（R8），无多租户取证需求；生成物已在 `data/mmh3.db` 留有
  任务级记录（项目/分镜/参数/产物路径），可满足"溯源到任务"的实际需要。
- 需要密码学级取证时，配置 `MMH3_SIGN_KEY` 环境变量（或仓库根放 `.watermark_key`）
  即启用嵌入签名——开关已存在（`watermark.py:46-49`），无需改代码。

## 4. 已知限制（知情保留，非缺陷）

- `COMFY_ENABLE`/`COMFY_PYTHON`/`COMFY_MAIN_PY`/`COMFY_LAUNCH_TIMEOUT`：自动拉起
  规划字段，未实现、零消费点，已在门禁 `_RESERVED_NON_ENV` 显式登记。实现时启动
  参数必须显式 loopback（禁止裸 `--listen`）。
- 7 个 spec 派生快照字段（`SAVE_PREFIX`/`SCHEDULER`/`RESOLUTION_DEFAULT`/
  `RESOLUTION_PRESETS`/`SUPPORTED_RATIOS`/`OUTPUT_BIT_DEPTH`/`OUTPUT_FORMAT`）：
  消费点直读 `h3.spec`，settings 副本暂为死镜像（漂移风险已在门禁注释标注），
  清理方向二选一：删副本或改消费点。
