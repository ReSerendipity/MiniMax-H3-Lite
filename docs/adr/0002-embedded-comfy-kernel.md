**ADR-0002: 内嵌 comfy_kernel 进程内复用（B 方案）**

- **状态**: Implemented
- **日期**: 2026-08-27
- **决策者**: 项目维护者 + AI 指挥（家族规范审计确认）

---

# 背景与问题

H3 官方工作流基于 ComfyUI 生态。为支持自定义/官方工作流的直接投递，选择了「B 方案：
进程内复用 ComfyUI 内核」而非另起独立 ComfyUI 服务进程。

# 评估的备选方案

- **方案 A：独立 ComfyUI 进程 + HTTP 提交工作流** —— `COMFY_URL`（默认 `http://127.0.0.1:8188`）方式，进程隔离好但需用户先启动 ComfyUI、部署重。
- **方案 B：内嵌 `comfy_kernel/` 进程内复用** —— 开箱即用（`MMH3_INFERENCE_BACKEND="comfy"`，环境变量名见 `backend/config.py:168` 与 `backend/engine_registry.py:33`），但引入 GPL-3.0 传染风险。**采用**（B 方案，`comfy_kernel/` 随仓内嵌）。

# 决策

- 默认推理后端：`comfy`（加载内嵌 comfy_kernel）；需切其他引擎时用 `MMH3_INFERENCE_BACKEND`（`comfy` | `vllm-omni` | `diffusers`）。
  > **2026-10-20 修订**：本条原文为「默认 `diffusers`（不加载 comfy_kernel）」，已过时。
  > 现行默认由 `backend/engine_registry.py:32` `DEFAULT_BACKEND = "comfy"` 决定（ADR-0003 已把
  > vllm-omni 登记为推荐默认，待 provisioning + 5070Ti recipe 验证后翻转）。另注意
  > `backend/config.py:42 INFERENCE_BACKEND` 仍写 `"diffusers"`，与 registry 默认不一致 ——
  > 属**代码待修项**，不在本文档范围内，见 ADR-0003。
- `comfy_kernel/custom_nodes/` 随仓携带 **16 个第三方节点包**（除 `__pycache__` 外，2026-10-20 实测
  `ls -d comfy_kernel/custom_nodes/*/ | grep -v __pycache__ | wc -l`；原文写 17，已更正），各自许可证
  见 `docs/LICENSE_COMPLIANCE.md` §3 台账、使用前需审计。
- 只读检查脚本：`scripts/check_comfy_kernel.py`。
  > **2026-09-10 演进**：该 PoC 脚本自 `a8f8472` 起不再被任何 CI 步骤调用（它在该提交前
  > "除目录缺失外恒 return 0"，属装饰性门禁）。内核的 CI 守卫现由
  > `scripts/comfy_kernel_baseline.py`（一级目录摘要漂移基线，test.yml `comfy-kernel-guard`
  > job）承担；脚本本身保留为不依赖 GPU/权重的手工 `import comfy` 探测工具。

# 实施影响

- 许可证：GPL-3.0 内核对分发（再分发）传染；商用场景须评估隔离或换 Apache-2.0 等价实现（计为合规待办）。
- 攻击面：comfy 节点代码与主进程同权限；切换到非 comfy 后端时不加载内核（缩小攻击面）。

# 可回滚路径与待验证项

- 回滚：切换推理后端为 `diffusers`（`MMH3_INFERENCE_BACKEND=diffusers`，或运行时持久化选择），
  此时 comfy_kernel 不加载。注意这**不是**"默认配置"——默认已为 `comfy`（见上「决策」修订注）。
- 待验证：`scripts/check_comfy_kernel.py` 退出码 0；节点包版本与台账一致。
  > **2026-09-10 注**：该项的 CI 复核已由 `scripts/comfy_kernel_baseline.py --check`
  > 取代（见上「只读检查脚本」的 2026-09-10 演进注记）。
