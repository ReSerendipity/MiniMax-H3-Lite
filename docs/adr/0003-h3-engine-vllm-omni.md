**ADR-0003: H3 服务引擎切换评估（引入 vllm-omni 作为推荐默认引擎）**

- **状态**: Proposed（PoC 门控，待验证后转 Implemented）
- **日期**: 2026-09-03
- **决策者**: 项目维护者 + AI 指挥（家族规范审计 / §4.5 任务 #3）
- **关联**: `docs/repo-analysis/MiniMax-H3_技术学习报告.md`、`docs/repo-analysis/vllm-omni_技术学习报告.md`、`docs/repo-analysis/Wan2.2_技术学习报告.md`、`docs/repo-analysis/LTX-Video_技术学习报告.md`

---

# 背景与问题

1. **默认引擎为 GPL-3.0，存在合规暴露**。现场核实 `backend/engine_registry.py`：`ENGINES={"diffusers","comfy"}`，`DEFAULT_BACKEND="comfy"`，`ENV_BACKEND="MMH3_INFERENCE_BACKEND"`。即**默认 H3 服务走内嵌 ComfyUI 内核（GPL-3.0）**——这与 `docs/adr/0002` 正文「默认 diffusers」不符（代码为准，0002 描述已过时，建议后续更正）。GPL-3.0 对分发/商用传染，正是 §3.4 合规待办的核心项。
2. **H3 官方是双 DiT 联合音视频模型**。官方 README 明确 `H3-Base-FL2VA` / `H3-Base-Ref2VA` 两套任务分区，`backend/h3/spec.py` 已抽象为 `T2VA/FL2VA/REF2VA` 框架无关任务层（24FPS / 32kHz 立体声 / mp4 / 短边 768p 上限）。需要一个能原生承载双 DiT + 同步音频、且许可清洁的服务引擎。
3. **消费者级显卡落地需求**。本仓目标硬件含 RTX 5070 Ti 类消费卡；当前 comfy/diffusers 路径缺乏针对性的低显存 H3 配方。

# 评估的备选方案

- **方案 A：维持 comfy 默认（现状）** —— 优势：直接投递官方 ComfyUI 工作流、改动最小；劣势：**默认路径 GPL-3.0 传染**，与 §3.4 合规目标冲突，且无官方 H3 消费卡优化配方。
- **方案 B：切 diffusers 默认** —— 优势：Apache-2.0 生态、无 GPL；劣势：vllm-omni 官方配方指出其直接消费 HF H3 权重并提供 paged KV / disaggregated / 消费卡配方，diffusers 原生 H3 服务在吞吐与显存上不如 vllm-omni 针对性优化。
- **方案 C：引入 vllm-omni 作为推荐默认引擎（采纳）** —— 优势：**Apache-2.0**（消除默认路径 GPL 暴露）；官方 `recipes/MiniMaxAI/MiniMax-H3*.md` 提供 **4090/5090/NPU/MUSA** 多硬件配方（4090 用 cuDNN attention 无需 FA4，最贴近本仓消费卡）；**OpenAI 兼容 `/v1/videos`** 统一对外 API；单 diffusion stage 同载 FL2VA+Ref2VA 双 DiT、输出 H.264+同步立体声 MP4，与 `h3/spec.py` 任务层天然对齐；**生产就绪**（pushed 2026-09-03，极活跃）。劣势：框架体量大（3,388 文件）、依赖 vLLM 主线，需评估与现有 `comfy_kernel` 共存/切换成本；H3 权重仍受 MiniMax H3 Community License 约束（需 HF 审批，商用另授权——见 `MiniMax-H3_技术学习报告.md` §五）。
- **方案 D：vllm-omni 默认 + comfy 可选工作流（混合，最终推荐）** —— 在 C 基础上保留 comfy 为 **opt-in 工作流后端**（GPL-3.0 隔离，仅当用户显式 `MMH3_INFERENCE_BACKEND=comfy` 时加载），diffusers 保留为回退。兼顾「默认路径 Apache-2.0 合规」与「ComfyUI 官方工作流可投递」。

# 决策

- **采用方案 D**：将 **vllm-omni 设为 H3 推荐/默认服务引擎**（Apache-2.0），**comfy 降级为可选工作流后端**（opt-in、GPL-3.0 运行时隔离），**diffusers 保留为回退**。
- `backend/h3/spec.py` 的框架无关任务层（T2VA/FL2VA/REF2VA、输出规格）**直接复用**，作为 vllm-omni 适配器的参数契约，无需重写。
- 本 ADR 为**评估结论**，状态 `Proposed`；引擎适配器代码实现不在本任务范围，待 PoC 验证通过后另立实施 ADR（或本 ADR 转 Implemented）。

# 实施影响（落地清单，待 PoC 后执行）

- `backend/engine_registry.py`：`ENGINES` 增加 `"vllm-omni"` 条目（`external:True`、`implemented:False` 初态），`DEFAULT_BACKEND` 改为 `"vllm-omni"`，`comfy` 标记 `external:False` 但默认不激活。
- 新增 `backend/routers/vllm_engine.py`：封装 `vllm serve MiniMaxAI/MiniMax-H3` 启动、以 OpenAI `/v1/videos` 提交 `extra_params.task`（fl2va/ref2va）对接 `h3/spec.py`。
- 文档：`docs/adr/0002` 更正「默认 diffusers」为「默认 comfy（现状）/ 拟切 vllm-omni」；`README` / `PRD` 同步引擎说明。
- 合规：默认路径脱离 GPL-3.0，§3.4 合规待办「comfy_kernel GPL 传染」项可据此关闭（comfy 仅作隔离可选后端）。
- 依赖：引入 vllm-omni（Apache-2.0）为可选依赖；与现有 `comfy_kernel`（GPL-3.0 vendor）物理隔离，继续沿用 Image 仓 `.dockerignore` 排除模式。

# 可回滚路径与待验证项

- **回滚**：`DEFAULT_BACKEND` 复位 `"comfy"`（或 `"diffusers"`），vllm-omni 条目 `implemented=False` 即不加载——`engine_registry.switch_backend` 已支持运行时切换且环境变量可锁定。
- **待验证（PoC 门控）**：
  1. vllm-omni `MiniMax-H3-4090.md` 配方在 **RTX 5070 Ti** 实测可起服（cuDNN attention 后端，无需 FA4）；记录峰值显存。
  2. `/v1/videos` 输出 MP4 的 分辨率/帧率/音频（24FPS、32kHz 立体声）与 `h3/spec.py` 预设一致。
  3. FL2VA / REF2VA 双任务经 `extra_params.task` 正确路由，Ref2VA 多参考（≤9 图/≤3 视频/≤3 音频）参数映射无丢失。
  4. H3 权重 HuggingFace 访问审批链路打通（`hf auth login` + 模型卡授权）。
  5. 与现有 `comfy` 后端在**同一份 `h3/spec.py` 契约**下输出字节级可比（回归 `tests/test_h3_spec_consistency.py`）。
- **合规待确认**：MiniMax H3 Community License 是否允许本仓目标用途（研究/个人/商用），须在 `LICENSE_COMPLIANCE.md` 单列 H3 模型许可条目（区别于 custom_nodes GPL 审查）。
