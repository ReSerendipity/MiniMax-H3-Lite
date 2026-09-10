# 安全审计 — MiniMax-H3-lite

> 只读审计 · 适配版（非 Image_MultiModel pydantic+config.yaml 架构）
> 审计日期：2026-09-01 · 审计对象：FastAPI + Jinja2 视频生成工作台（含 vendored `comfy_kernel/`）

## ⚡ 状态更新（2026-09-05，安全合规评估复核；下文原文保留不动）

按「代码/配置 > SECURITY_AUDIT」单一事实来源优先级，两条发现的状态已与 2026-09-01 审计时点不同：

- **M1 → 已修复（非"缓解"）**：commit `f97fd73`。`backend/config.py:112-118` 的 `MMH3_HOST`
  覆盖带 loopback fail-fast；`scripts/clean_launch.py:122-134` `_require_loopback` +
  `:198` 消费 `MMH3_HOST` + `:209` 接线 uvicorn（双层防御）。原文"实际启动硬编码
  `--host 127.0.0.1`"的描述已过时。根因门禁 `scripts/check_config_refs.py` 已接入 CI
  （`test.yml` security-assertions），实跑 exit 0。
- **M2 → 休眠风险（严重度低于原文描述）**：风险链前提「`COMFY_ENABLE` 自动拉起」在代码中
  **不存在**——`COMFY_ENABLE`/`COMFY_PYTHON`/`COMFY_MAIN_PY`/`COMFY_LAUNCH_TIMEOUT`
  全仓零消费点（config.py:48-51 声明后无读取）；实际 in-process 引擎
  （`backend/routers/comfy_engine.py:346`）仅改 `cli_args.args.lowvram` 等显存参数，
  **从不启动 HTTP 监听**。`comfy_kernel/comfy/cli_args.py:63` 的 `const="0.0.0.0,::"`
  回退确实仍在（vendored 未改），已由 `security-assertions` 棘轮断言锁定：该行变更即
  fail，项目调用面禁止 `--listen` 传参；若未来实现自动拉起，启动参数须显式 loopback。
- 其余发现（凭据/供应链/路径注入）复核无变化；`scripts/security_gate.py` 棘轮门禁已接入
  `security-scan`（commit `c3b92ff`），pip-audit `|| true` 的假绿问题已闭环。

## 执行摘要（总体评级：中 / Medium）

本地优先（localhost）设计总体 sound：无硬编码密钥、锁文件齐全、`127.0.0.1` 绑定、上传与 SQL 均安全。主要问题集中在**配置-实现一致性**（`MMH3_HOST` 死配置）与** vendored 组件暴露面**（comfy_kernel）。未发现凭据泄露或命令注入。共 5 项发现（1 中 / 1 中 / 1 低 / 2 信息级良性）。

## 按维度发现

### 1. 凭据 / 密钥
- **良性**：`backend/watermark.py:45-55` 签名密钥仅取自 `MMH3_SIGN_KEY` 环境变量或 `.watermark_key` 文件，**无硬编码默认值**（未配置则直接不签名，非假安全）。
- **良性**：`.gitignore` 已忽略 `.env`、`.watermark_key`、`secrets/`（已验证 `git ls-files` 无密钥文件入库）。
- **良性**：`comfy_kernel/execution.py:157-223` 的 `auth_token_comfy_org/api_key_comfy_org` 为用户经配置传入的外部 API Key，属正常透传模式。

### 2. 依赖供应链
- **良性**：`requirements-lock.txt` 由 pip-compile 全量 pin（`fastapi==0.141.1`、`pillow==12.3.0` 等），`requirements.txt:42` 含 `pip-audit` 扫描依赖。✅

### 3. 网络暴露
- **[M1-Medium] 死配置 / 配置-实现错配**：`backend/config.py:112-113` 解析 `MMH3_HOST` 写入 `settings.HOST`，但全仓 `backend/` 未消费 `settings.HOST`（grep 确认）；实际启动 `scripts/clean_launch.py:186` **硬编码** `--host 127.0.0.1`。后果：①该环境变量是「声明了但没人读」的假控制；②无 loopback 强制，若日后把 uvicorn 接上 `settings.HOST` 会**静默绑定 0.0.0.0**。建议：要么在启动脚本消费 `settings.HOST`，要么删除 `MMH3_HOST`；并加 loopback 校验。
- **[M2-Medium] vendored comfy_kernel 暴露面**：`comfy_kernel/comfy/cli_args.py:63` 的 `--listen` 默认 `127.0.0.1`，但裸 `--listen`（无参）会回退为 `0.0.0.0,::`；`comfy_kernel/custom_nodes/ComfyUI-Manager/glob/manager_server.py:37-41` 的安全级别提示表明其管理端可被网络暴露。若 `COMFY_ENABLE` 自动拉起 ComfyUI 时传入裸 `--listen`，会绑定全网。建议：固定启动参数为显式 loopback，审查 ComfyUI-Manager 安全级别。

### 4. 路径 / 注入
- **良性**：`backend/routers/uploads.py:130-133` 落盘用生成的 `aid` + 仅取扩展名，**无路径拼接遍历**；`:164/:190` SQL 全部参数化（无拼接）；`watermark.py`/`uploads.py` 的 `subprocess` 均用 list 形参、无 `shell=True`（无命令注入）。✅

### 5. 配置-实现一致性（适配版）
- 见 M1：`MMH3_HOST` 声明但未消费，属典型「假控制」。其余 `Settings` 字段（上传上限 `MAX_*_COUNT`、队列等）均在对应路由中真实消费。✅

### 6. 前端 / 客户端
- 不适用（Jinja2 服务端模板，无 SPA 危险 API）。

## 门禁适用性说明

Image_MultiModel 的 `scripts/check_config_refs.py` **不直接适用**，原因：
1. 它解析 `config_models.py` 的 **pydantic `BaseModel`** 字段（`collect_class_fields` 仅识别 `BaseModel`/`ConfigModel` 基类），而本仓库配置是 `backend/config.py` 的 **`@dataclass Settings`**，不会被识别；
2. 它校验 **根 `config.yaml` 的 `security:` 段每个键都被代码消费**，本仓库**没有** `config.yaml` 与 `security:` 段。

**最小改造点（若要移植该门禁）**：
- 扩展 `collect_class_fields()`：除 `BaseModel` 外，也收集带 `@dataclass` 装饰器的类的 `AnnAssign` 字段；
- 在仓库根新增 `config.yaml` 的 `security:` 段（建议键：`host`（loopback 强制）、`max_upload_size_mb`、`max_*_count`、`mmh3_sign_key`（必填）、`comfy_url`（loopback）），并让 `check_security_keys_consumed()` 扫描 `backend/` 确认每个键被消费；
- 或写轻量 MiniMax 版门禁：解析 `backend/config.py:Settings` 的属性 → grep 全仓是否出现 `settings.<attr>` 读取；未发现读取即失败（可直接捕获 M1 这类死配置）；
- 另建议加一条**独立 loopback 强制**：扫描启动脚本/uvicorn 调用，断言 `host` 不出现 `0.0.0.0`（参考 Image_MultiModel `ServerConfig.host_must_be_loopback` 校验器）。
