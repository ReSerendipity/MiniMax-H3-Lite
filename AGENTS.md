# MiniMax-H3-lite AGENTS.md — AI 辅助开发指南

> 🧬 **自进化协议版本**：v0.1
> 📅 **最后更新日期**：2026-08-17
> 🎯 **对应项目版本**：v0.1.0（Apache-2.0 开源协议）

---

## ⚠️ 🤖 Agent 行为契约（自进化协议 · 必须严格遵守）

AI Agent 打开本文件后的 **第一件事** 是执行下面的「🧪 自进化自检清单」，并遵守以下 5 条铁律：

### 🔴 5 条自进化铁律
1. **🔄 同步规则（Synchronize First）**：如果发现项目实际情况（目录结构、依赖版本、技术栈、配置文件名、端口等）与本文件描述 **不一致** → **立即更新本文件**，不要只改代码不改 AGENTS.md。这是最高优先级的规则。
2. **📝 坑点累积（Gotchas Accumulation）**：每次修复 Bug / 踩坑后（哪怕是很小的坑），**必须** 追加一条到第 8 节「常见陷阱（Known Gotchas）」，写清楚：触发场景、现象/报错、正确做法、首次发现日期。
3. **📚 SOP 累积（SOP Accumulation）**：每次完成一个「本文件现有 SOP 没覆盖」的典型开发任务后，**必须** 把步骤整理成新 SOP 追加到第 9 节「典型 AI 开发场景 SOP」。
4. **✅ 自检流程（Self-Check on Startup）**：每次打开本文件准备工作前，**必须** 先运行下面的「🧪 自进化自检清单」，逐项核对，有任何一项不符先修正 AGENTS.md 再干活。
5. **🏷️ 版本递增（Version Increment）**：每次更新本文件内容后，**必须** 做三件事：① 文件顶部「自进化协议版本号」+0.1（小改）或 +1.0（大改/框架调整）；② 更新「最后更新日期」；③ 在文件末尾「📋 自进化修订记录表」追加一行记录。

### 🧪 自进化自检清单（每次启动工作前必跑）
- [ ] 目录结构（`backend/`、`bin/`、`scripts/`、`tests/`、`workflows/`）是否和第 3 节模块边界描述一致？
- [ ] 单端口 18080 与 `backend/config.py → PORT` 是否一致（有无被改成其他端口）？
- [ ] 六个 `/api/*` 路由（projects / shots / generations / uploads / history / system）是否和 `backend/main.py` 的 include_router 列表一致？
- [ ] 上次工作是否踩了新坑？如果是，是否已追加到第 8 节 Known Gotchas？
- [ ] 上次更新是否正确递增了自进化协议版本号 + 追加了修订记录表？
- [ ] `requirements-lock.txt` 是否随 `requirements.txt` 的变更一并更新（pip-compile 或环境快照）？

---

## 1. 项目概览

> **MiniMax-H3-lite**：MiniMax H3 视频生成时间线工作台（轻量 Web 壳）。
> 定位：面向 MiniMax H3 视频生成的三模式页面（T2V / I2V / R2V）+ 多项目 / 分镜时间线 + 历史库 + 上传校验，后端 FastAPI 单端口直出页面与 API。
> 核心特色：**单端口 18080**（Jinja2 页面 + `/api` + `/assets` + `/uploads` 统一由 FastAPI 提供）+ 三模式页面 + 项目/分镜管理 + 上传三校验（数量 / 大小 / 类型）。
> 开源协议：**Apache-2.0**
> 技术栈：**Python 3.10+（推荐 3.12）+ FastAPI + Uvicorn + Pydantic v2 + Jinja2 + SQLite（stdlib）+ diffusers（真实推理）**
> 代码入口：`bin/clean_launch.py`（推荐，自动选 CUDA Python + 启动 uvicorn，端口被占用自动向上顺延）
> 后端 Uvicorn 入口：`python -m uvicorn backend.main:app --host 127.0.0.1 --port 18080`
> 默认端口：**`http://127.0.0.1:18080`**（被占用时自动顺延，见第 8 节陷阱）
> 依赖管理：`requirements.txt`（生产）+ `requirements-lock.txt`（锁定）+ `package.json` / `package-lock.json`（前端测试）

---

## 2. 代码风格 & 格式约定

- **命名规则**：类/异常 `PascalCase`，函数/方法/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`，模块 `snake_case.py`。
- **Ruff / Black / Mypy**：如 `pyproject.toml` 配置存在则遵循；无配置时遵循 PEP 8 + 100 列。
- **import 顺序**：stdlib → 第三方 → 本地项目（`from config import settings`、`from routers import ...`）。
- **public 函数**：加 Google 风格 docstring（Args / Returns / Raises）。
- 后端代码不拼 HTML/JS 字符串；页面统一用 `backend/templates/*.html`（Jinja2）。

---

## 3. 模块边界 & 关键规则（🚫 跨层引用严格禁止）

```
MiniMax-H3-lite/
├── backend/               ← FastAPI 后端（单端口直出页面 + API）
│   ├── main.py            ← app（FastAPI 实例）、页面路由、include_router 注册
│   ├── config.py          ← Settings（dataclass）：路径 / 端口 / 采样默认值 / 上传校验 / 环境变量覆盖（MMH3_*）
│   ├── database.py        ← init_db()：SQLite（stdlib）
│   ├── engine_registry.py ← active_backend() / list_engines()：推理后端注册
│   ├── settings_store.py  ← 设置持久化（读写存储的配置项）
│   ├── watermark.py       ← 内容来源标识 / 不可见水印模块
│   ├── h3/
│   │   └── spec.py        ← MiniMax H3 官方模型名 / 采样默认值的单一事实来源（MODELS / SAMPLER_NAME / SCHEDULER / STEPS / DENOISE …）
│   ├── routers/           ← /api/* 路由：projects / shots / generations / uploads / history / system / _queue_manager
│   │   ├── projects.py    ← 项目列表 CRUD
│   │   ├── shots.py       ← 分镜（时间线）管理
│   │   ├── generations.py ← 任务提交 / 队列（queue_manager.enqueue）
│   │   ├── inference.py   ← 推理（diffusers / comfy workflow 参数构建）
│   │   ├── uploads.py     ← 上传（数量 / 大小 / 类型三校验）
│   │   ├── history.py     ← 历史库
│   │   ├── system.py      ← 系统信息 / 引擎列表
│   │   └── queue_manager.py ← 任务队列管理
│   └── templates/         ← Jinja2 页面：base / t2v / i2v / r2v + partials
├── bin/
│   ├── clean_launch.py    ← 启动入口（选 CUDA Python + 校验依赖 + 端口顺延 + uvicorn + 自动开浏览器）
│   └── render_pages.py    ← 把三页面模板渲染到 tests/frontend/_rendered/（供前端 smoke 测试读取）
├── assets/                ← 前端静态资源（css / js / favicon）
├── workflows/             ← 官方推理工作流 JSON（video_minimax_h3_{t2v,i2v,r2v}.json）
├── scripts/               ← smoke_real.py / verify_watermark.py
├── tests/                 ← pytest（test_api_smoke / test_h3_spec_consistency / test_performance …）+ Playwright 前端冒烟
├── requirements.txt        ← 生产依赖
├── requirements-lock.txt   ← 锁定依赖版本
├── pytest.ini              ← pytest 配置
├── package.json            ← 前端测试依赖（Playwright）
└── start.bat               ← Windows 一键（→ bin/clean_launch.py）
```

### 🔴 关键约束
1. **`backend/h3/spec.py` 是官方参数唯一事实来源**：模型文件名、采样默认值（sampler / scheduler / steps / denoise）只能在此定义，`config.py` 通过 `h3.spec` 导入，`_build_params` / `comfy_workflow` / diffusers 均消费 spec，禁止在别处另写一套。
2. **单端口直出**：页面（`/`、`/i2v`、`/r2v`）与 `/api`、`/assets`、`/uploads` 统一由一个 FastAPI 进程提供，不要新增第二端口服务。
3. **路由不做业务推理**：路由负责参数校验 + 调 `engine_registry` / 队列 / 数据库 + 返回；`inference.py` 专门负责推理参数构建。
4. **上传三校验**：`uploads.py` 必须做数量（`MAX_IMAGE/VIDEO/AUDIO_COUNT`）、大小（`MAX_UPLOAD_SIZE_MB`）、类型（扩展名 + 魔数）三重校验，不能只看扩展名。
5. **只监听 `127.0.0.1`**：距离绑 `host="127.0.0.1"`，外网访问必须套反代（HTTPS + 鉴权），见第 8 节陷阱。

---

## 4. 启动命令

### 4.1 一键启动（推荐）
- **Windows**：双击 `start.bat` → 自动检测系统 Python / 兄弟项目 WinPython → 启动 `bin/clean_launch.py` → 自动打开浏览器。

### 4.2 手动启动
```bash
# 方式 A（推荐，含 CUDA Python 切换 + 依赖校验 + 端口顺延）
python bin/clean_launch.py
# → 默认 http://127.0.0.1:18080（被占用则自动向上顺延）

# 方式 B（纯 Uvicorn，调试用）
python -m uvicorn backend.main:app --host 127.0.0.1 --port 18080 --reload
# ⚠️ --reload 仅限开发；生产禁用（会重复加载模型 / 端口冲突）
```

### 4.3 启动后验证
- `GET http://127.0.0.1:18080/api/health` → 返回 `{"status":"ok","engine":"MiniMax H3","model":...,"backend":...,"max_concurrency":...}` 即启动成功。
- 浏览器打开 `/`（T2V）、`/i2v`、`/r2v` 确认三页面可渲染。

---

## 5. 配置与环境变量覆盖

`backend/config.py → Settings` 为统一配置中心，支持环境变量覆盖（优先级最高）：
| 环境变量 | 覆盖字段 | 说明 |
|---------|---------|------|
| `MMH3_HOST` | HOST | 监听地址（保持 127.0.0.1） |
| `MMH3_PORT` | PORT | 起始端口（默认 18080） |
| `MMH3_MODEL_PATH` | MODEL_PATH | 本地权重路径，空则从 HF / 魔搭拉取 |
| `MMH3_INFERENCE_BACKEND` | INFERENCE_BACKEND | 默认 `diffusers` |
| `MMH3_QUANTIZATION` | QUANTIZATION | `bf16 / int8 / int4 / gguf-q4_k_m` |
| `MMH3_MAX_CONCURRENCY` | MAX_CONCURRENCY | 单机默认串行（1） |
| `MMH3_MODEL_*` | MODEL_FL2VA / REF2VA / CLIP / VAE_VIDEO / VAE_AUDIO | 官方模型文件名覆盖 |

> 上传限制（`MAX_IMAGE_COUNT=9` / `MAX_VIDEO_COUNT=3` / `MAX_AUDIO_COUNT=3` / `MAX_TOTAL_REFS=12` / `MAX_UPLOAD_SIZE_MB=200`）与模型规格（`SUPPORTED_RATIOS` / `SUPPORTED_DURATIONS=[4,8,10,15]` / `SUPPORTED_RESOLUTIONS=["768P","2K"]` / `MAX_PROMPT_CHARS=7000`）均可在 `backend/config.py` 调整。

---

## 6. 测试约定

- pytest 配置在 `pytest.ini`，测试文件在 `tests/`（`test_api_smoke.py` / `test_h3_spec_consistency.py` / `test_gaps_uploads.py` / `test_build_params.py` / `test_performance.py`）。
- 前端冒烟：`tests/frontend/smoke.js` 读取 `tests/frontend/_rendered/*.html`（由 `bin/render_pages.py` 生成）；Playwright 配置在 `tests/playwright.config.js` + `tests/e2e`。
- 命名规范：类 `Test<被测类>`，方法 `test_<场景>_<期望>_<条件>`；**严禁 `assert True` 凑覆盖率**。
- 依赖完整性：`test_h3_spec_consistency.py` 保证 `h3/spec.py` 与 workflows JSON 默认值一致，改了任意一边记得跑它。

---

## 7. Git 提交规范 & CI

### 7.1 Conventional Commits
```
<type>(<scope>): <subject>
```
Type：`feat` / `fix` / `docs` / `refactor` / `perf` / `test` / `chore` / `ci`
Scope 建议：`backend` / `routers` / `inference` / `i2v` / `r2v` / `t2v` / `uploads` / `i18n` / `ci`

### 7.2 CI（`.github/workflows/test.yml`）
- 触发：push 到 main / PR
- 关键检查：依赖锁存在性（`requirements-lock.txt` 必须存在）+ 基础冒烟。

### 7.3 依赖更新流程
1. 改 `requirements.txt` 后，重新生成锁：
   ```bash
   python -m piptools compile requirements.txt -o requirements-lock.txt
   ```
2. 提交 `requirements.txt` + `requirements-lock.txt` 一起提交，不要只改一个。

---

## 8. 常见陷阱（Known Gotchas）

| # | 坑点标题 | 触发场景 | 现象/报错 | 正确做法 | 首次发现日期 |
|---|---------|---------|---------|---------|------------|
| 1 | **端口被占用自动顺延，URL 不再是 18080** | 18080 被其他进程占用后运行 `bin/clean_launch.py` | 启动日志提示"后端端口 18080 已被占用，自动切换到 1808X"，浏览器打开的是新端口 | `clean_launch.py` 的 `find_available_port()` 会从起始端口向上探测；若手动打开 18080 没反应，看启动日志里的实际端口，或 `MMH3_PORT` 指定其它起始位 | 2026-08-17 |
| 2 | **`bin/clean_launch.py` 会 `os.execv` 重启为 CUDA Python** | 当前 Python 与 `find_winpython()` 找到的 CUDA 环境不是同一个 | 进程会看似"退出又起来一次"，日志里有 `[INFO] Relaunching with CUDA Python: ...` | 这是有意的（保证用带 CUDA 的 Python 跑 diffusers）；不是崩溃，别 kill。离线环境禁用下载时靠 `HF_HUB_OFFLINE=1` 等环境变量兜底 | 2026-08-17 |
| 3 | **`tests/frontend/_rendered/*.html` 是渲染产物，易被误提交** | `bin/render_pages.py` 把三页面模板渲染成 HTML 供前端冒烟 | 生成物进 git，渲染逻辑变更后前三页快照与模板漂移 | 该目录是构建产物：确认是否应加入 `.gitignore`（`tests/frontend/_rendered/`）；真需要快照对比就让 CI 生成而非手工提交 | 2026-08-17 |
| 4 | **单端口直出，模板路径必须在 `backend/templates/`** | 新增页面时把 `.html` 放到别处 | `Jinja2Templates(directory=...)` 找不到模板 → 页面 404 / TemplateNotFound | 页面模板统一放 `backend/templates/`，在 `backend/main.py` 加页面路由（`templates.TemplateResponse(request, "xxx.html")`），不要在 Python 里手拼 HTML | 2026-08-17 |

---

## 9. 典型 AI 开发场景 SOP

#### SOP-1: 新增一个 /api 子路由
1. `backend/routers/` 新建 `xxx.py`，定义 `router = APIRouter(prefix="/xxx", tags=["xxx"])`（前缀唯一，避免与现有前缀冲突）。
2. 在 `backend/main.py` 的 import 区加入 `from routers import xxx`，并 `app.include_router(xxx.router, prefix="/api", tags=["xxx"])`（**注意：本仓库是手动 include_router，不是自动扫描**）。
3. 需要写库走 `backend/database.py` / SQLite；需要推理参数走 `inference.py`。
4. 在 `tests/` 补对应 pytest；`GET /api/health` 确认不影响既有路由。
5. 按第 5 节核对是否需新增配置 / 环境变量。

#### SOP-2: 修改官方模型参数 / 工作流
1. **统一改 `backend/h3/spec.py`**（模型文件名 / 采样默认值），不要改 workflows JSON 里的值（会不一致）。
2. 若确需改 workflows JSON，则同步改 `h3/spec.py`，并跑 `pytest tests/test_h3_spec_consistency.py` 确认一致。
3. 重新生成 `requirements-lock.txt`（若涉及依赖）。

#### SOP-3: Debug 一个端口顺延 / 启动问题
1. 先看 `bin/clean_launch.py` 打印的 `[INFO] 后端启动中: http://127.0.0.1:<port>`，确认实际端口。
2. 看是否有 `[INFO] Relaunching with CUDA Python`（属于正常的 Python 切换）。
3. `python -m uvicorn backend.main:app --host 127.0.0.1 --port 18080` 前台直跑，能看到真实 traceback。

---

## 📋 自进化修订记录表（AGENTS.md 进化史）

| 自进化版本 | 日期 | 触发原因 | 更新内容摘要 | 对应项目版本 |
|:---------:|------|---------|------------|:------------:|
| v0.1 | 2026-08-17 | 初始建立自进化协议（对齐家族 TTS/Image/SeedVR2 约定） | 建立自进化协议（5 条铁律 + 自检清单）；项目概览（MM·H3 三模式视频工作台，单端口 18080）；模块边界（backend/main.py + h3/spec.py 单一事实来源 + 6 个 /api 路由）；启动命令（bin/clean_launch.py + 端口顺延 + CUDA Python 切换）；配置与环境变量（MMH3_*）；测试约定；Known Gotchas（端口顺延 / execv 重启 / _rendered 产物 / 模板路径）；SOP-1~3 | v0.1.0 |

<!-- 🔄 下次更新 AGENTS.md 时，在上面表格末尾追加新一行，不要删除历史记录 -->