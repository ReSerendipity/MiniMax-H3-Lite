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
- **方案 B：内嵌 `comfy_kernel/` 进程内复用** —— 开箱即用（`INFERENCE_BACKEND="comfy"`），但引入 GPL-3.0 传染风险。**采用**（B 方案，`comfy_kernel/` 随仓内嵌）。

# 决策

- 默认推理后端：`diffusers`（不加载 comfy_kernel）；需要工作流投递时 `INFERENCE_BACKEND="comfy"` 启用内嵌内核。
- `comfy_kernel/custom_nodes/` 随仓携带 **17 个第三方节点包**（除 `__pycache__` 外），各自许可证见许可证台账、使用前需审计（见 SECURITY.md §四与 D6 台账）。
- 只读检查脚本：`scripts/check_comfy_kernel.py`。

# 实施影响

- 许可证：GPL-3.0 内核对分发（再分发）传染；商用场景须评估隔离或换 Apache-2.0 等价实现（计为合规待办）。
- 攻击面：comfy 节点代码与主进程同权限，未启用时不被加载（默认 diffusers 后端缩小攻击面）。

# 可回滚路径与待验证项

- 回滚：回到纯 diffusers 后端（默认配置），comfy_kernel 不加载。
- 待验证：`scripts/check_comfy_kernel.py` 退出码 0；节点包版本与台账一致。
