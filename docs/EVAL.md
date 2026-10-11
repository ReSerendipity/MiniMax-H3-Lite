# 生成质量评估集规范（AI/ML 评估 P2 · 语义质量评估补给线）

> 配套：`scripts/golden_compare.py`（结构性质量基线）+ `scripts/smoke_real.py`（GPU 真机冒烟）
> 定位：本文档补上"语义质量评估与主观对比留档"的流程规范；**不假覆盖**语义评分
> （CLIP score / FVD / 人工评分需真机 GPU 反复生成 + 人工标定，单机工具形态下成本不合理）。

## 一、评估集设计（固定 seed 样本表）

评估集 = 一组「固定 prompt + 固定参数 + 固定 seed」的样本，用于跨版本/跨引擎对比。
样本表建议（本仓约定，新增样本须在此登记）：

| 样本 ID | 模式 | prompt（示例） | 参数（duration/aspect/resolution/seed） | 用途 |
| --- | --- | --- | --- | --- |
| eval-t2v-01 | text (T2V) | "A cat walking on a beach, cinematic." | 5s / 16:9 / 0.98 / 42 | 引擎/版本一致性主样本 |
| eval-i2v-01 | first_frame (I2V) | 跟随首帧尺寸 + 运动描述 | 5s / 16:9 / 0.98 / 7 | 首帧跟随回归 |
| eval-r2v-01 | ref (R2V) | 官方标签引用（见 PROMPT_GOVERNANCE.md） | 5s / 16:9 / 0.98 / 2026 | 多模态参考回归 |

原则：**seed 必须固定**（可复现性依赖 seed 血缘机制，见 `tests/test_seed_lineage.py`）；
样本变化（换 prompt/参数/seed）须登记为**新样本 ID**，不覆盖旧样本（保证历史可比）。

## 二、结构性基线（已落地工具，勿重复造轮子）

```bash
# 记录基线（模型/引擎就位后执行一次）
python scripts/golden_compare.py record --name eval-t2v-01 --video outputs/eval-t2v-01.mp4 --params '{"seed":42}'
# 对比（容差：duration 0.20s / fps 0.50 / size_ratio 15%；超差退出码 1）
python scripts/golden_compare.py compare --name eval-t2v-01 --video outputs/eval-t2v-01.mp4
# 人工确认后刷新基线
python scripts/golden_compare.py compare --name eval-t2v-01 --video outputs/eval-t2v-01.mp4 --update
```

退出码：0=一致 / 1=检出回归 / 2=跳过（无基线、无 ffprobe、视频不存在）。

## 三、主观对比留档流程

结构基线无法捕获语义劣化，人工对比是唯一兜底。每次**推理服务升级 / 引擎切换 / 参数契约变更
（SPEC_VERSION +1）**后：

1. 用评估集样本（固定 seed）重新生成视频；
2. 新旧成片并排（建议 2×2 网格，逐样本截图存 `outputs/eval/<样本ID>_<版本>.png`）；
3. 按以下维度逐样本打分并留档（表头含：日期、提交 hash、引擎版本、backend）：
   - 指令遵循（prompt adherence）：1-5
   - 时序连贯（temporal consistency）：1-5
   - 运动合理性（motion plausibility）：1-5
   - 参考保真（仅 R2V：identity/detail retention）：1-5
4. 结论记录到 `docs/EVAL.md` 附录或 `.workbuddy` 评估记忆：**结论为"回归"时回滚或登记降级，不得静默继续**。

## 四、与 CI 的关系

- `gpu-smoke.yml` 已含 `golden_compare.py compare` 步骤（结构基线自动对比，见该 workflow）；
- 语义评分（CLIP/FVD）与人工留档**不进 CI**（需 GPU 与人工，成本与工具形态不匹配）——
  由本文档流程承载，作为发布/升级前的质量闸门。

## 五、边界声明（诚实边界）

- golden_compare 的采样帧哈希对比依赖 seed 血缘（同参数+同 seed → 可复现）；无 seed 的
  逐帧对比恒失败，仅粗粒度指标（时长/帧率）有意义——这是设计取舍，不是缺陷。
- 本规范不承诺"自动发现语义退化"；它提供的是**固定样本 + 结构基线 + 人工留档**的完整链路。
