# SRE 运行手册（日志落点 / 勘误指引 / 事件响应）

> 2026-09-18 建立：补齐家族统一的日志落点文档（勘误用）。
> 2026-10-06 扩写：事件响应 playbook（安全合规落地 P1-4）。

## 日志落点（勘误用）

| 用途 | 位置 | 说明 |
|------|------|------|
| 后端服务日志 | `logs/backend.log` | RotatingFileHandler 5MB×5 滚动 |
| mypy 扫描日志 | `_archive/logs/mypy_scan.log` | 扫描任务留档 |
| Docker 容器日志 | `docker compose logs mmh3` | json-file 10MB×3 |
| 完整性自检日志 | `logs/backend.log` 中 `[SELF-CHECK]` / `[SECURITY]` 前缀 | 启动时 fail-closed 拒绝启动会打 ERROR |
| 崩溃栈（faulthandler） | `logs/backend_faults.log` | 进程级致命崩溃（含原生层）栈落盘（append）；Python 层异常仍在 backend.log |

> 勘误优先看 `logs/backend.log` 尾部；mypy 基线扫描结果在 `_archive/logs/mypy_scan.log`。

## 事件分级与响应 playbook（2026-10-06 补）

> 本仓为单人维护的本地单机工具，以下 playbook 为维护者自约束；发生事件时按以下顺序处置。

### P0 — Critical（需立即处置）
**触发条件**：
- 完整性自检失败（`[SECURITY] 核心模块完整性校验失败`）→ 可能被篡改
- Ed25519 验签失败 → 清单或公钥被替换
- 磁盘上 `data/.manifest_signing_key` / `.watermark_key` 文件丢失或泄露
- GPU 推理进程失控（占满显存/磁盘）

**响应步骤**：
1. 立即停止服务（`Ctrl+C` 或 `docker compose down`）；
2. 备份 `data/mmh3.db`、`uploads/`、`outputs/`（事件现场，不清理）；
3. 完整性问题：`python scripts/diag_integrity.py` 诊断；对照 `git status` 确认是否有非本人改动；
4. 密钥问题：**不要**在未确认公钥配套前重签清单；记录事件时间线，待人工决策；
5. 恢复：从干净 checkout 重新部署（`git stash` 在制品后 `git checkout .`），重算清单并重签（需签发机私钥）。
6. 需外发排障时：`python scripts/diag_bundle.py` 生成诊断包（logs + 版本 + 设置摘要 → diagnostics/*.zip；本地打包不上传，外发前人工脱敏）。

### P1 — High（24 小时内处置）
**触发条件**：
- Trivy/pip-audit 报告新 HIGH/CRITICAL CVE
- CI 红（security-scan / security-assertions / integrity-freshness job 失败）
- Docker 容器反复重启（healthcheck 失败）
- 上传/生成产物异常（路径遍历尝试、异常大文件）

**响应步骤**：
1. `gh run view` 看 CI 失败日志；
2. CVE：Dependabot PR 自动升级，或手动 `pip install` 修复版本后重算 `requirements-lock.txt`；
3. healthcheck：`docker compose logs mmh3 --tail=100` 看启动报错；模型未加载是常态（惰性加载），非真故障；
4. 产物异常：检查 `uploads/` 文件列表，确认无路径遍历产物（`../` 前缀文件名）。

### P2 — Medium（随版本处置）
**触发条件**：
- 日志中有 WARN/ERROR 但服务正常
- mypy/flake8 新增告警
- 磁盘空间增长异常（outputs/ 或 logs/）

**响应步骤**：
1. `logs/backend.log` grep ERROR/WARN；
2. `scripts/ops.py status` / `health` / `backup` 查看运行状态；
3. 磁盘：`docker compose exec mmh3 du -sh /app/*` 或本地 `Get-ChildItem`；prune 旧 outputs。

### 事件后复盘
- 在 `docs/SECURITY_REMEDIATION_TRACKER.md` 追加一行（事件编号 / 时间 / 根因 / 处置 / 遗留项）；
- 若暴露了新攻击面，更新 `.github/SECURITY_MATRIX.md` R 矩阵；
- 不公开披露细节，由报告者决定是否公开。

## 常见故障速查

| 症状 | 首查位置 | 典型根因 |
|---|---|---|
| 启动即退出 `RuntimeError: 完整性自检失败` | `logs/backend.log` | 改了 backend/*.py 但未重算清单；从干净 checkout 重跑 generate+sign |
| 启动即退出 `MMH3_HOST 必须为回环地址` | `logs/backend.log` | 环境变量 MMH3_HOST 被改为非回环；改回 127.0.0.1 |
| 页面 502 / 连接拒绝 | `docker compose ps` | 容器未启动或模型加载中（start-period 300s） |
| GPU OOM | `nvidia-smi` | 并发数>1 或分辨率过高；MMH3_MAX_CONCURRENCY=1 |
| CI security-scan 红 | `gh run view` | pip-audit/npm audit 新漏洞超基线；`python scripts/security_gate.py` 看详情 |
