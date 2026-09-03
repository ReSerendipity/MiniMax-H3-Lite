# MiniMax-H3-lite 许可证合规台账（License Compliance）

> 最后更新：2026-09-03（§3.4 四项未决收口：节点包 LICENSE 实测复核 + Image/MiniMax 不对称说明；节点包实测 19 个）。
> 本台账覆盖**随仓内嵌/随包分发**的组件；Python 依赖以 `pyproject.toml` 为准，另行核查。
> ⚠️「商用合规 / 合规要求」两列仅记录**事实与风险提示**，不构成法律意见；标「需人工确认」者必须逐项人工补查后再分发。

## 1. 主程序许可

| 组件 | 许可证 | 商用合规 | 合规要求 |
|---|---|---|---|
| MiniMax-H3-lite 项目代码 | Apache-2.0（以根级 LICENSE 为准） | 宽松许可 | 保留版权声明与 NOTICE |

## 2. 内嵌 ComfyUI 内核（B 方案进程内复用）

| 组件 | 许可证 | 商用合规 | 合规要求 |
|---|---|---|---|
| `comfy_kernel/`（上游 ComfyUI 内核） | GPL-3.0 | ⚠️ 传染风险（进程内复用）；具体分发形态需人工评估 | 隔离进程边界，或改用 Apache-2.0 等价实现；保留上游版权与许可文本 |

## 3. `comfy_kernel/custom_nodes/` 第三方节点包（19 个，除 `__pycache__` 外）

> §3.4 四项未决收口记录（2026-09-03，LICENSE 文件实测复核）：
> ① `ComfyUI_Dynamic-RAMCache` 原记 **NOT FOUND** 实为「**目录存在但无 LICENSE 文件**」（默认保留所有权利，无明确授权）→ 须核实上游许可或移除；
> ② 9 个 GPL-3.0 节点 LICENSE 首行均实测为 `GNU GENERAL PUBLIC LICENSE`，**传染风险成立**；
> ③ `ComfyUI-EsesImageCompare` 许可实测为 `"My ComfyUI Nodes License" (1.0)`，**明确禁止 Bundling / Code Reuse / 再分发**，**当前 vendor 进仓即违反许可**；
> ④ Image vs MiniMax 不对称：Image `comfy_kernel/custom_nodes/` 仅 2 个示例节点（业务节点在 `app/integrated_app/native/`），MiniMax vendor 19 个 → 为架构差异非缺陷，MiniMax 侧须按本台账逐包复核。

| 组件 | 许可证 | 商用合规 | 合规要求 |
|---|---|---|---|
| comfyui_controlnet_aux | Apache-2.0（LICENSE 首行） | ✅ 已核实 2026-09-03 | 保留版权声明 |
| ComfyUI_Dynamic-RAMCache | **无 LICENSE 文件**（默认保留所有权利） | ⚠️ 需人工确认上游许可 | **当前 vendor 进仓无明确授权；须核实上游许可或移除**（原 §3.4 误记 NOT FOUND，实为 LICENSE 缺失） |
| ComfyUI_IPAdapter_plus | GPL-3.0（LICENSE 实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 隔离进程边界/改用 Apache 等价实现；保留上游版权 |
| ComfyUI_toyxyz_test_nodes | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 同上 |
| ComfyUI_UltimateSDUpscale | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 同上 |
| ComfyUI-EsesImageCompare | "My ComfyUI Nodes License" (1.0)（LICENSE.txt 实测） | 🚫 **禁止 Bundling/Code Reuse/再分发**（仅 quasiblob 原仓分发） | ⚠️ **当前 vendor 进仓违反许可**：须移除该节点，或获作者书面授权后仅作外部安装（不从本仓分发） |
| ComfyUI-GGUF | Apache-2.0（LICENSE 首行） | ✅ 已核实 2026-09-03 | 保留版权声明 |
| ComfyUI-Impact-Pack | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 隔离/改用 Apache 等价 |
| ComfyUI-Inspire-Pack | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 同上 |
| ComfyUI-KJNodes | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 同上 |
| ComfyUI-Manager | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 同上 |
| ComfyUI-ReservedVRAM | Apache-2.0（LICENSE 首行） | ✅ 已核实 2026-09-03 | 保留版权声明 |
| ComfyUI-RMBG | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 隔离/改用 Apache 等价 |
| ComfyUI-SeedVR2_VideoUpscaler | Apache-2.0（LICENSE 首行） | ✅ 已核实 2026-09-03 | 保留版权声明 |
| ComfyUI-VideoHelperSuite | GPL-3.0（实测） | ⚠️ 已核实 GPL-3.0（2026-09-03），传染风险 | 隔离/改用 Apache 等价 |
| ComfyUI-WanVideoWrapper | Apache-2.0（LICENSE 首行） | ✅ 已核实 2026-09-03 | 保留版权声明 |
| rgthree-comfy | MIT（LICENSE 首行） | ✅ 已核实 2026-09-03 | 保留版权声明 |

## 4. 模型权重

| 组件 | 许可证 | 商用合规 | 合规要求 |
|---|---|---|---|
| MiniMax H3 权重（`model/`，下载获得） | 以官方仓库/ModelScope 条款为准 | 需人工确认 | 权重许可独立于代码许可，商用前单独核对 |

## 5. 维护约定

- 新增/升级任何第三方节点包，**必须**同步更新本台账并标「需人工确认」直至人工核实。
- 生成命令（只读复核）：`Get-ChildItem comfy_kernel/custom_nodes -Directory | Where-Object Name -ne '__pycache__'`