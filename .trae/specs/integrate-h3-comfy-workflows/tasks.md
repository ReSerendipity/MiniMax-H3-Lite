# Tasks

- [x] Task 1: 新增框架无关任务规格层 `backend/h3/`（新建 `__init__.py` + `spec.py`）
  - [x] SubTask 1.1: 任务类型常量（`t2va`/`fl2va`/`ref2va`）与 `mode → task_type` 映射
  - [x] SubTask 1.2: `frames_for_duration(d)`：`max(5, round(d*24)) + (5 - (max(5, round(d*24)) % 17)) % 17`
  - [x] SubTask 1.3: `resolution_for(aspect, short_side=768, multiple)`：取偶（diffusers）/32 倍数（ComfyUI），上限 768×1344
  - [x] SubTask 1.4: 官方模型文件名与采样默认值常量（fl2va/ref2va 扩散、clip、video/audio VAE；`res_multistep`/`simple`/20 步）
  - [x] SubTask 1.5: refs 分组规范（首帧图 / 末帧图 / 参考图 / 参考视频 / 参考音频）与上限常量

- [x] Task 2: 补全默认 diffusers 路径（[inference.py](file:///c:/Users/Doro/MiniMax-H3/backend/routers/inference.py)，脱离 ComfyUI 的核心闭环）
  - [x] SubTask 2.1: `_build_params` 重构为基于规格层，产出结构化任务（task_type / prompt / width / height / num_frames / fps / audio_sample_rate / refs 分组）
  - [x] SubTask 2.2: `_run_diffusers` 按规格层构造 `ModularPipeline` 输入：t2va 纯文本；fl2va 传 `image`(+`last_image`)；ref2va 传 `ref_images`/`ref_videos`/`ref_audios`
  - [x] SubTask 2.3: `num_frames` 改用 `frames_for_duration(d)`（不再 `duration*fps` 直算）

- [x] Task 3: 重写 ComfyUI 可选执行器
  - [x] SubTask 3.1: 新增 `backend/comfy_workflow.py`：按 task_type 构建 API 格式 prompt（`MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo` + UNET/CLIP/双 VAE + res_multistep 采样 + CreateVideo/SaveVideo），消费规格层
  - [x] SubTask 3.2: 参考素材上传 helper（默认 `/upload/image` input 型，图/视频/音频按 kind 分组注入加载节点）
  - [x] SubTask 3.3: 结果经 `/view?filename=&subfolder=&type=output` 下载，兼容远程 ComfyUI
  - [x] SubTask 3.4: `_run_comfyui` 委托 `comfy_workflow`，移除旧式 CheckpointLoaderSimple / EmptyH3LatentVideo / KSampler 硬编码工作流

- [x] Task 4: 后端推理引擎注册与切换（参照 Image_MultiModel / SeedVR2 / TTS_MultiModel 模式）
  - [x] SubTask 4.1: 新增 `backend/engine_registry.py`：声明可用引擎（diffusers 本地 / comfyui 外部 / sglang 未实现），提供 `list_engines()` / `switch(name)` / `active()`
  - [x] SubTask 4.2: 新增运行时配置持久化 `backend/settings_store.py`（`data/settings.json`，env 优先），`run_inference` 据此选后端
  - [x] SubTask 4.3: 新增 `backend/routers/system.py`：`GET /api/engines`、`POST /api/engine/switch`、`GET/POST /api/system/settings`
  - [x] SubTask 4.4: `backend/main.py` 注册新路由；`/api/health` 增加 `backend` 与 `backend_requires_external` 字段

- [x] Task 5: 前端推理引擎切换器（[index.html](file:///c:/Users/Doro/MiniMax-H3/index.html)）
  - [x] SubTask 5.1: 状态栏 `ENGINE: MINIMAX H3` 改为可点击切换器（下拉列出可用引擎 + 激活态 + 是否需要外部服务标注；sglang 置灰）
  - [x] SubTask 5.2: 切换逻辑：`GET /api/engines` 初始化 → `POST /api/engine/switch` 切换 → 更新状态栏与 `CONN`；默认「本地 diffusers」无需 ComfyUI
  - [x] SubTask 5.3: 相关 CSS 与可访问性（aria 标注、键盘可达）

- [x] Task 6: [generations.py](file:///c:/Users/Doro/MiniMax-H3/backend/routers/generations.py) 模式校验微调
  - [x] SubTask 6.1: `first_frame`/`last_frame`/`first_last` 需提供对应图片 ref；`ref` 需提供 ref_ids；否则 422 明确提示

- [x] Task 7: 一致性测试与回归
  - [x] SubTask 7.1: 新增测试：加载三份 JSON，断言规格层模型文件名一致（t2v/i2v→fl2va 权重，r2v→ref2va 权重）
  - [x] SubTask 7.2: 帧长公式抽样核对（4→107、8→192、10→243、15→362）
  - [x] SubTask 7.3: 引擎切换冒烟：`GET /api/engines` 列表、`POST /api/engine/switch` 持久化与回读、`/api/health` 含 `backend` 字段
  - [x] SubTask 7.4: 运行 `tests/test_api_smoke.py` 确保既有功能不回归

# Task Dependencies

- [Task 2] 依赖 [Task 1]
- [Task 3] 依赖 [Task 1]
- [Task 4] 独立（可与 Task 1–3 并行）
- [Task 5] 依赖 [Task 4]
- [Task 6] 独立（可与 Task 1–5 并行）
- [Task 7] 依赖 [Task 1]–[Task 6]