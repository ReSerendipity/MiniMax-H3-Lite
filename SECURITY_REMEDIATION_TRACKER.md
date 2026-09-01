# MiniMax-H3-lite 安全整改追踪表

> 配套 Image_MultiModel 家族安全深度评估（`SECURITY_ASSESSMENT_v2.0.0.md`，17 项发现）。
> 本仓为 **FastAPI + Jinja2** 工作台，配置为 `@dataclass Settings`（无 `config.yaml` /
> pydantic），故「配置-实现一致性根因门禁」做了轻量适配版（见下）。

## 1. 根因门禁（已落地）

**配置幻觉（Phantom Control）**：`config.py` 的 `Settings` 字段若由 `MMH3_*` 环境变量
覆盖却从未被代码真实应用，即「声明了但没人读」的假控制。

本仓门禁 `scripts/check_config_refs.py`（MiniMax 适配版，纯标准库）：
1. 解析 `backend/config.py` 的 `Settings` 字段与 `from_env()` 的 `MMH3_*` → 字段映射；
2. 对每个可环境变量覆盖的字段，断言其在 `backend/`（读取 `settings.<field>`）或
   `scripts/`（启动层读取 `MMH3_*` 并落地，如 `uvicorn --host`）被真实应用；
3. 未应用者判 `[FAIL]`（保留字段进 allowlist）。

接入 CI：`.github/workflows/test.yml` 的 `security-assertions` 硬门禁。

## 2. 整改状态表

| 编号 | 类别 | 措施 | 状态 | 落地文件 |
|------|------|------|------|----------|
| M1 | 死配置 / 假控制（HOST） | `clean_launch.py` 改为读取 `MMH3_HOST` 并经 `_require_loopback` 强制回环校验后绑定 uvicorn；`config.py.from_env()` 同步加 loopback 校验（fail-fast）；门禁覆盖 HOST | ✅ 已落地 | `scripts/clean_launch.py`、`backend/config.py`、`scripts/check_config_refs.py` |
| M2 | vendored comfy_kernel `--listen` 0.0.0.0 | **残留（潜伏期）**：当前 `backend/` 无 comfy 自动拉起实现（`COMFY_ENABLE` 默认 False，无 spawn 站点），故暂无实际暴露。已加 `COMFY_URL` 经 `settings.COMFY_URL` 消费（默认 `http://127.0.0.1:8188`）；待未来实现 comfy 自动拉起时，启动参数须显式 `--listen 127.0.0.1`，禁止裸 `--listen` | 🟡 文档化待办 | `backend/config.py`、`comfy_kernel/comfy/cli_args.py`（vendored，未改） |
| C-01 | 0.0.0.0 监听 | CI `security-assertions` 禁 0.0.0.0；`_require_loopback` 强制回环 | ✅ 既有 + 增强 | `scripts/clean_launch.py`、`test.yml` |

> 注：`MODEL_FL2VA/REF2VA/CLIP/VAE_*` 与 `COMFY_SOURCE_DIR` 经审计确认当前为**保留字段**
> （env 可覆盖但未被消费），非安全控制，已进门禁 allowlist 并文档化；若未来变为安全相关
> 须移除 allowlist 并补消费点。

## 3. 日常纪律（与家族一致）

1. 新增 `MMH3_*` 环境变量覆盖的 `Settings` 字段：必须同步在 `backend/` 或 `scripts/`
   中真实应用；否则 `check_config_refs.py` 在 CI 判 `[FAIL]`。
2. 删除 env 覆盖点：同步删除 `from_env()` 映射与代码读取点。
3. 禁止绕过门禁：CI 中该步骤为真实门禁，不得加 `|| true`。
4. 任何监听地址必须经 `_require_loopback` / CI 红线校验，禁止 `0.0.0.0`。

## 4. 跨仓对账

| 仓库 | 根因门禁 | 安全头中间件 | 提交状态 |
|------|----------|--------------|----------|
| Image_MultiModel | ✅ (config.yaml security:) | ✅ | 已提交 |
| TTS_MultiModel | ✅ (config.yaml security:) | ✅ | 已提交（本地） |
| SeedVR2-lite | ✅ (runtime.security:) | ✅ | 已提交（本地） |
| MiniMax-H3-lite | ✅ (dataclass Settings 死配置检测) | 不适用（Jinja2 服务端模板，无 SPA 危险 API） | 本次落地 |
| SpiritPal | 不适用（Rust/Tauri） | 审计中 | 只读审计 |
| DraftPeek | 不适用（Kotlin） | 审计中 | 只读审计 |
