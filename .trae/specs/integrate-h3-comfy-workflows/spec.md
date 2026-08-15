# 集成官方工作流能力 + 推理引擎切换 Spec（保持脱离 ComfyUI 可运行）

## Why

- 三份官方工作流（`workflows/video_minimax_h3_t2v.json` / `_i2v.json` / `_r2v.json`）封装了 H3-Base 本地生成的三种任务 **t2va / fl2va / ref2va** 的**权威参数语义**：帧长按 24fps 下 17k+5 网格、768 短边 / 32 倍数分辨率、官方模型文件名（fl2va / ref2va 扩散权重、Qwen3-VL clip、视频/音频 VAE）、`res_multistep` 采样、参考素材上限与 `<Picture N>` / `<Video N>` / `<Audio N>` 标签语义。
- 本项目设计为**脱离 ComfyUI 也能运行**：默认 `INFERENCE_BACKEND=diffusers`，进程内 `ModularPipeline` 完成 768p 闭环，ComfyUI 仅是可选后端之一。因此本次集成**不是把 ComfyUI 作为后端**，而是：
  1. 将三份官方工作流固化为**框架无关的任务规格层**（单一事实源，不依赖任何推理框架）；
  2. 默认 diffusers 路径据此**补全** t2va / fl2va / ref2va（现状：首尾帧与多模态参考的输入映射不完整、`num_frames` 未按网格对齐）；
  3. ComfyUI 作为**可选执行器**消费同一规格层（现状：内置工作流节点结构/模型名与官方模板不兼容、不处理参考素材、结果只认本机 output 目录）。
- 参照三个兄弟项目（Image_MultiModel / SeedVR2 / TTS_MultiModel）的成熟模式：三者前端均提供**引擎/模型切换入口**（顶栏菜单、设置抽屉或状态栏），后端提供 `GET /engines` + `POST /engine/switch|load|unload` 与**配置持久化**，且默认均为本地进程内引擎、完全脱离 ComfyUI。当前本项目前端**没有任何切换入口**（状态栏 `ENGINE: MINIMAX H3` 为写死文本，后端引擎只能靠环境变量）。需要补齐：前端可切换的推理模式选项 + 后端引擎注册表与持久化。

## What Changes

- **新增框架无关的任务规格层** `backend/h3/`（`__init__.py` + `spec.py`）：
  - 任务类型常量与模式映射：`text → t2va`；`first_frame / last_frame / first_last → fl2va`；`ref → ref2va`；
  - `frames_for_duration(d)`：`max(5, round(d*24)) + (5 - (max(5, round(d*24)) % 17)) % 17`（4→107 / 8→192 / 10→243 / 15→362）；
  - `resolution_for(aspect, short_side=768, multiple)`：`multiple=2`（diffusers 取偶）/ `multiple=32`（ComfyUI 对齐 `ResolutionSelector`），上限 768×1344；
  - 官方模型文件名映射与采样默认值（fl2va / ref2va 扩散、clip、video VAE、audio VAE；`res_multistep` / `simple` / 20 步）；
  - refs 分组规范：首帧图 / 末帧图 / 参考图 / 参考视频 / 参考音频，及上限（图≤9、视频≤3、音频≤3、混合≤12）。
- **默认 diffusers 路径补全**（脱离 ComfyUI 的核心闭环）：`_run_diffusers` 按规格层构造 `ModularPipeline` 输入——t2va 纯文本；fl2va 传 `image`（首帧）+ `last_image`（末帧）；ref2va 传 `ref_images` / `ref_videos` / `ref_audios`；`num_frames = frames_for_duration(d)`。
- **ComfyUI 可选执行器重写**：新增 `backend/comfy_workflow.py`（API 格式 prompt 构建 + 参考素材上传 + 结果 `/view` 下载），消费同一规格层，替换 `_run_comfyui` 内置旧式硬编码工作流。
- **推理引擎切换（前端 + 后端，参照三兄弟项目）**：
  - 后端：新增引擎注册表与运行时配置持久化——`GET /api/engines`（列出可用引擎：本地 diffusers / 外部 comfyui / 未实现 sglang，含元数据与激活态）、`POST /api/engine/switch`（切换并持久化到 `data/settings.json`，即时生效，无需重启）、`GET/POST /api/system/settings`（读写可配置项）；环境变量 `MMH3_INFERENCE_BACKEND` 仍为最高优先级。
  - 前端：[index.html](file:///c:/Users/Doro/MiniMax-H3/index.html) 状态栏 `ENGINE: MINIMAX H3` 改为可点击的**引擎切换器**（下拉列出可用引擎 + 当前激活 + 是否需要外部服务标注），切换后即时更新状态栏与 `CONN`；默认「本地（diffusers）」无需 ComfyUI。
- **生成模式校验微调** [generations.py](file:///c:/Users/Doro/MiniMax-H3/backend/routers/generations.py)：`first_frame / last_frame / first_last` 需提供对应图片 ref，`ref` 需提供 ref_ids。
- **一致性测试**：读取三份 JSON，断言规格层的任务类型、模型文件名与官方模板一致；既有 `tests/test_api_smoke.py` 保持通过。
- **BREAKING（仅限 comfyui 后端内部）**：ComfyUI 路径不再使用旧式 `CheckpointLoaderSimple` / `EmptyH3LatentVideo` / `KSampler(euler)` / 单 VAE 工作流；默认 diffusers 路径与对外 API 契约不变（仅新增端点到 `/api/health` 字段）。

## Impact

- Affected specs: PRD §6 推理接入层（6.1 能力边界 / 6.2 框架选型）、§8 API 契约（新增引擎/设置端点）、§7 非功能（性能/兼容）。
- Affected code:
  - 新增 `backend/h3/__init__.py`、`backend/h3/spec.py`（框架无关规格层）
  - `backend/routers/inference.py`（`_build_params`、`_run_diffusers`、`_run_comfyui` 重写，`run_inference` 按运行时配置选后端）
  - 新增 `backend/comfy_workflow.py`（可选 ComfyUI 执行器）
  - 新增 `backend/engine_registry.py` + `backend/settings_store.py`（或合并进 `backend/settings.py`）、`backend/routers/system.py`（`/api/engines`、`/api/engine/switch`、`/api/system/settings`）
  - `backend/main.py`（注册新路由、`/api/health` 增加 `backend` 字段）、`backend/config.py`（运行时配置项）
  - `backend/routers/generations.py`（模式校验）
  - `index.html`（状态栏引擎切换器 + 相关 JS/CSS）
  - `tests/`（一致性测试 + 引擎切换冒烟）

## ADDED Requirements

### Requirement: 框架无关任务规格层

系统 SHALL 提供基于三份官方工作流的框架无关任务规格层，作为默认 diffusers 路径与可选 ComfyUI 路径的公共参数契约。

#### Scenario: 帧长网格对齐
- **WHEN** 任意后端需要视频帧数
- **THEN** 使用 `frames_for_duration(d)`（17k+5 网格 @24fps），抽样 4→107、8→192、10→243、15→362。

#### Scenario: 分辨率规范
- **WHEN** 由宽高比计算输出尺寸
- **THEN** 768 短边；diffusers 取偶、ComfyUI 取 32 倍数，均上限 768×1344。

#### Scenario: 任务类型与模型映射
- **WHEN** 前端提交 `mode`
- **THEN** 映射为 `t2va / fl2va / ref2va` 并选用对应官方扩散权重（fl2va 权重用于 t2v/i2v，ref2va 权重用于 r2v）。

### Requirement: 默认 diffusers 路径（脱离 ComfyUI 可运行）

系统 SHALL 在默认 `INFERENCE_BACKEND=diffusers` 下，无需任何 ComfyUI 依赖即可完成 t2va / fl2va / ref2va 三种生成。

#### Scenario: 三任务闭环
- **WHEN** 提交 `text / first_frame / last_frame / first_last / ref` 任一种模式
- **THEN** `ModularPipeline` 输入按规格层正确构造（`image` / `last_image` / `ref_images` / `ref_videos` / `ref_audios`，`num_frames` 走网格公式），生成、落盘、缩略帧、状态流转全链路可用。

### Requirement: ComfyUI 可选执行器

系统 SHALL 在 `INFERENCE_BACKEND=comfyui` 下，基于同一规格层构建与官方模板一致的 API prompt 并完整执行。

#### Scenario: 选择 comfyui 后端
- **WHEN** 用户切换 / 配置 `MMH3_INFERENCE_BACKEND=comfyui`
- **THEN** 按任务类型构建 `MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo` 模板，参考素材上传后注入对应加载节点，结果经 `/view` 下载，兼容远程 ComfyUI。

### Requirement: 推理引擎切换（前端 + 后端）

系统 SHALL 提供可在前端切换并持久化的推理引擎选项，默认本地 diffusers，脱离 ComfyUI 可完整运行。

#### Scenario: 前端查看与切换引擎
- **WHEN** 用户点击状态栏 `ENGINE` 切换器
- **THEN** 展示可用引擎列表（本地 · diffusers 进程内 / 外部 · ComfyUI 服务 / 未实现 · sglang 置灰），标注当前激活项与「是否需要外部服务」；切换后状态栏与 `CONN` 即时更新。

#### Scenario: 后端引擎注册与持久化
- **WHEN** 调用 `POST /api/engine/switch`（body: `backend`）
- **THEN** 校验引擎名合法，写入运行时配置 `data/settings.json`，`run_inference` 对后续任务立即按新后端执行，无需重启；环境变量 `MMH3_INFERENCE_BACKEND` 优先级最高。

#### Scenario: 查询可用引擎与设置
- **WHEN** 调用 `GET /api/engines` / `GET /api/system/settings`
- **THEN** 返回可用引擎元数据（名称 / 显示名 / 描述 / 是否外部服务 / 是否激活）与当前可配置项；`POST /api/system/settings` 可更新并持久化。

## MODIFIED Requirements

### Requirement: diffusers 推理客户端（补全）

原 `_run_diffusers` 的输入映射 SHALL 按规格层补全：首帧/末帧分别传 `image` / `last_image`，多模态参考按 `ref_images` / `ref_videos` / `ref_audios` 分组，`num_frames` 采用网格公式；仍保持「依赖缺失或失败即抛错、绝不假成功」的既有约定。

### Requirement: ComfyUI 推理客户端（重写）

原 `_run_comfyui` 内置旧式硬编码工作流 SHALL 被规格层驱动的新实现替换（选模板 → 上传 refs → 提交 `/prompt` → 轮询 `/history` → `/view` 下载）；`run_inference` 的资产落盘 / 缩略帧 / `result_asset_id` 逻辑不变。

### Requirement: 健康检查接口（扩展）

原 `/api/health` SHALL 增加 `backend`（当前激活引擎）与 `backend_requires_external` 字段，供前端初始化引擎切换器状态。

## REMOVED Requirements

### Requirement: 旧式硬编码 ComfyUI 工作流与不完整的 diffusers 映射

**Reason**: 旧式 ComfyUI 工作流（`CheckpointLoaderSimple` + `minimax_h3.safetensors`、`EmptyH3LatentVideo` 秒帧混淆、`KSampler euler`、单 VAE、`SaveVideo` 接 IMAGE）与官方 H3 模板不兼容；diffusers 路径未按网格帧数、未正确区分首/末帧与多模态参考分组。
**Migration**: 两者统一由规格层驱动，各后端仅保留适配器。

## 风险与边界

- 官方 r2v 模板仅演示图片参考；视频 / 音频参考需对应加载节点（默认类名 `LoadVideo` / `LoadAudio`，可配置覆盖）。所连 ComfyUI 缺节点时任务以明确原因失败，不做静默降级。
- 三份 JSON 为 UI 格式（含子图 `definitions.subgraphs`），本方案不运行时解析 JSON，而是将其作为权威参照转录为规格层常量，并用一致性测试防漂移。
- 引擎切换为运行时配置持久化；若 `MMH3_INFERENCE_BACKEND` 环境变量已显式设置，则前端切换仅提示「已被环境变量锁定」或允许覆盖但不持久化——具体按「环境变量优先」原则实现并在设置接口文案中说明。
- H3-Regenerate-2K / Context-IR 未开源，本期仍不实现（沿用 PRD §6.4–§6.5 边界）。
