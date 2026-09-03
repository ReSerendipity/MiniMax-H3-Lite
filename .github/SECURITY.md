# Security Policy

> MiniMax-H3-lite 安全策略。最后更新：2026-08-27（与代码实测逐项对齐）

## 一、项目形态与默认安全姿态

MiniMax-H3-lite 是**本地单机运行**的 MiniMax H3 视频生成时间线工作台：

- 后端为 **FastAPI**（`backend/main.py`），**单端口**统一提供 Jinja2 页面 + `/api/*` 接口 + 静态资源（`/assets`、`/uploads`）。
- 服务默认仅绑定 **`127.0.0.1`**，不对外网开放（见 `backend/config.py` 的 `HOST="127.0.0.1"` 默认值与 `from_env()` 的 `MMH3_HOST`/`MMH3_PORT` 覆盖）。
- **当前版本无内置鉴权中间件**（后端全量 grep 无 `HTTPBearer` / `Depends` 鉴权 / `Authorization` 头处理）。因此：**不要**在修改 `MMH3_HOST` 后把服务暴露到局域网/公网而不自行加一层访问控制；如需对外，请前置反向代理 + 鉴权。
- 本项目**不收集、不上传任何用户数据**；所有数据（SQLite 库、上传素材、生成结果、checkpoint）均存于本机仓库目录（`data/`、`uploads/`、`outputs/`）。

## 二、支持的版本范围

| 版本 | 支持状态 | 说明 |
|---|---|---|
| `main` 分支（HEAD） | ✅ 活跃维护 | 以最新提交为准，安全修复直接合入 |
| 旧 tag / 分支 | ⚠️ 尽力而为 | 项目为个人/研究性质，无正式 LTS 承诺；建议始终跟踪 `main` |

漏洞修复通常以「合入 `main` + 在 AGENTS.md 修订记录标注」的方式交付，不单独出安全公告。

## 三、`127.0.0.1` 监听约束

- 默认：`HOST = "127.0.0.1"`，`PORT = 18080`（`backend/config.py` 顶部常量）。
- 运行方式：`uvicorn backend.main:app`（或仓库 launch 脚本），保持默认即仅本机可访问。
- 环境变量可覆盖：`MMH3_HOST` / `MMH3_PORT`。**任何将其改为 `0.0.0.0` 或局域网地址的操作，都等于主动扩大攻击面**——先自行配置鉴权/防火墙再暴露。
- 前台页面与 API 同源同端口，无 CORS 跨域白名单配置（同源访问，无额外暴露）。

## 四、`comfy_kernel` 第三方节点风险

仓库**内嵌了上游 ComfyUI 内核**（`comfy_kernel/`，B 方案进程内复用，`INFERENCE_BACKEND="comfy"` 时启用），并随包携带 **17 个第三方自定义节点包**（`comfy_kernel/custom_nodes/`，不含 `__pycache__`）：

```
comfyui_controlnet_aux, ComfyUI_Dynamic-RAMCache, ComfyUI_IPAdapter_plus,
ComfyUI_toyxyz_test_nodes, ComfyUI_UltimateSDUpscale, ComfyUI-EsesImageCompare,
ComfyUI-GGUF, ComfyUI-Impact-Pack, ComfyUI-Inspire-Pack, ComfyUI-KJNodes,
ComfyUI-Manager, ComfyUI-ReservedVRAM, ComfyUI-RMBG, ComfyUI-SeedVR2_VideoUpscaler,
ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, rgthree-comfy
```

风险与处置：

- 自定义节点的 Python 代码以**与主进程相同权限**执行，恶意/漏洞节点可直接读写本机文件、执行任意代码。
- `.gitignore` 已将大体积第三方目录排除（不入库），但**本机工作区仍然存在**，请勿随意更新到未审计版本。
- 使用任何工作流前，建议对 `comfy_kernel/custom_nodes/` 下节点包的来源、版本、补丁记录做一次核对（分布台账见 `docs/LICENSE_COMPLIANCE.md`，各包许可证与商用合规判定逐项列出）。
- 仅在你实际需要 Comfy 后端（B 方案）时启用；仅使用 `diffusers` 后端（默认）时，`comfy_kernel` 代码不会被加载执行，攻击面显著缩小。

## 五、密钥与敏感信息处理

- 本仓库**没有**任何内置 API key / token / 证书硬编码；`backend/config.py` 全部为本地路径、模型名、采样参数等非机密配置。
- 环境变量（`MMH3_HOST`、`MMH3_PORT`、`MMH3_MODEL_PATH` 等）仅用于连接与路径覆盖，不承载密钥。
- 模型权重存放于 `model/`（便携模式自包含），属大文件不进 git。
- 上传素材与生成结果位于 `uploads/`、`outputs/`、`data/checkpoints/`——如涉及他人肖像/隐私内容，请在使用后及时清理本机副本。
- **不做**把令牌写入代码、日志或提交记录的操作；如未来引入外部服务鉴权，须走环境变量/配置文件且不入库。

## 六、发现漏洞如何报告

请**不要**公开先披露。优先通过 GitHub Issues 提交（仓库私有或公开均可见维护者），或直接联系维护者；描述尽量含：影响范围、可复现步骤（最小示例）、建议缓解方案。修复将合入 `main` 并在 AGENTS.md 修订记录中标注（含「证据绑定」校验，确保修复描述不与实现脱节）。

处理流程（与 AGENTS.md 修订协议一致）：

1. **Triage**：48 小时内确认可复现与影响面；
2. **修复**：合入 `main`，补回归用例（如有对应测试层）；
3. **发布**：修订记录追加一行（描述用泛化语言，不复述敏感细节），版本号按仓内协议递增；
4. **披露**：由报告者决定是否在修复落地后再公开细节，避免 0-day 窗口扩大。

## 七、数据流与存储说明（本地自管）

- 项目运行期间产生的数据全部为**本地文件**：`data/mmh3.db`（SQLite 任务库）、`uploads/`（上传素材）、`outputs/`（生成结果）、`data/checkpoints/`（断点续跑快照）。
- 除「主动调用的远端模型权重拉取」（HuggingFace / ModelScope）与「B 方案下连本机 ComfyUI（`COMFY_URL`，默认 127.0.0.1:8188）」外，服务**不发起任何外联**。
- 模型权重仅作本地加载与推理，不上传任务内容。
- 如任务内容涉及敏感素材，使用后删除 `uploads/`、`outputs/` 对应文件即可完成本地数据擦除（无服务端副本）。

## 八、相关文件索引

| 路径 | 职责 |
|---|---|
| `backend/main.py` | FastAPI 应用入口与路由挂载 |
| `backend/config.py` | 服务地址、端口、模型、上传限额等全部配置 |
| `backend/routers/queue_manager.py` | 任务队列（单机串行 `MAX_CONCURRENCY`）与断点续跑 |
| `comfy_kernel/custom_nodes/` | 17 个第三方节点包（B 方案，需审计） |
| `docs/COMPLIANCE_CHECKLIST.md` | 合规检查清单（本地文档，未随仓库发布） |
| `docs/LICENSE_COMPLIANCE.md` | 三方组件/节点许可证台账与合规判定（本地文档，未随仓库发布） |
| `scripts/check_comfy_kernel.py` | Comfy 内核复用只读检查脚本 |