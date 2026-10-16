# ADR 0005：comfy B 方案 CI 覆盖的最小成本方案

- **状态**：Implemented（守卫 job 已接入 test.yml；真机链路归 gpu-smoke.yml）
- **日期**：2026-09-06
- **决策者**：仓库所有者（全权委托执行）
- **来源**：MLOps 评估提示词 v2.3.2 §2.5 / §4⑥ / 必答一问

---

## 背景

`comfy_kernel/` 为 vendored 上游 ComfyUI 内核（1724 个 .py / ~50 万行），被 `.gitignore:128`
排除、不入库。GitHub 托管 runner 的 checkout 天然没有该目录 → **B 方案（`COMFY_ENABLE=true`
进程内复用内核）在 CI 中零覆盖**。但需澄清覆盖的三层：

1. **适配器代码**（`backend/routers/comfy_engine.py` 的工作流映射 / 参数注入 / 假节点剔除）：
   **已有单测覆盖**（`tests/test_comfy_engine.py` + `test_comfy_engine_integration.py`，
   纯标准库 + pytest，不依赖内核），CI 的 python-test job 常态执行 —— 这层并非零覆盖。
2. **内核集成面**（`import comfy` 可行性 / 内核版本 / 暴露面 / 自定义节点 vendor 状态）：
   零覆盖，且只有内核在场的机器能检。
3. **真机全链路**（真实权重 + GPU 进程内推理）：零覆盖，且成本最高。

## 备选方案

| 方案 | 内容 | 结论 |
|---|---|---|
| A. 子模块 / subtree 化 | 把 `comfy_kernel/` 纳入版本控制 | **否决**。3558 文件入库膨胀仓库；GOTCHAS #19 记录过对内核源码的本地改（`nodes.py` 摘除两个 extras），入库后与上游 diff 会丢失可更新性；AGENTS 禁区 + ADR-0002 明确要求保留 vendored 形态 |
| B. CI 内 slim 拉取 | CI checkout 后按 pinned commit 从上游拉取内核子集 | **否决**。上游无官方固定 release（需 pin commit + 长期维护 pin）；拉取全量源码 ~50 万行拖慢 CI；GPL-3.0 再分发边界需额外合规动作（内核只读评估已提示"进程内复用需隔离边界"） |
| **C. 条件式守卫（采纳）** | CI 步骤级检测内核在场性：在场→跑只读评估 + 棘轮 + 适配器测试；不在场→步骤级 SKIP（日志可见，非吞错） | **采纳**。零额外基建、托管 runner 不飘红、有内核的机器（本机 / 自托管）自动获得实检；真机 GPU 链路归 gpu-smoke.yml 同条件扩展 |

## 决策（方案 C 落地）

- `test.yml` 新增 `comfy-kernel-guard` job：
  - 内核在场判定（步骤级 `if`，用输出传递而非 job 级 `hashFiles`，避免条件上下文歧义）；
  - 在场 → `python scripts/check_comfy_kernel.py .`（只读：结构 / 版本 / 许可 / vendor）+
    `--listen` 回退行棘轮复检 + comfy 适配器单测（`pip install pytest` 级轻依赖，不拉 torch）；
    > **2026-09-10 演进**：上述"内核只读评估"步骤已由
    > `python scripts/comfy_kernel_baseline.py --check`（漂移基线守卫）取代 ——
    > 原 PoC 脚本 `main()` 除目录缺失外恒 return 0，属装饰性门禁，无法真正让 CI 变红；
    > 新守卫在 `test.yml` `comfy-kernel-guard` job 内以三态判定（基线缺失=FAIL /
    > 内核缺失=SKIP / 摘要不符=FAIL）。
  - 不在场 → 明确打印 SKIP 及原因。
- **棘轮双闸不变**：本机 `precheck.ps1`（push 钩子必经）仍是 `--listen` 棘轮的实强制层。
- 真机 GPU B 方案链路：后续在 `gpu-smoke.yml` 追加同条件 job 复用 `scripts/smoke_comfy.py`
  （self-hosted runner 本机具备内核与权重；本期未实施，留待 runner 上权重就位后启用）。

## 影响

- 正面：B 方案 CI 覆盖从"零"变为"分层覆盖"——适配器（常态）+ 内核集成面（有内核机器）+
  真机（gpu-smoke 扩展点）；托管 runner 零成本不飘红。
- 代价：托管 runner 上"内核集成面"永远是 SKIP——这是 vendored 不入库的固有代价，
  由本机 push 前钩子补偿；若未来该缺口不可接受， revisit 方案 A/B。

## 证据等级申报（2026-10-16 harness 修复新增）

> 解决的问题：本 ADR 记录了"哪一层没被覆盖"，但没有规定"改动 comfy 引擎时怎样才算拿到过证据"。
> 结果是改 `backend/routers/comfy_engine.py` / `backend/routers/queue_manager.py` 的人（含 agent）
> 可以把"CI 全绿"误读成"引擎行为已验证"。本节把申报动作本身变成交付要求。

三层证据与各自的**实际**执行入口（引用路径均已核对存在）：

| 层 | 覆盖对象 | 执行入口 | 可移植环境（托管 CI / 干净检出）能否拿到 |
|---|---|---|---|
| L1 适配器 | `comfy_engine.py` 的工作流映射 / 参数注入 / 假节点剔除 | `python -m pytest tests/test_comfy_engine.py tests/test_comfy_engine_integration.py --no-cov -q` | 能（纯标准库、不依赖内核；`test.yml` 的 comfy-kernel-guard 在内核在场分支执行） |
| L2 内核集成面 | `import comfy` 可行性 / 内核版本 / vendor 漂移 | `python scripts/comfy_kernel_baseline.py --check` | 不能。内核不入库 → `present=false` → 步骤级 SKIP，由 `kernel-guard-status` 的 job 名显式申报"未执行" |
| L3 真机 comfy 推理 | 真实权重 + GPU 进程内 comfy 出片 | `python scripts/smoke_comfy.py`（本机手动，需内核与权重就位） | 不能。`gpu-smoke.yml` 复用 `scripts/smoke_real.py`（diffusers 路径），**不含 comfy 链路**；其 `schedule`（每周一 03:00 UTC）与 `workflow_dispatch` 都跑在 self-hosted `gpu` runner 上 |

申报规则：

1. 改动 comfy 引擎相关代码后，交付说明必须写明取得的是哪一层证据（L1 / L1+L2 / L1+L2+L3）。
2. 只有 L1 时，必须显式写「内核集成面与真机 comfy 链路证据等级 = 无」，不得以 CI 绿色代替。
3. 不得把 L3 写成 CI 已覆盖：本仓不存在任何自动执行 `scripts/smoke_comfy.py` 的作业（2026-10-16 实测：`grep -rn smoke_comfy .github/workflows/` 仅命中 `test.yml` 的注释，无调用点）。
4. L2/L3 的缺失是 vendored + GPL 许可边界的固有代价，不是待补的缺陷；本规则只约束**表述**。
