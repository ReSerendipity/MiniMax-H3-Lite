# LTX-Video 技术学习报告（MiniMax-H3-lite 竞品对标 · 代码级）

> **性质**：竞品（视频扩散模型）对标学习报告（非建议文档）。事实来自 `C:\Users\Doro\reference_repos\MiniMax-H3-lite\LTX-Video` 浅克隆 + `gh api` 实时核验。
> **核验**：`Lightricks/LTX-Video` — **10,930★ / Apache-2.0 / Python / `pushed_at=2026-01-05`**。
> ⚠️ **项目状态**：仓库 HEAD（4b2d053）为「LTX-2 redirect notice」；**开源 LTX-Video 已由 LTX-2 接替为主开发线**（LTX-2 为首个 DiT 音视频同步基础模型）。本报告基于 LTX-Video 0.9.8 线，落地时优先参考 LTX-2。

## 一、概览
- **定位**：Lightricks 开源的 **DiT 视频生成模型**，强调同步音频+视频、高保真、多性能模式、生产可用、开放获取。
- **许可**：**Apache-2.0**——可自由借鉴/商用，**无 GPL 传染风险**。
- **形态**：模型权重 + 推理代码（`inference.py`、`ltx_video/` 包）+ 配置（`configs/`）+ 训练工具（LTX-Video-Trainer 外部仓）。

## 二、技术栈（README + 仓库结构）
- 运行时：Python；`pyproject.toml`；推理入口 `inference.py`；核心包 `ltx_video/`。
- 能力接口：在线 demo、本地运行、ComfyUI 集成（ComfyUI-LTXVideo）、Diffusers 集成。
- 配置：`configs/ltxv-13b-0.9.8-{dev,distilled,dev-fp8,distilled-fp8}.yaml`、`ltxv-2b-*.yaml` 等多档模型配置。

## 三、核心能力
- **同步音频+视频**：单次生成可达 50 FPS、原生 4K、同步音频（LTX-2 进一步：最长 10s 连续同步音视频、算力降 50%）。
- **多条件控制**：I2V、多关键帧、视频扩展（前/后向）、V2V；IC-LoRA 控制模型（depth/pose/canny）、LoRA 微调（2B 蒸馏 LoRA 仅需 1GB VRAM）。
- **蒸馏与实时**：13B/2B 蒸馏模型；FP8 权重支持 H100 实时；低分辨率预览 3s 出图。
- **ComfyUI 原生集成**：官方内置 ComfyUI 工作流（与 MiniMax-H3-lite 的 ComfyUI 路线契合）。

## 四、与 MiniMax-H3-lite 对标点（关键）
- **音视频同步竞品**：LTX（尤其 LTX-2）与 H3 同属「原生同步音频视频」赛道；LTX-2 已内建 ComfyUI 核心集成，与本仓 `comfy_kernel` 路线天然契合。
- **轻量 LoRA 门槛低**：2B 蒸馏 + 1GB VRAM LoRA，是消费卡微调的友好范式；对比 H3 无开源训练代码，LTX 训练链路更完整。
- **差异化**：H3 由托管 Context-IR 做多模态理解（闭源），LTX 走 DiT 原生一体；本仓若需「可训练/可微调」音视频模型，LTX 系比 H3 更自主。

## 五、许可与合规
- **Apache-2.0**：代码/权重可自由借鉴与商用；按本仓 `THIRD_PARTY_NOTICES.md` 登记即可。
- 无 GPL 内核依赖，区别于 ComfyUI custom_nodes 的 9 个 GPL-3.0 节点。

## 六、可借鉴点（P0/P1）
- **P1**：LTX-2 的 ComfyUI 原生集成 + 多关键帧/IC-LoRA 控制范式，作为本仓 ComfyUI 视频工作流的对照模板。
- **P1**：2B 蒸馏 + FP8 + 1GB-VRAM LoRA 的低显存微调链路，作为本仓视频 LoRA 训练参考（与 sd-scripts/fluxgym 报告互补）。

## 七、风险 / 不适用
- 开源线已转向 LTX-2，LTX-Video 0.9.8 进入维护态；落地须以 LTX-2 为基准，本报告须随 LTX-2 复盘更新。
- 4K/50FPS 高规格需多卡推理栈，单消费卡仅能跑 2B 蒸馏低分辨率档。

## 八、参考文件（克隆内可复核）
- `reference_repos/MiniMax-H3-lite/LTX-Video/README.md`（介绍 / News / LTX-2 重定向）
- `reference_repos/MiniMax-H3-lite/LTX-Video/inference.py`（推理入口）
- `reference_repos/MiniMax-H3-lite/LTX-Video/ltx_video/`（核心包）
- `reference_repos/MiniMax-H3-lite/LTX-Video/configs/`（多档模型配置）
- `reference_repos/MiniMax-H3-lite/LTX-Video/pyproject.toml`（依赖）
