# MiniMax H3 Community License — 全文获取与核验指引

> **状态（2026-09-16，P1-3 已收口）**：License 全文已随仓入库——`MiniMax-H3-Community-License.txt`
> （17.6KB，License date: **August 2, 2026**；经 HF raw 端点拉取）。下方核对清单已对照全文逐项验证。

## 官方全文来源（唯一权威）

- 模型页：https://huggingface.co/MiniMaxAI/MiniMax-H3
- 许可全文：https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE
- 原始文本（便于保存）：https://huggingface.co/MiniMaxAI/MiniMax-H3/raw/main/LICENSE

## 核对清单（保存全文后逐项勾选）

- [x] 许可名称确为 "MiniMax H3 COMMUNITY LICENSE AGREEMENT"（全文首行，与 NOTICE 摘要一致）
- [x] 地域排除条款：定义条款第 5 条明列欧盟/英国/大韩民国/美国（全文 L10）
- [x] 商用门槛：收入超阈值需经 api@minimax.io 取得事先书面授权（全文 L36）
- [x] 署名要求：产品/服务须展示使用 MiniMax H3 的声明（全文 L29）
- [x] 再分发义务：向第三方分发须随附 "NOTICE" 声明文本（全文 L32）——全文入库后本仓已满足
- [x] 输出限制：不得用 MiniMax H3 Works/Outputs 训练其他 AI 模型（全文 L41）；AUP 见 Exhibit A（L61）
- [x] 版本记录见下表

## 版本记录

| 日期 | 全文版本/日期标记 | 保存人 | 备注 |
|---|---|---|---|
| 2026-09-16 | License date: August 2, 2026 | AutoClaw（HF raw 端点拉取，17.6KB） | 与 NOTICE 摘要逐条吻合 |

## 与本仓的关系

- `workflows/` 三份官方 ComfyUI 模板随本仓分发，构成对 MiniMax 官方材料的再分发——
  依 NOTICE:23 须随附完整协议副本：**全文现已随仓（本目录 txt），义务已满足**；
  分发前自查清单（GPL_COMPLIANCE.md §2）中"协议全文在包内"项默认通过。
- encoder `Qwen3-VL-32B` 为 Apache-2.0，不受本许可约束（NOTICE:26-27）。
