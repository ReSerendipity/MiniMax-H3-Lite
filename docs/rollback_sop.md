# 回滚 SOP（Rollback Standard Operating Procedure）

> 建立：2026-10-15（v2.9 修复批次，运维稳定性评估 P1-3：backend/database.py 两处引用本文件而文件此前不存在——悬空引用修复）。
> 适用范围：本仓（MM·H3 工作台）本地单机部署形态（裸机 uvicorn / Docker compose / 桌面壳 NSIS）。

## 1. 回滚总原则

- 先备份后动手：任何回滚动作前，先用 `python scripts/backup_data.py --dest <仓外目录>` 备份 data/（含 mmh3.db、settings.json、checkpoints）。
- 回滚点：git tag（发版与修复批次均打 tag；修复回滚点示例 `v29-remediate-start` / `v29-p1-N`）。
- 完整性自检 fail-closed：更换代码后 `INTEGRITY_ENFORCE=True`（默认）会在启动时校验 integrity_manifest + Ed25519 签名（backend/security/integrity_selfcheck.py），代码与清单不一致**直接拒启**。因此每次代码回滚后必须重算并重签清单：

  ```bat
  python scripts/generate_integrity_manifest.py
  python scripts/sign_integrity_manifest.py
  ```

  （重签需签发机 `data/.manifest_signing_key`；CI 侧对应 test.yml 的 integrity-freshness 与 security-scan 验签两道门。）

## 2. 坏版本回退（应用 / 安装包 / 镜像）

- 桌面安装形态：从 GitHub Release 取上一版本资产（先对 SHA256SUMS.desktop 验哈希）重装；卸载保留数据（安装器弹问选"否"）。
- Docker 形态：把 compose 的 `image:` 改回上一 `X.Y.Z-cu130` 语义 tag，重跑 `pwsh scripts/build_and_pin.ps1` 生成 digest 固化覆盖层后 `docker compose -f docker-compose.yml -f docker-compose.pinned.yml up -d`。
- 源码形态：`git checkout <上一tag>` 后按 §1 重签清单再启动。
- 回退后验证：`GET /api/health` 返回 ok 且 `backend` 字段与预期引擎一致；`git status --short` 干净。

## 3. 数据回退（SQLite）

- data/mmh3.db 损坏或误清空：停服 → 取最近一份 `backup/<时间戳>/mmh3.db`（或仓外备份）→ 覆盖回 `data/mmh3.db` → 启动 → `/api/health` ok → 抽查一个项目/镜头历史与产物引用。
- WAL 伴生文件：覆盖旧库前先停服并删除 `mmh3.db-wal` / `mmh3.db-shm`（它们属于旧进程状态，与新覆盖库混用会造成数据不一致）。

## 4. 数据库 schema 回滚（backend/database.py 引用点）

代码基线：backend/database.py 的 `SCHEMA_VERSION` + `_MIGRATIONS`。守卫语义：

- 启动时 `PRAGMA user_version` 高于代码支持的 `SCHEMA_VERSION` → 直接 RuntimeError 拒启（防旧代码读写新结构导致静默损坏）。
- 迁移幂等：ALTER 报 duplicate column / already exists 时忽略，其余错误照常抛出。

回滚步骤（"新代码 + 已升级的库"回退到"旧代码"）：

1. 停服（Ctrl+C 或 `docker compose down`）。
2. 备份：`python scripts/backup_data.py --dest <仓外目录>`。
3. 读当前库版本：`python -c "import sqlite3; print(sqlite3.connect('data/mmh3.db').execute('PRAGMA user_version').fetchone()[0])"`。
4. 若 user_version 高于目标代码的 SCHEMA_VERSION，二选一：
   - **方案 A（推荐，字段级回退）**：对照 `_MIGRATIONS` 中该版本的迁移语句，在备份副本上手工回删对应列（如 `ALTER TABLE shot_refs DROP COLUMN pair_asset_id`，SQLite 3.35+ 支持），再 `PRAGMA user_version = <目标版本>`；校验后覆盖回 `data/`。
   - **方案 B（整库回退）**：直接用第 2 步备份中的旧库覆盖 `data/mmh3.db`（接受丢失升级窗口内的新数据——先与数据所有者确认）。
5. 切换代码到目标版本（`git checkout <tag>`）→ 按 §1 重算重签完整性清单 → 启动 → `/api/health` ok。
6. 留痕：把本次回滚的时间线与根因追加到 docs/SECURITY_REMEDIATION_TRACKER.md（安全相关）或仓外发版证据目录；演练留痕要求见 §5。

## 5. 回滚/恢复演练留痕要求

- 每次发版（local/agents/RELEASE_PROFILE.md 阶段 4）收尾时，在既有「恢复备份并验证 git status 干净」之外，留一条**恢复验证记录**：时间戳、备份源路径、恢复目标、SHA256 对比结果、`/api/health` 结论、执行人。
- 记录位置：仓外发版证据目录（`<仓外>\_mmh3_release_evidence_<版本>\`）；模板示例见 v2.9 修复批次的《恢复演练记录》。
