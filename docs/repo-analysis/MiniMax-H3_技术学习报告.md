# MiniMax-H3 技术学习报告（MiniMax-H3-lite 竞品对标 · 代码级）

> **性质**：竞品（官方基座）对标学习报告（非建议文档）。事实来自 `C:\Users\Doro\reference_repos\MiniMax-H3-lite\MiniMax-H3` 浅克隆 + `gh api` 实时核验。
> **核验**：`MiniMax-AI/MiniMax-H3` — **7,908★ / 许可=MiniMax H3 Community License（自定义·非 OSI）** / Python / `pushed_at=2026-08-15`。
> ⚠️ **许可关键事实**：`gh api` 返回 `license=null`，仓库根目录**无 LICENSE 文件**（`ls LICENSE*` 为空）；README 徽标指向 HuggingFace 上的 `MiniMax H3 Community License`。即 H3 权重/代码采用**自定义社区许可（非开源、大概率含研究/非商用与商用授权限制）**，与 Apache-2.0/MIT 的竞品（vllm-omni/Wan2.2/LTX-Video）性质完全不同，本仓商用前须单独核验授权。

## 一、概览
- **定位**：通用全模态生成系统（omni-modal），统一理解文本/图像/视频/音频，并**原生生成带立体声的视频**（最高 2K / 15s / 24FPS / 32kHz 立体声）。
- **形态**：本仓库是**模型权重 + 推理代码 + 架构说明**仓（diffusers 风格目录：`FL2VA/`、`Ref2VA/`、`transformer/`、`text_encoder/`、`tokenizer/`、`vae/`、`audio_vae/`、`audio_scheduler/`、`scheduler/`、`processor/`、`scripts/`）。
- **生态**：在线 API（platform.minimax.io）、在线 App（hailuoai.video / hub.minimax.io）、HuggingFace / ModelScope 权重分发。

## 二、技术栈（README + 仓库结构）
- 推理：Python；依赖见 `requirements.txt`；提供 `scripts/`（推理脚本）、`processor/`（多模态预处理）、`tokenizer/`（含 `<d>` 等特殊 token）。
- 三大模块：
  - **H3-Context-IR**：多模态指令理解/精炼 → Context-IR 结构化表示。**⚠️ 该模块为托管服务，未开源，仅提供 API 复现官方行为**（README 原文）。
  - **H3-Base**：基于 Context-IR 生成 768p 视频+音频。
  - **H3-Regenerate-2K**：将 768p 结果与原文上下文回灌 H3，重生成 2K。
- 架构细节（README「Model Architecture」）：H3-Encoder 复用 **Qwen3-VL-32B 第 50 层隐藏态**；VisualVAE 时空压缩 f16t4d24 + ViT 解码器降成本；AudioVAE 40Hz 潜空间、左右声道独立处理；H3-Omni-Transformer 联合预测视频/音频潜变量。

## 三、核心能力
- **原生音视频联合生成**：视频与同步立体声一次生成（区别于 Wan2.2 基础版需外接 CosyVoice、LTX 基础版需 LTX-2 才同步音频）。
- **两种模型变体**：`H3-Base-FL2VA`（首/尾帧，支持 0/1/2 张图→T2V/首帧/首尾帧）、`H3-Base-Ref2VA`（全参考：≤9 图、≤3 视频、≤3 音频，跨模态文件上限 12）。
- **稀疏注意力**：原生支持稀疏注意力训练/推理（初始开源版仅全注意力，稀疏实现后续放出）——长序列降本关键。
- **多语言**：稳定支持 11 种语言（含中/英/日/韩），与用户多语言站点需求一致。

## 四、与 MiniMax-H3-lite 对标点（关键）
- **本仓即被对标对象**：MiniMax-H3-lite 的 H3 推理能力直接来源于此官方仓；本报告是 T3「H3 官方对标 + 引擎切换」的事实基座。
- **Context-IR 未开源 = 最大自托管缺口**：官方仅给 API 复现；本仓若要做离线/私有化 H3，需**自建 Context-IR 等价预处理**（或长期依赖 MiniMax API），这是 H3-lite 架构的核心约束。
- **Qwen3-VL-32B 文本编码器**：与用户本地 ComfyUI 的 Qwen3-VL 系一致，TE 资源可复用。
- **2K 重生成两阶段**：推理管线需分 Base + Regenerate 两段，调度/显存规划须按此建模。

## 五、许可与合规
- **MiniMax H3 Community License（自定义，非 OSI）**：仓库无 LICENSE 文件、GitHub 无法识别；权重在 HuggingFace 需**访问审批**（gh 文档提及 `hf auth login` + 审批）。
- 影响：本仓若将 H3 用于**任何产品/商用**，必须先取得 MiniMax 商用授权；仅研究/个人使用亦须遵守社区许可条款。须在 `LICENSE_COMPLIANCE.md` 单列 H3 模型许可条目（区别于 custom_nodes 的 GPL 审查）。
- 代码（推理脚本）随权重许可分发，**不等同于 Apache-2.0**，借鉴代码前须确认许可允许。

## 六、可借鉴点（P0/P1）
- **P0**：H3-Base / Regenerate-2K 的两阶段推理封装、Qwen3-VL-32B TE 集成方式、VisualVAE/AudioVAE 潜空间参数（f16t4d24 / 40Hz）作为本仓 H3 推理管线的规格基准。
- **P0**：Ref2VA 的多模态参考聚合接口设计（≤9 图/≤3 视频/≤3 音频），作为本仓多参考输入的schema 参考。
- **P1**：稀疏注意力降本思路（对比本仓 fp8/gguf 路线）。

## 七、风险 / 不适用
- Context-IR 闭源 → 离线全能力不可用，须 API 或自研替代。
- 自定义许可 ≠ 开源；商用受阻，竞品 vllm-omni/Wan2.2/LTX-Video 均为 Apache-2.0/MIT，可借鉴性更高。
- 仓库仅权重+推理，无训练代码；LoRA/微调需另寻路径（见 sd-scripts / fluxgym 报告）。

## 八、参考文件（克隆内可复核）
- `reference_repos/MiniMax-H3-lite/MiniMax-H3/README.md`（系统概览、架构、变体）
- `reference_repos/MiniMax-H3-lite/MiniMax-H3/FL2VA/`、`Ref2VA/`（双 DiT 权重布局）
- `reference_repos/MiniMax-H3-lite/MiniMax-H3/transformer/`、`text_encoder/`、`vae/`、`audio_vae/`、`audio_scheduler/`、`scheduler/`、`processor/`、`scripts/`（推理与多模态组件）
- `reference_repos/MiniMax-H3-lite/MiniMax-H3/requirements.txt`（依赖/许可线索）
