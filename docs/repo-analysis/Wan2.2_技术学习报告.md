# Wan2.2 技术学习报告（MiniMax-H3-lite 竞品对标 · 代码级）

> **性质**：竞品（视频扩散模型）对标学习报告（非建议文档）。事实来自 `C:\Users\Doro\reference_repos\MiniMax-H3-lite\Wan2.2` 浅克隆 + `gh api` 实时核验。
> **核验**：`Wan-Video/Wan2.2` — **17,388★ / Apache-2.0 / Python / `pushed_at=2026-03-17`**。

## 一、概览
- **定位**：阿里开源的大规模视频生成基础模型（Wan2.2），视频扩散方向头部项目，星数最高（17.4k）。
- **许可**：**Apache-2.0**——可自由借鉴/商用，**无 GPL 传染风险**。
- **形态**：模型权重 + 推理代码 + 多任务配方（T2V / I2V / TI2V / S2V / Animate）。

## 二、技术栈（README + 仓库结构）
- 运行时：Python；`requirements.txt`（torch ≥ 2.4.0，flash_attn 最后装）；提供 `wan/` 推理包与多任务脚本。
- 架构亮点：**MoE（混合专家）** 跨时间步分离去噪专家，扩充容量不增算力；VAE 压缩比 **16×16×4**；5B 模型（Wan2.2-VAE）支持 720P@24fps，可在 4090 消费卡跑。
- 生态：ComfyUI 官方集成（docs.comfy.org 教程）、Diffusers 集成（T2V-A14B / I2V-A14B / TI2V-5B）。

## 三、核心能力
- **多任务**：T2V（A14B/14B）、I2V（A14B）、TI2V（5B，720P@24fps）、**S2V 语音驱动视频（Wan2.2-S2V-14B，外接 CosyVoice 合成语音）**、**Animate 角色动画/替换（Wan2.2-Animate-14B）**。
- **电影级美学**：精细光照/构图/色调标签，可控风格生成。
- **复杂运动**：数据量较 2.1 大幅提升（+65.6% 图 / +83.2% 视频），运动/语义/美学泛化强。
- **低显存路径**：DiffSynth-Studio 提供层离屏、FP8 量化、序列并行、LoRA/全量训练——对应本仓低显存目标。

## 四、与 MiniMax-H3-lite 对标点（关键）
- **视频质量直接竞品**：Wan2.2 是 H3 在「文/图生视频」维度的强对手，且 Apache-2.0 可商用（H3 为社区许可受限）。
- **音频差异是 H3 护城河**：Wan2.2 **基础版无原生音频**，S2V 需外接 CosyVoice 合成语音（非原生同步立体声）；H3 原生同步立体声 32kHz。本仓若主打「音视频一体」应优先 H3。
- **可借鉴的工程加速**：MoE 跨时间步专家、FP8 量化、层离屏、ComfyUI/Diffusers 双集成模式，可作为本仓视频链路的加速与集成范式。

## 五、许可与合规
- **Apache-2.0**：代码/权重可自由借鉴与商用；模型权重须按本仓 `THIRD_PARTY_NOTICES.md` 登记（与现有合规框架一致）。
- 无 GPL 内核依赖，区别于 ComfyUI custom_nodes 的 9 个 GPL-3.0 节点。

## 六、可借鉴点（P0/P1）
- **P1**：MoE 跨时间步去噪、FP8 量化、层离屏作为本仓视频推理加速参考；ComfyUI + Diffusers 双集成模式作为本仓分发范式。
- **P1**：若本仓需「无音频纯视频」高质链路，Wan2.2-5B（4090 可跑）是 H3 之外的轻量备选。

## 七、风险 / 不适用
- 原生非音视频联合模型（与 H3 定位差一档）；若本仓核心卖点是同步音频，Wan 仅作补充。
- 14B 模型显存门槛高，须走 FP8/离屏；5B 才是消费卡友好档。

## 八、参考文件（克隆内可复核）
- `reference_repos/MiniMax-H3-lite/Wan2.2/README.md`（创新点 / 模型下载 / 运行 / 社区工作）
- `reference_repos/MiniMax-H3-lite/Wan2.2/wan/`（推理包）
- `reference_repos/MiniMax-H3-lite/Wan2.2/requirements.txt`（依赖）
