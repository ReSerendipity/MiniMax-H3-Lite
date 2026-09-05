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
| M2 | vendored comfy_kernel `--listen` 0.0.0.0 | **休眠风险（2026-09-05 复核降级）**：`COMFY_ENABLE` 等自动拉起字段全仓零消费点、无 spawn 站点，in-process 引擎不启动 HTTP server，当前无实际暴露。已加双道 CI 断言（见 S-02） | 🟡 棘轮断言已锁（2026-09-05） | `backend/config.py`、`comfy_kernel/comfy/cli_args.py`（vendored，未改）、`test.yml` |
| C-01 | 0.0.0.0 监听 | CI `security-assertions` 禁 0.0.0.0；`_require_loopback` 强制回环 | ✅ 既有 + 增强 | `scripts/clean_launch.py`、`test.yml` |
| S-01 | 供应链 `|| true` 假绿（评估 P1） | `security_gate.py` 棘轮门禁（报告与判定分离，基线全零起步）接入 `security-scan` 末步 | ✅ 已落地（commit c3b92ff） | `scripts/security_gate.py`、`.ci/security_baseline.json`、`test.yml` |
| S-02 | comfy_kernel 暴露面无 CI 断言（评估 P1） | `security-assertions` 新增：`cli_args.py` 回退行棘轮（变更即 fail 须人工确认）+ 项目调用面禁 `--listen` 传参 | ✅ 已落地（2026-09-05） | `test.yml` security-assertions |
| S-03 | 许可合规零代码层提示/拦截（评估 P0） | 本地开发：`clean_launch.py` 启动横幅打印许可范围（不阻断）；容器化部署：`preflight.sh` 强制 `MMH3_ACK_LICENSE=1` 确认 | ✅ 已落地（2026-09-05） | `scripts/clean_launch.py`、`scripts/preflight.sh` |
| S-04 | 幽灵门禁盲区：非 env 字段无检测（评估 P2） | `check_config_refs.py` 扩面至全部 Settings 字段：新增 `_RESERVED_NON_ENV` 显式保留表；同步修 env 提取器盲区（`int()`/`max()` 包装、`.strip()` 链、中间变量——HOST/PORT/MAX_CONCURRENCY 收回视野）；新发现 7 个 spec 死镜像字段显式登记（清理方向：删副本或改消费点） | ✅ 已落地（2026-09-05） | `scripts/check_config_refs.py` |
| S-05 | 审计文档双向失真（评估 P1） | `SECURITY_AUDIT` 头部追加 2026-09-05 状态更新节（M1 已修复 / M2 休眠降级），原文保留；安全需求统一收敛至 `SECURITY.md` 矩阵 | ✅ 已落地（2026-09-05） | `SECURITY_AUDIT_MiniMax-H3-lite.md`、`SECURITY.md` |
| S-06 | 取证策略张力无决策（评估 P2） | 决策落档：维持缺省不签名 + debug 日志（`LOCAL_RULES` 第 5 条用户无感铁律优先，单机场景任务级记录足够）；需密码学取证时配置 `MMH3_SIGN_KEY` 即启用 | ✅ 已决策（2026-09-05） | `SECURITY.md` §3 |

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
