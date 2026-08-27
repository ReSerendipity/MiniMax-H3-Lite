# MiniMax-H3-lite AGENTS.md — AI 辅助开发指南

> 🧬 **自进化协议版本**：v1.8
> 📅 **最后更新日期**：2026-08-27  
> 🎯 **对应项目版本**：v0.1.0（Apache-2.0 开源协议）

---

## 0. 文档优先级（单一事实来源）

当以下文档相互矛盾时，**以此顺序为准**，并立即按铁律 #1 修正靠后者：

1. 代码与配置本身（`pyproject.toml` / `package.json` / `.pre-commit-config.yaml` / 源码）
2. `docs/official_spec.md`（若本仓存在；当前本仓无此文件）
3. `AGENTS.md`
4. `README.md` / `docs/**`
5. `CHANGELOG.md`

> 判据：**能被机器验证的事实永远优先于自然语言描述。**

---

## ⚠️ 🤖 Agent 行为契约（自进化协议 · 必须严格遵守）

AI Agent 打开本文件后的**第一件事**是执行下面的「🧪 自进化自检清单」，并遵守以下 5 条铁律：

### 🔴 6 条自进化铁律
1. **🔄 同步规则（Synchronize First）**：如果发现项目实际情况（目录结构、依赖版本、技术栈、配置文件名、端口等）与本文件描述 **不一致** → **立即更新本文件**，不要只改代码不改 AGENTS.md。这是最高优先级的规则。
2. **📝 坑点累积（Gotchas Accumulation）**：每次修复 Bug / 踩坑后（哪怕是很小的坑），**必须** 追加一条到第 8 节「常见陷阱（Known Gotchas）」，写清楚：触发场景、现象/报错、正确做法、首次发现日期。
3. **📚 SOP 累积（SOP Accumulation）**：每次完成一个「本文件现有 SOP 没覆盖」的典型开发任务后，**必须** 把步骤整理成新 SOP 追加到第 9 节「典型 AI 开发场景 SOP」。
4. **✅ 自检流程（Self-Check on Startup）**：每次打开本文件准备工作前，**必须** 先运行下面的「🧪 自进化自检清单」，逐项核对，有任何一项不符先修正 AGENTS.md 再干活。
5. **🏷️ 版本递增（Version Increment）**：每次更新本文件内容后，**必须** 做三件事：① 文件顶部「自进化协议版本号」+0.1（小改）或 +1.0（大改/框架调整）；② 更新「最后更新日期」；③ 在文件末尾「📋 自进化修订记录表」追加一行记录。
6. **🔬 证据绑定（Evidence Binding）**：本文件中每出现一个**可执行文件路径**（脚本、配置、workflow、源码），它必须是**当时可验证存在**的。引用前跑一次 `python scripts/check_spec_refs.py`；若确实想描述尚未实现的东西，必须显式加 `（计划，未实现）` 前缀。禁止把"CI 会阻断 X"写成一个 CI 里不存在的门禁。

### 🧪 自进化自检清单（每次启动工作前必跑）
- [ ] 目录结构（`backend/`、`scripts/`、`tests/`、`workflows/`）是否和第 3 节模块边界描述一致？
- [ ] 单端口 18080 与 `backend/config.py → PORT` 是否一致（有无被改成其他端口）？
- [ ] 六个 `/api/*` 路由（projects / shots / generations / uploads / history / system）是否和 `backend/main.py` 的 include_router 列表一致？
- [ ] 是否包含 `POST /api/projects/clear`（一键清空接口）？
- [ ] 分辨率/时长/输出规格是否以 `workflows/*.json` 为准（`h3/spec.py` 的 `RESOLUTION_PRESETS` / `DURATION_MIN..MAX`，config 只从 spec 派生）？
- [ ] 上次工作是否踩了新坑？如果是，是否已追加到第 8 节 Known Gotchas？
- [ ] 上次更新是否正确递增了自进化协议版本号 + 追加了修订记录表？
- [ ] `requirements-lock.txt` 是否随 `requirements.txt` 的变更一并更新（pip-compile 或环境快照）？
- [ ] 本文引用的 scripts/ configs/ workflows/ 路径是否全部真实存在？（跑 `python scripts/check_spec_refs.py`，要求退出码 0）
- [ ] §pre-commit 表格是否与 `.pre-commit-config.yaml` **双向**一致？（既无虚构钩子，也无漏记实际钩子）

---

## 1. 项目概览

> **MiniMax-H3-lite**：MiniMax H3 视频生成时间线工作台（轻量 Web 壳）。
> 定位：面向 MiniMax H3 视频生成的三模式页面（T2V / I2V / R2V）+ 多项目 / 分镜时间线 + 历史库 + 上传校验，后端 FastAPI 单端口直出页面与 API。
> 核心特色：**单端口 18080**（Jinja2 页面 + `/api` + `/assets` + `/uploads` 统一由 FastAPI 提供）+ 三模式页面 + 项目/分镜管理 + 上传三校验（数量 / 大小 / 类型）。
> 开源协议：**Apache-2.0**
> 技术栈：**Python 3.10+（推荐 3.12）+ FastAPI + Uvicorn + Pydantic v2 + Jinja2 + SQLite（stdlib）+ diffusers（真实推理）**
> 代码入口：`scripts/clean_launch.py`（推荐，自动选 CUDA Python + 启动 uvicorn，端口被占用自动向上顺延）
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
│   │   ├── comfy_engine.py← B 方案：把任务参数注入官方 H3 工作流(t2v/i2v/r2v)，经本机 ComfyUI HTTP API(8188) 提交执行并取回 mp4（显存管理/解码/合成全交给 ComfyUI，避免手动复刻底层崩溃）
│   │   ├── uploads.py     ← 上传（数量 / 大小 / 类型三校验）
│   │   ├── history.py     ← 历史库
│   │   ├── system.py      ← 系统信息 / 引擎列表
│   │   └── queue_manager.py ← 任务队列管理
│   └── templates/         ← Jinja2 页面：base / t2v / i2v / r2v + partials
├── assets/                ← 前端静态资源（css / js / favicon）
├── model/                 ← 本地权重（ComfyUI 单文件 safetensors，目录命名对齐 ComfyUI-aki-v3：diffusion_models/ text_encoders/ vae/ loras/）
├── workflows/             ← 官方推理工作流 JSON（video_minimax_h3_{t2v,i2v,r2v}.json）
├── scripts/               ← clean_launch.py（启动入口：选 CUDA Python + 校验依赖 + 端口顺延 + uvicorn + 自动开浏览器）/ render_pages.py（把三页面模板渲染到 tests/frontend/_rendered/ 供前端 smoke 测试读取）/ smoke_real.py / verify_watermark.py / cleanup_garbage.py（原 bin 目录的 clean_launch.py / render_pages.py 已并入本目录）
├── tests/                 ← pytest（test_api_smoke / test_h3_spec_consistency / test_performance …）+ Playwright 前端冒烟
├── requirements.txt        ← 生产依赖
├── requirements-lock.txt   ← 锁定依赖版本
├── pytest.ini              ← pytest 配置
├── package.json            ← 前端测试依赖（Playwright）
└── start.bat               ← Windows 一键（→ scripts/clean_launch.py）
```

### 🔴 关键约束
1. **`backend/h3/spec.py` 是官方参数唯一事实来源**：模型文件名、采样默认值（sampler / scheduler / steps / denoise）只能在此定义，`config.py` 通过 `h3.spec` 导入，`_build_params` / `comfy_workflow` / diffusers 均消费 spec，禁止在别处另写一套。
2. **单端口直出**：页面（`/`、`/i2v`、`/r2v`）与 `/api`、`/assets`、`/uploads` 统一由一个 FastAPI 进程提供，不要新增第二端口服务。
3. **路由不做业务推理**：路由负责参数校验 + 调 `engine_registry` / 队列 / 数据库 + 返回；`inference.py` 专门负责推理参数构建。
4. **上传三校验**：`uploads.py` 必须做数量（`MAX_IMAGE/VIDEO/AUDIO_COUNT`）、大小（`MAX_UPLOAD_SIZE_MB`）、类型（扩展名 + 魔数）三重校验，不能只看扩展名。
5. **只监听 `127.0.0.1`**：距离绑 `host="127.0.0.1"`，外网访问必须套反代（HTTPS + 鉴权），见第 8 节陷阱。

---

## 🚫 禁区目录（禁止 AI 自动修改，必须人工确认）

| 路径 | 为什么禁 | 改动需什么 |
|---|---|---|
| `model/` | 权重误改导致推理结果静默劣化 | 人工逐项确认 + SHA-256 复验 |
| `comfy_kernel/` | vendored 上游（ComfyUI 内核），改动后与上游 diff 会丢失可更新性 | 记录进 ADR + 保留 patch 文件 |
| `outputs/`、`data/checkpoints/` | 生成物与断点快照，手改即失效 | 只通过生成命令更新 |
| `_archive/` | 归档不可回写 | 只新增，不修改 |

## 4. 启动命令

### 4.1 一键启动（推荐）
- **Windows**：双击 `start.bat` → 自动检测系统 Python / 兄弟项目 WinPython → 启动 `scripts/clean_launch.py` → 自动打开浏览器。

### 4.2 手动启动
```bash
# 方式 A（推荐，含 CUDA Python 切换 + 依赖校验 + 端口顺延）
python scripts/clean_launch.py
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
| `MMH3_INFERENCE_BACKEND` | INFERENCE_BACKEND | `comfy`（默认，B 方案）/ `diffusers` |
| `MMH3_COMFY_SOURCE_DIR` | COMFY_SOURCE_DIR | (保留，已不主用) Comfy 内核源码目录 |
| `MMH3_COMFY_URL` | COMFY_URL | ComfyUI HTTP 服务地址（默认 `http://127.0.0.1:8188`，B 方案经此提交官方工作流） |
| `MMH3_QUANTIZATION` | QUANTIZATION | `bf16 / int8 / int4 / gguf-q4_k_m` |
| `MMH3_MAX_CONCURRENCY` | MAX_CONCURRENCY | 单机默认串行（1） |
| `MMH3_MODEL_*` | MODEL_FL2VA / REF2VA / CLIP / VAE_VIDEO / VAE_AUDIO | 官方模型文件名覆盖 |

> 上传限制（`MAX_IMAGE_COUNT=9` / `MAX_VIDEO_COUNT=3` / `MAX_AUDIO_COUNT=3` / `MAX_TOTAL_REFS=12` / `MAX_UPLOAD_SIZE_MB=200`）与模型规格（`SUPPORTED_RATIOS` / `SUPPORTED_DURATIONS`=4~15 整秒 / `RESOLUTION_PRESETS`=0.4~0.98 MP / `MAX_PROMPT_CHARS=7000`，均从 `backend/h3/spec.py` 派生，勿在 config 另写一套）均可在 `backend/config.py` 调整（仅改 spec 为准）。

### 5.1 官方规格对照表（单一事实来源：`workflows/*.json` + `github.com/MiniMax-AI/MiniMax-H3`）

> 发生冲突时以官方来源为准；修任何一边都要同步 `backend/h3/spec.py` + `tests/test_h3_spec_consistency.py`。

| 类别 | 官方要求（README） | 项目定位/值 | 备注 |
|---|---|---|---|
| 时长 | 输出 **4–15 秒** | `h3.spec` `DURATION_MIN..MAX`=4..15，`config.SUPPORTED_DURATIONS`=range(4,16) | 前端 4–15 整秒档位 |
| 宽高比 | 21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16 | `h3.spec.RATIOS` → `SUPPORTED_RATIOS` | 与 README 一致 |
| 分辨率 | 短边默认 768；**2K 需 H3-Regenerate-2K（未开源）** | `RESOLUTION_PRESETS`=0.4~**0.98**（16:9→864×480…**1344×768**）；`dims_for_resolution()` multiple=32、长边封顶 1344 | 0.98=原生上限；`>0.98` 不作前端档位 |
| 帧率 | 24 FPS（固定） | `FPS=24` | 前端不展示/不可改 |
| 输出音频 | 32 kHz 立体声（固定） | `AUDIO_SAMPLE_RATE=32000` | 固定 |
| 输出封装 | —（ComfyUI mp4 / 8bit） | `OUTPUT_FORMAT=mp4`、`OUTPUT_BIT_DEPTH=8` | 仅在 spec 声明，前端不展示 |
| Ref2VA 图 | ≤ 9 张 | `MAX_IMAGE_COUNT=9` | |
| Ref2VA 视频 | ≤ 3 段；每段 **2–15s**；同类合计 **≤15s** | `MAX_VIDEO_COUNT=3`；`uploads.py` `MIN/MAX_SEGMENT_DURATION` + `MAX_TOTAL_KIND_DURATION`(ffprobe) | 未生效会拒传 |
| Ref2VA 音频 | ≤ 3 段；每段 2–15s；同类合计 ≤15s | `MAX_AUDIO_COUNT=3`；同上 | 音频须配图或视频 |
| Ref2VA 混合 | 文件总数 ≤ 12 | `MAX_TOTAL_REFS=12` | |
| FL2VA | 0/1/2 张图（文生/首帧/末帧/首尾帧） | `MODE_TO_TASK` text/first_frame/last_frame/first_last → t2va/fl2va | i2v 额外「跟随首帧」= 官方 Use Image Size 可选组 |

**README 关键澄清**：① H3-Base 只输出 768p；2K 走 H3-Regenerate-2K（未随开源 Base 提供）→ 本地分辨率封顶 0.98。② H3-Context-IR 未开源（官方强烈建议接入）→ 本项目「指令优化」仅为轻量本地增强，前端已如实标注非等价物。③ 模型仓库为 `MiniMaxAI/MiniMax-H3`（HF），`config.MODEL_NAME` 与之同名；`MODELS` 内的 safetensors 文件名来自 Comfy-Org 工作流导出，供参数对齐。

---

## 6. 测试约定

- 覆盖率门禁（诚实设定，家族治理 D9）：本仓**未配置** `fail_under`（无 pyproject，依赖为 requirements.txt）；当前以集成用例 + `test_h3_spec_consistency.py` 规格一致性用例为质量基线，M1 阶段评估是否引入 pytest-cov 门禁。
- pytest 配置在 `pytest.ini`，测试文件在 `tests/`（`test_api_smoke.py` / `test_h3_spec_consistency.py` / `test_gaps_uploads.py` / `test_build_params.py` / `test_performance.py`）。
- 前端冒烟：`tests/frontend/smoke.js` 读取 `tests/frontend/_rendered/*.html`（由 `scripts/render_pages.py` 生成）；Playwright 配置在 `tests/playwright.config.js`，E2E spec 位于 `tests/frontend/e2e/`（`testDir` 实测指向此；进 `tests/` 目录执行 `npx playwright test` 运行）。
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
| 1 | **端口被占用自动顺延，URL 不再是 18080** | 18080 被其他进程占用后运行 `scripts/clean_launch.py` | 启动日志提示"后端端口 18080 已被占用，自动切换到 1808X"，浏览器打开的是新端口 | `clean_launch.py` 的 `find_available_port()` 会从起始端口向上探测；若手动打开 18080 没反应，看启动日志里的实际端口，或 `MMH3_PORT` 指定其它起始位 | 2026-08-17 |
| 2 | **`scripts/clean_launch.py` 会 `os.execv` 重启为 CUDA Python** | 当前 Python 与 `find_winpython()` 找到的 CUDA 环境不是同一个 | 进程会看似"退出又起来一次"，日志里有 `[INFO] Relaunching with CUDA Python: ...` | 这是有意的（保证用带 CUDA 的 Python 跑 diffusers）；不是崩溃，别 kill。离线环境禁用下载时靠 `HF_HUB_OFFLINE=1` 等环境变量兜底 | 2026-08-17 |
| 3 | **`tests/frontend/_rendered/*.html` 是渲染产物，易被误提交** | `scripts/render_pages.py` 把三页面模板渲染成 HTML 供前端冒烟 | 生成物进 git，渲染逻辑变更后前三页快照与模板漂移 | 该目录是构建产物：确认是否应加入 `.gitignore`（`tests/frontend/_rendered/`）；真需要快照对比就让 CI 生成而非手工提交 | 2026-08-17 |
| 4 | **单端口直出，模板路径必须在 `backend/templates/`** | 新增页面时把 `.html` 放到别处 | `Jinja2Templates(directory=...)` 找不到模板 → 页面 404 / TemplateNotFound | 页面模板统一放 `backend/templates/`，在 `backend/main.py` 加页面路由（`templates.TemplateResponse(request, "xxx.html")`），不要在 Python 里手拼 HTML | 2026-08-17 |
| 5 | **diffusers ModularPipeline 参数名 ≠ 官方 ComfyUI 工作流参数名** | T2V/I2V/R2V 提交后推理抛 `TypeError: pipe() got an unexpected keyword argument 'first_image'` | 任务状态变 `failed`，前端只能看到 `TypeError: ...` | `_run_diffusers` 已做"原名 + 常见别名（image/video/audio）"两轮尝试，最终仍失败会把 `原错误 / 别名后错误 / 当前入参 / pipeline.__call__ 签名` 一并写入 RuntimeError，看 `generation_tasks.error` 字段即可定位 | 2026-08-17 |
| 6 | **测试会大量灌入 `proj_*` 项目 & 4 字节空 PNG/WAV，挤爆 `uploads/`** | 跑 `tests/test_performance.py` / `test_api_smoke.py` 后 | SQLite 有几百条 `性能测试_*` / `冒烟测试项目`，`uploads/` 几千个 4 字节空文件 | 用 `scripts/cleanup_garbage.py` 一键清空（删全部项目 + 任务 + 资产 + uploads/assets 内文件）；UI 也接入了 `POST /api/projects/clear` 按钮 | 2026-08-17 |
| 7 | **官方 t2v 工作流实际调用 `MiniMaxH3ImageToVideo` 节点（与 i2v 共用 FL2VA 模型）** | 查 `workflows/video_minimax_h3_t2v.json` 时疑惑"为什么 t2v 也是 I2V 子图" | 误以为前端 T2V 应换模型 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` 同时驱动 T2V/I2V（first_frame/last_frame 为空时退化为 T2V）；前端 T2V 页面应显示 T2VA 任务标签 + 该模型文件名，而非改模型 | 2026-08-17 |
| 8 | **分辨率/时长/输出格式需以官方工作流 + 官方模型页为准，不能硬编码 `["768P","2K"]` 或 `[4,8,10,15]`** | 用户指出"前端后端都未对齐 workflows"，并援引官方 README 纠偏 2K | 前端只给 768P/2K（2K 误标），时长只有 4/8/10/15，还显示固定的"输出规格 24fps·32kHz"可点行 | 以 `workflows/*.json` + `github.com/MiniMax-AI/MiniMax-H3` 为事实来源写入 `backend/h3/spec.py`：**H3-Base 原生上限 = 0.98MP(1344×768，短边 768)**，`RESOLUTION_PRESETS` 只到 0.98（>0.98 需 H3-Regenerate-2K 模块，未随开源 Base 提供 → 不作前端档位），`dims_for_resolution()` 按 aspect×MP算出（multiple=32，长边封顶 1344）；时长 = `DURATION_MIN..MAX`(4~15 全部整秒)；输出固定（fps24/bit_depth8/mp4/32k 立体声）只在 spec 声明、前端不显示；config 的 `SUPPORTED_*` 从 spec 派生 | 2026-08-17 |
| 9 | **diffusers 模型未下载 / 离线模式 → 任务 failed 且报 `Could not find or load 'modular_model_index.json' or 'model_index.json'`** | 未设 `MMH3_MODEL_PATH` 且本机 HF 缓存无 `MiniMaxAI/MiniMax-H3`（`clean_launch.py` 默认 `HF_HUB_OFFLINE=1`） | 任务 `failed`，错误是底层 diffusers/hf_hub 裸 traceback（`LocalEntryNotFoundError` / `OfflineModeIsEnabled`），用户不知下一步 | 用默认 **comfy 后端（B 方案）**：`comfy_engine.py` 把参数注入官方 H3 工作流（t2v/i2v/r2v）经本机 ComfyUI `MMH3_COMFY_URL`(8188) HTTP 提交执行并取回 mp4，无需 diffusers 格式权重；仅当坚持 diffusers 后端才需 `inference.py` 的 `_model_available_locally/_model_missing_error` 预检（本地目录校验 `model_index.json`、依赖 diffusers 格式权重）。官方 `modular_model_index.json` = 单个 `MiniMaxH3ModularPipeline` | 2026-08-18 |
| 10 | **comfy 后端（B 方案）的正确跑法 = HTTP 提交官方工作流，而非进程内手动调 Comfy 内核** | 早期 `comfy_engine` 在 C:\Python312 手动 `comfy.sd.load_diffusion_model` + `VAE.decode`，12GB 卡上采样后解码 OOM / conv3d NotImplementedError / 段错误(0xC0000005)，纯 CPU 兜底又致内存过载 | 任务 failed，报 `CUDA OOM` / `slow_conv3d_forward CUDA backend` / `Input type (float) and bias type (c10::Half)`，甚至进程崩溃重启 | 改走 **ComfyUI HTTP 方案**：`comfy_engine.run` 加载 aki-v3 官方工作流 `user/default/workflows/video_minimax_h3_{t2v,i2v,r2v}.json` → `_extract_api` 转 API(剔除 `MarkdownNote/Note/Reroute`) → `_inject_common` 注入宽高/时长(PrimitiveFloat 秒数)/种子/prompt/steps + 统一 clip 名为 `qwen3vl_32b_minimax_h3_abliterated_nvfp4.safetensors`（aki 只有这个，官方 i2v/r2v 引用的 `nvfp4_awq` 不存在需改写）→ POST /prompt → 轮询 /history → 拷贝 output mp4 到 `assets/generated/`。显存/解码/合成全交给 ComfyUI(aimdo 动态显存)，已实测 4s t2va 产出 1.06MB mp4。**注意：官方工作流 editor 转 API 时 `ResolutionSelector`→`MiniMaxH3ImageToVideo` 的 width/height 连接会丢失，需在注入时把宽高写进主节点或 ResolutionSelector** | 2026-08-18 |
| 11 | **akiv3 自带官方工作流引用的 clip 名与实际模型不一致（i2v/r2v 用 `nvfp4_awq`，实际只有 `abliterated_nvfp4`）** | 用官方 i2v/r2v 工作流直接提交 → CLIPLoader 找不到 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 提交时加载 CLIP 失败 / 400 | `_inject_common` 强制把 CLIPLoader.clip_name 统一改为 aki 实际存在的 `qwen3vl_32b_minimax_h3_abliterated_nvfp4.safetensors`（本机唯一）。模型权重需硬链接到 aki `models/{unet,vae,text_encoders}` 目录（同卷不占空间） | 2026-08-18 |
| 12 | **全局环境装了最新版 torch（2.13+cu132）与 H3 不兼容，导致 diffusers 加载模型即失败** | 之前误装了当前最新 torch，`MiniMaxAI/MiniMax-H3` 模型无法加载 | `RuntimeError: Failed to load config from 'MiniMaxAI/MiniMax-H3'` / conv3d 崩溃（参见 #10） | 用 **项目 venv 隔离**：`python -m venv .venv` 后离线安装 `torch 2.9.1+cu130 / torchvision 0.24.1+cu130 / torchaudio 2.9.1+cu130`（dowload-r2 直链，manual 目录），CUDA conv3d 验证通过。aki ComfyUI 内核实测也与该版本配套 | 2026-08-19 |
| 13 | **PyTorch cu130 wheel 有文件名陷阱：官方直链偶发把 torchvision 内容错当 torchaudio / 下载不完整，装错包且看不出** | 用 `download-r2.pytorch.org/whl/cu130` 多线程下载 torchvision/torchaudio | 文件名是 `torchvision-…win_amd64.whl` 但 `pip show` 装出来是 torchaudio；或 wheel 仅几 MB（真实应数十 MB） | 装前置校验 wheel 的 METADATA：`zipfile` 读 `*.dist-info/METADATA` 的 `Name/Version`，与文件名严格一致才安装；大小过小多半是 404 错误页被落盘 | 2026-08-19 |
| 14 | **脱离 ComfyUI 独立运行 = 内置 comfy_kernel 引擎进程内执行官方工作流，而非 HTTP 或手动复刻底层** | 用户要求"完全脱离 ComfyUI"；此前 HTTP(8188) 依赖外部服务、进程内手动调内核 12GB 卡崩溃（#10） | 服务未启则任务 failed / crash | 项目内置完整 `comfy_kernel/`（复制 aki ComfyUI 源码，**必须补齐 `comfy/ldm/models/`、`comfy_api/input/` 等被缩小遗漏的目录**）；进程内：`folder_paths.add_model_folder_path` 绑定项目 `model/` → `nodes.init_extra_nodes` 注册 601 节点 → `execution.validate_prompt`（拓扑补全，返回 `outputs_to_execute`）→ `scene/kernel` 的 `PromptExecutor.execute` → 从 `history_result["outputs"]` 或输出目录兜底找最新 mp4。默认走进程内；显式设 `MMH3_COMFY_URL` 才走 HTTP | 2026-08-19 |
| 15 | **comfy_kernel 进程内 init 用 `/XD input` 会误删源码里的 `comfy_api/input` 目录** | 用 robocopy 同步 comfy_kernel 时把 `input` 当运行时目录排除 | `ImportError: No module named 'comfy_api.input'` | robocopy 排除目录必须用**绝对路径**（`/XD "…\ComfyUI\input"` 而非 `input`），否则会命中 `comfy_api/input` 等源码同名目录 | 2026-08-19 |
| 16 | **项目 model/ 权重文件名 ≠ 官方工作流引用的文件名（大小写/量化后缀不同），直接提交会校验失败** | 固化 API 引用 `minimax_h3_fl2va_pruned_int8_convrot.safetensors`，项目实为 `MiniMax_H3_FL2VA_pruned_int8_convrot.safetensors`；clip 官方 `awq`、项目只有 `abliterated` | `validate_prompt` 报 `Value not in list: unet_name: ... not in [...]` | `comfy_engine._inject_models` 扫描项目 `model/` 实际文件名，与 API 引用做「子串/共同前缀」改写（UNET/CLIP/VAE/Lora）；官方 subgraph 工作流需经 `extract_api_prompt` 一次性展开固化到 `workflows/api/*.api.json`（运行时不再依赖 aki 工具） | 2026-08-19 |
| 17 | **12GB 卡进程内跑 20GB H3 模型必须启用 DynamicVRAM（comfy-aimdo），否则采样阶段 CUDA OOM** | 服务常驻下提交生成 → 节点执行到 `SamplerCustomAdvanced`（node 号视工作流而异）报 `CUDA error: out of memory` | 显存不足，任务 failed；独立脚本偶发成功因进程退出释放显存 | `_ensure_kernel` 需：①在 comfy 模块加载前设 `cli_args.args.lowvram=True`；②对 N 卡依次 `comfy_aimdo.control.init()`（先加载 DLL！只调 `init_devices` 会因 `lib=None` 静默返回 False）→ `init_devices((idx, headroom))` → `CoreModelPatcher=ModelPatcherDynamic` + `aimdo_enabled=True` ③**`execution.py/model_prefetch` 在 control.init() 前已 import model_vbar，其顶层 `lib=control.lib` 快照为 None → 必须 `importlib.reload(comfy_aimdo.model_vbar)` 等**，否则执行器调 vbar API 报 `'NoneType' object has no attribute 'vbars_reset_watermark_limits'` | 2026-08-19 |
| 18 | **comfy-aimdo 必须 `control.init()` 先加载 DLL，纯 `init_devices` 判定 `lib is None` 会静默失败** | 直接调 `comfy_aimdo.control.init_devices(...)` 想启用动态显存 | 返回 False，`aimdo_enabled` 永远 False，后续 OOM/crash | 先 `control.init()`（失败可查日志 "comfy-aimdo failed to load"），再 `init_devices`；若 `lib` 为 None 说明 DLL 未装载（CTRL 直连 CDLL 可测） | 2026-08-19 |
| 19 | **headless 进程内内核初始化时两个内置 comfy_extras 节点导入失败告警（`comfy_angle` 缺失 / `PromptServer.instance` 无）** | 项目后端启动时 `nodes.init_extra_nodes` 扫描 `nodes.py` 的 `extras_files` 全量列表 | `WARNING:root:IMPORT FAILED: nodes_glsl.py`（`No module named 'comfy_angle'`）+ `nodes_glsl.py` / `nodes_replacements.py` | 这俩模块与 H3 无关且需 GUI 服务端/ATGL：在 `comfy_kernel/nodes.py` 的 `extras_files` 列表里删除 `"nodes_glsl.py"` 与 `"nodes_replacements.py"` 两行即可（`init_builtin_extra_nodes` 跑出 `IMPORT_FAILED: []`）；`expandable_segments not supported` 是 Windows CUDA 缓存分配器良性告警，忽略即可 | 2026-08-19 |
| 20 | **model/ 整类目录级 Junction 会暴露 ComfyUI 顶层占位文件到扫描列表（无害）** | 把 `model/{diffusion_models,text_encoders,vae,loras}` 改为整类目录 Junction 指向 ComfyUI 后，`_scan_project_models`（`glob("*") + is_file()`）扫出 ComfyUI 顶层 0 字节占位文件（`put_*_here` / `desktop.ini`） | 扫描候选列表出现 `put_diffusion_model_files_here` / `desktop.ini` 等非模型文件名；但 `_inject_models` 按「子串/共同前缀」匹配 API 引用，占位文件不会被选中，功能无影响 | 占位文件是 ComfyUI 空目录标记，可忽略；若想列表干净，删除 ComfyUI 对应目录顶层的 `put_*_here`/`desktop.ini`（不影响两侧）。MiniMax 侧模型平铺于类别根层，故用**整类目录 Junction**；若模型按子目录嵌套（如 Image_MultiModel 的 FLUX.1-dev-fp8/），则应像 Image 那样按**每模型子目录**建 Junction，避免暴露同类别其他内容 | 2026-08-19 |

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
1. 先看 `scripts/clean_launch.py` 打印的 `[INFO] 后端启动中: http://127.0.0.1:<port>`，确认实际端口。
2. 看是否有 `[INFO] Relaunching with CUDA Python`（属于正常的 Python 切换）。
3. `python -m uvicorn backend.main:app --host 127.0.0.1 --port 18080` 前台直跑，能看到真实 traceback。

#### SOP-4: 一键清空临时项目 / 测试残留
1. 首选 UI：顶栏项目下拉里点 `⌫ 一键清空全部`（POST /api/projects/clear）。
2. 命令行：`python scripts/cleanup_garbage.py`（同步清空 SQLite + uploads/ + assets/）。
3. 仅清数据库保留文件：`POST /api/projects/clear {"keep_uploads": true}` 或 `Invoke-WebRequest -Body '{"keep_uploads":true}' -Method POST .../api/projects/clear`。
4. 上线前必跑一次（开发期间积压几百个 `性能测试_*` 很正常）。

#### SOP-5: 调试 I2V/R2V 推理失败（ModularPipeline 参数名）
1. 看 `generation_tasks.error` 字段（前端历史库会展示），新格式会把 `原错误 / 别名后错误 / 当前入参 / pipeline.__call__ 签名` 一并写入 RuntimeError。
2. 官方 ComfyUI 工作流节点名（`MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo`）≠ diffusers ModularPipeline 实际参数名。常见映射：
   - `first_image` / `last_image` → `image`（同时只接受一个）
   - `ref_images` → `image`（List）
   - `ref_videos` / `ref_audios` / `ref_video_audios` → `video` / `audio`（可能不直接对应）
3. 若 diffusers 升级后参数名变化，扩展 `backend/routers/inference.py → _run_diffusers` 的 `alias_map` + 增加新候选即可。
4. 确认 `backend/h3/spec.py` 的 `MODELS / SAMPLER / SCHEDULER / STEPS` 与 workflows JSON 一致（`pytest tests/test_h3_spec_consistency.py`）。

#### SOP-6: 进程内 comfy_kernel 引擎出片（脱离外部 ComfyUI）
1. 前提：`comfy_kernel/` 必须完整（含 `comfy/ldm/models/`、`comfy_api/input/`），`model/` 有 7 个官方单文件权重，`workflows/api/*.api.json` 为已固化的扁平 API 图（由官方 subgraph 实流经 `extract_api_prompt` 展开一次生成）。
2. `comfy_engine.run(params)` 默认走进程内：`_load_api` 读 `workflows/api/*.api.json` → `_inject_common`（宽高/时长/种子/prompt/steps + `_inject_models` 把 API 引用改写为项目实际权重名）→ `_run_in_process`（`_ensure_kernel` 惰性初始化：folder_paths 绑定 model/ + init_extra_nodes 注册 601 节点 + PromptExecutor；`validate_prompt` 校验 → `executor.execute` → 找最新 mp4）。
3. 需外部 ComfyUI 联调时，设 `MMH3_COMFY_URL` 走 HTTP 旧路径。
4. 模型文件名差异很大时，先跑 `python -c` 打印项目 `model/` 各子目录实际文件名，确认 `_inject_models` 的匹配规则（子串 → 共同前缀）能命中。
5. 首次在某环境跑通后，把 `assets/generated/` 的 mp4 当作端到端成功标志；`executor.success=False` 时看 `status_messages` 里的 `execution_error`。

---

## 📋 自进化修订记录表（AGENTS.md 进化史）

| 自进化版本 | 日期 | 触发原因 | 更新内容摘要 | 对应项目版本 | 已校验 |
|:---------:|------|---------|------------|:------------:|:-----:|
| v0.1 | 2026-08-17 | 初始建立自进化协议（对齐家族 TTS/Image/SeedVR2 约定） | 建立自进化协议（5 条铁律 + 自检清单）；项目概览（MM·H3 三模式视频工作台，单端口 18080）；模块边界（backend/main.py + h3/spec.py 单一事实来源 + 6 个 /api 路由）；启动命令（bin/clean_launch.py + 端口顺延 + CUDA Python 切换）；配置与环境变量（MMH3_*）；测试约定；Known Gotchas（端口顺延 / execv 重启 / _rendered 产物 / 模板路径）；SOP-1~3 | v0.1.0  | — |
| v0.2 | 2026-08-17 | 修复 I2V/R2V 推理 + 一键清空 + 前端 T2VA 对齐 + 清理测试残留 | `_run_diffusers` 加 alias 容错 + 详细错误上报（`RuntimeError` 含原错误/别名错误/入参/签名）；新增 `POST /api/projects/clear` + UI 按钮（顶栏项目下拉）+ `scripts/cleanup_garbage.py`；T2V 页面 PROMPT/STAG/me-tag 改为 T2VA（官方 t2v 工作流与 i2v 共用 FL2VA 模型，参见 Gotcha #7）；清空 232 个测试项目 + 236 个 4 字节空文件；自检清单新增"是否含 clear 接口"；Known Gotchas +3 条（#5 ModularPipeline 参数名 / #6 测试残留 / #7 t2v 与 i2v 共用模型）；SOP-4 / SOP-5 | v0.1.0  | — |
| v0.3 | 2026-08-17 | bin 并入 scripts | 删除 `bin/` 目录，`clean_launch.py` / `render_pages.py` 移入 `scripts/`；同步更新所有引用：start.bat（检查 + 调用 + 报错文案）、第 3 节目录树（bin/ 段并入 scripts/）、第 4 节启动命令、第 6 节测试约定、Gotcha #1~3、SOP-3、README.md 目录树与测试命令、`.github/workflows/test.yml` 入口断言、package.json 的 test:template/test:frontend、tests/frontend/smoke.js 注释、.gitignore 注释 | v0.1.0  | — |
| v0.4 | 2026-08-17 | 前端/后端分辨率、时长、输出格式对齐官方 workflows | 以 `workflows/video_minimax_h3_{t2v,i2v,r2v}.json` 为事实来源写入 `backend/h3/spec.py`：新增 `RESOLUTION_PRESETS`（0.4~2.0 MP + 16:9 精确尺寸，0.98 原生 1344×768，2.0=1920×1088 原生即支持）、`RESOLUTION_SHORT_SIDE`、`dims_for_resolution()`（aspect×MP，multiple=32，原生档长边封顶 1344）、`DURATION_MIN..MAX`(4~15)；`config.py` 的 `SUPPORTED_DURATIONS`=range(4,16)、`RESOLUTION_PRESETS`/`RESOLUTION_DEFAULT` 改为从 spec 派生、`OUTPUT_BIT_DEPTH/FORMAT` 声明固定输出；`inference._build_params` 用 `dims_for_resolution`（兼容旧值 768P/2K）；前端三模板分辨率改 megapixel 档、时长 4~15、移除"输出规格"可点行与"2K 重绘禁用"占位；`shared.js` 新增 `H3_RES_*`/`dimsForResolution` 并同步 `getActiveParams`/`readbackParams`/resPx；Gotcha #8；自检清单新增"分辨率/时长/输出以 workflows 为准" | v0.1.0  | — |
| v0.5 | 2026-08-17 | 按官方 README 纠偏分辨率上限（之前误把 2.0MP 当原生支持） | 用户指出"最多 0.98，后面不支持"，并给官方页 `github.com/MiniMax-AI/MiniMax-H3`：README 明确 "2K \| generation can be achieved with **H3-Regenerate-2K**"，H3-Base 只输出 768p。修正：`spec.py` 的 `RESOLUTION_PRESETS`/`RESOLUTION_SHORT_SIDE` 砍掉 1.2/1.5/2.0，只到 **0.98(1344×768)**；`dims_for_resolution` 长边统一封顶 1344；`inference` 旧值 "2K"→回退原生 0.98；`shared.js` 同步；前端三模板分辨率档改 0.4~0.98、时长补全 4~15 全部整秒、页脚注明"≥1080p/2K 需 H3-Regenerate-2K（未随开源 Base 提供）"；`scripts/verify_pages.py` 校验档位封顶与时长补全 | v0.1.0  | — |
| v0.6 | 2026-08-17 | 将「官方 README ↔ 项目设置」对照表沉淀进 AGENTS | 完整读取官方 README 后，新增第 5.1 节「官方规格对照表」（时长 4–15 / 六宽高比 / 分辨率 0.4~0.98 封顶 1344×768 / 24FPS / 32kHz 立体声 / mp4·8bit / Ref2VA 图 9·视频 3·音频 3·混合 12·每段 2–15s·同类≤15s / FL2VA 0-2 图），并注明 README 关键澄清（2K 需未开源的 H3-Regenerate-2K、Context-IR 未开源）。顺带修正第 5 节说明里残留的旧"RESOLUTION_PRESETS=0.4~2.0 MP"为"0.4~0.98 MP" | v0.1.0  | — |
| v0.7 | 2026-08-18 | 用户贴出 `from_pretrained` 找不到 `model_index.json` 的裸 traceback | 根因：模型未下载 + `HF_HUB_OFFLINE=1` 离线，非代码逻辑错。`inference.py` 新增 `_model_available_locally` / `_model_missing_error` 预检：本地目录校验 `model_index.json`、HF id 校验本地缓存；缺失时抛可操作中文指引（下载 + `MMH3_MODEL_PATH`，或取消 `HF_HUB_OFFLINE` 在线拉取）；`tests/test_build_params.py` 新增 `test_model_missing_preflight`。核实 HF 根 `modular_model_index.json` = 单个 `MiniMaxH3ModularPipeline`（含 transformer+transformer_ref），三任务均走根目录；Gotcha #9 | v0.1.0  | — |
| v0.8 | 2026-08-18 | 用户下载 7 个 ComfyUI 单文件权重到 `model/`，要求按类存放 | 在 `model/` 下建 `transformer/`（FL2VA+Ref2VA 主干）、`text_encoder/`（qwen3vl）、`vae_video/`、`vae_audio/`、`lora/`（fl2v_8step / ref2v_4step turbo）并移动归类；第 3 节目录树新增 `model/` 行（注明是 ComfyUI 单文件权重，非 diffusers 格式） | v0.1.0  | — |
| v0.9 | 2026-08-18 | 用户要求目录命名对齐 ComfyUI-aki-v3 的 models 布局 | `model/` 子目录改名/合并：`transformer/`→`diffusion_models/`、`text_encoder/`→`text_encoders/`、`vae_video/`+`vae_audio/`→合并 `vae/`、`lora/`→`loras/`；第 3 节目录树 `model/` 行更新为对齐 ComfyUI 的四目录命名 | v0.1.0  | — |
| v1.0 | 2026-08-18 | 用户定夺：Image_MultiModel 与 MiniMax-H3-lite 都用 B 方案（进程内 Comfy 内核） | **Image_MultiModel**：`config.yaml` 默认引擎 `z_image_turbo_diffusers`→`z_image_turbo_native`（comfy_kernel 已就位、权重路径已匹配）。**MiniMax-H3-lite**：新增 `backend/routers/comfy_engine.py`（B 方案 native 引擎：进程内复用 aki-v3/comfy_kernel 内核 → `comfy.sd.load_diffusion_model`/`load_clip(MINIMAX)` → H3 节点条件构建 → KSamplerSelect/BasicScheduler/BasicGuider/RandomNoise/SamplerCustomAdvanced 采样 → 视频/音频 VAE 解码 → imageio-ffmpeg 合成 mp4）；`config.py` 新增 `COMFY_SOURCE_DIR`（`MMH3_COMFY_SOURCE_DIR`）；`engine_registry.py` 注册 `comfy` 后端并设为默认（settings.json→comfy）；`inference.run_inference` 按 backend 分发；`requirements.txt` 加 `av`/`imageio-ffmpeg`/`soundfile` 并重生成 lock；`tests/test_comfy_engine.py`（5 用例）；health 测试允许值加 `comfy`。Gotcha #9 更新 + #10 新增 | v0.1.0  | — |
| v1.1 | 2026-08-18 | 验证后把 comfy 后端改为 HTTP 提交官方工作流（进程内手动调内核在 12GB 卡上解码 OOM/段错误崩溃） | 重写 `backend/routers/comfy_engine.py`：改为加载 aki-v3 官方 `user/default/workflows/video_minimax_h3_{t2v,i2v,r2v}.json` → `_extract_api`(剔除 `MarkdownNote/Note/Reroute`) → `_inject_common`(宽高/时长(PrimitiveFloat 秒数)/种子/prompt/steps + 统一 clip 为 `qwen3vl_32b_minimax_h3_abliterated_nvfp4`) → HTTP POST /prompt(`/MMH3_COMFY_URL` 8188) → 轮询 /history → 拷贝 mp4 到 `assets/generated/`；`config.py` 新增 `COMFY_URL`(`MMH3_COMFY_URL`)；`tests/test_comfy_engine.py` 重写为 9 用例(任务→工作流映射/假节点剔除/参数注入/clip 名 pin/参考图绑定/URL)。全部 35 项测试通过。**已实测**：ComfyUI 完整执行官方 t2v 出 `MiniMax_H3_00006_.mp4`，comfy_engine.run 出 `assets/generated/h3_t2va_*.mp4`(1.06MB)。模型权重硬链接到 aki `models/{unet,vae,text_encoders}`。Gotcha #9/#10 更新 + #11 | v0.1.0  | — |
| v1.2 | 2026-08-19 | 为脱离 ComfyUI + 修复全局最新 torch 不兼容，给项目建 venv 隔离 torch 2.9.1+cu130 | 新建 `.venv`（`python -m venv .venv`），离线安装 `torch 2.9.1+cu130 / torchvision 0.24.1+cu130 / torchaudio 2.9.1+cu130`（download-r2 直链到 `_dl/manual`，装前校验 METADATA 防文件名陷阱）；其余依赖（fastapi 0.141 / diffusers 0.39 / transformers 5.15 / av / imageio-ffmpeg / soundfile / safetensors 等）均已入 venv。已验证 `import torch 2.9.1 + CUDA 13.0 + RTX 5070 Ti + conv3d ok`。Gotcha #12（全局最新 torch 不兼容→venv 隔离 2.9.1）+ #13（cu130 wheel 文件名陷阱） | v0.1.0  | — |
| v1.3 | 2026-08-19 | 实现「完全脱离 ComfyUI 独立运行」 | **comfy_engine 改为进程内复用内置 comfy_kernel 引擎**（复制 aki ComfyUI 源码，补齐 `comfy/ldm/models/`、`comfy_api/input/`；`comfy_engine.run` 默认进程内，HTTP 仅在显式 `MMH3_COMFY_URL` 时启用）；官方 subgraph 工作流经 `extract_api_prompt` 一次性展开固化到 `workflows/api/*.api.json`（运行时不再依赖 aki 工具）；`folder_paths` 绑定项目 `model/`（diffusion_models/text_encoders/vae/loras）；主流程 `validate_prompt` → `PromptExecutor.execute` → 输出目录兜底找 mp4。**`_inject_models` 扫描项目 model/ 实际文件名改写 API 引用**（处理 `minimax_h3_…` vs `MiniMax_H3_…`、`awq` vs `abliterated` 差异）。为 venv 补装 comfy 内核依赖（einops/aiohttp/psutil/alembic/sqlalchemy/blake3/simpleeval/yarl/torchsde/scipy/sentencepiece/comfy-kitchen/comfy-aimdo/PyOpenGL/kornia/pydantic-settings/spandrel 等）。`clean_launch.py` 优先使用项目 `.venv`。**已实测**：进程内独立出 `assets/generated/h3_t2va_*.mp4`(352KB)，13 项测试通过。Gotcha #14/#15/#16；SOP-6 | v0.1.0  | — |
| v1.4 | 2026-08-19 | UI 服务端到端冒烟发现 12GB 卡采样 OOM → 启用 DynamicVRAM 修复 | 进程内引擎仅 `init_devices` 时 `aimdo` 未真正启用（需先 `control.init()` 载 DLL），且 `execution.py` 前已 import 的 `model_vbar.lib` 快照为 None → 报 `NoneType.vbars_reset_watermark_limits`。修复 `_ensure_kernel`：`cli_args.args.lowvram=True` + `control.init()` → `init_devices` → `CoreModelPatcher=ModelPatcherDynamic`、`aimdo_enabled=True`、reload `comfy_aimdo.model_vbar` 等。**已实测**：UI API 全链路（建项目→镜头→提交生成→轮询 completed）进程内成功出 `video/MiniMax_H3_00005_.mp4`(718KB 含音轨)，asset 入库，`/api/health` 报 `backend_requires_external:false`。Gotcha #17/#18；版本 v1.3→v1.4；修订记录 +1 | v0.1.0  | — |
| v1.5 | 2026-08-19 | model/ 权重迁移 ComfyUI + Junction 复用（零冗余），对齐 Image_MultiModel 方式 | 将 `model/` 下 FL2VA/Ref2VA×2/qwen3vl te/video+audio vae/turbo lora×2 共 8 个模型（~90.2GB）逐文件移动至 ComfyUI `models/{diffusion_models,text_encoders,vae,loras}`，`model/` 四子目录改建**整类目录级 Junction** 指向 ComfyUI（两侧共用、无冗余、无需改代码：`_scan_project_models` 的 `Path.glob/is_file` 与 `folder_paths.add_model_folder_path` 均穿透 Junction）；新增 `model/README.md`；新增 Gotcha #20（整类目录 Junction 暴露 ComfyUI 顶层 0 字节占位文件，扫描列表无害）；说明与 Image 差异（Image 每模型子目录 Junction vs MiniMax 整类目录 Junction）；版本 v1.4→v1.5 | v0.1.0  | — |
| v1.6 | 2026-08-27 | 幻影引用清理（家族规范审计 T5） | §6 测试约定中指向不存在的 e2e 目录引用（`tests` 下旧写法）RETARGET 为 `tests/frontend/e2e`（`tests/playwright.config.js` 的 `testDir: './frontend/e2e'` 实测指向此，spec 为 `smoke.spec.js`），并补记真实运行命令（`tests/` 下 `npx playwright test`，已用 `--list` 验证可发现全部用例）；其余内容未动 | v0.1.0  | — |

| v1.7 | 2026-08-27 | **家族规范完整性审计（Phase B · B4）：自进化协议打补丁（第 6 条铁律 + 修订表已校验列）** | ① 新增第 6 条铁律「证据绑定（Evidence Binding）」：可执行路径必须当时可验证存在、未实现项须显式标注、禁止虚构 CI 门禁；② 自检清单追加两项：路径真实存在校验（跑 `python scripts/check_spec_refs.py`）与 pre-commit 双向一致校验；③ 修订记录表增加「已校验」列，历史行统一填 `—`（未校验），新条目须填 `✓ (check_spec_refs)` 或 `✗`；④ 本仓新增 `scripts/check_spec_refs.py` 家族审计 wrapper 与 `.github/workflows/docs-consistency.yml`（本地/含审计器环境强校验，纯 CI 环境找不到审计器时降级跳过保持绿）。本行即首个填写「已校验」的条目 | v0.1.0| ✓ (check_spec_refs) |
| v1.8 | 2026-08-27 | **家族规范治理 Phase C/D/E 落地（一致性·补齐·账本）** | C2 合规文档统一命名 COMPLIANCE_CHECKLIST.md；C0 未入库 docs 链接标注；D1 §0 仲裁节；D3 FILEMAP+同步脚本；D4 禁区章节；D5 .github 治理层补齐；D8 SECURITY.md 空壳重写为 6.2KB 事实文档；D9 覆盖率路线图（诚实设定）；E3 AGENTS 体量拆分 48.4KB（达标）。docs/ 被 .gitignore:59 忽略，治理文档以本地文档形式存在 | v0.1.0 | ✓ (check_spec_refs) |

<!-- 🔄 下次更新 AGENTS.md 时，在上面表格末尾追加新一行，不要删除历史记录 -->

## 路线图落地新增模块（2026-08-18，未提交）
- backend/checkpoint.py — TaskCheckpoint 断点保存（移植自 TTS_MultiModel）
- backend/routers/queue_manager.py — 接入任务级 + worker 级 checkpoint 快照与恢复
- backend/main.py — startup 调用 resume_unfinished_tasks()
- backend/config.py — 新增 CHECKPOINT_DIR / CHECKPOINT_EVERY
- scripts/check_comfy_kernel.py — Comfy 内核复用只读检查
- docs/comfy-kernel-reuse-poc.md（本地文档，未随仓库发布） — Comfy 内核进程内复用 PoC 评估
- tests/test_api_integration.py（10 用例）、tests/test_checkpoint.py（13 用例）

## 📂 文件归档与放置规范（重要：新增文件必须遵守）

> 本仓库目录已于 2026-08-23 系统整理（见 `docs/整理记录_20260823.md`（本地文档，未随仓库发布））。后续任何新增/生成文件，**先判断类型再放置**，不要随意丢在仓库根目录或其他位置。

**docs/ 分类（项目文档）**
- `docs/project/`：需求(PRD)、架构、API、技术选型、设计上下文
- `docs/plans/`：实施计划、路线图、指南(Guide)、待办(TASKS)
- `docs/reports/`：评估/审计/安全/测试/优化报告、Lessons
- `docs/repo-analysis/`：仓库学习报告（命名 `{仓库名}_技术学习报告.md`）
- `docs/_devarchive/`：历史/一次性开发产物、交接方案、旧版本文档（**归档而非删除**）

**根目录只允许放置**
- 标准仓库文件：README、LICENSE、NOTICE、CONTRIBUTING、CHANGELOG、AGENTS、SECURITY
- 构建与配置：build/gradle、pytest.ini、requirements*.txt、package.json、.gitignore、.env(.example)、启动脚本(start/install)
- 明确被 build/CI 或文档要求从根目录运行的工具

**禁止事项（防止回归混乱）**
- ❌ 一次性调试脚本/截图/日志/草稿 → 放 `scripts/` 或 `docs/_devarchive/`，绝不堆在根目录
- ❌ 文档散落到 backend/tests/scripts 等业务目录 → 归入 `docs/` 对应分类
- ❌ 移动/删除 gitignored 运行时产物（`.coverage` 等）
- ❌ 删除旧版本文档 → 需要留档移入 `docs/_devarchive/`

> 本仓库特别说明：`docs/` 目前仅 4 篇平铺文档，文档增多后再按 `project/ plans/ reports/` 归类即可。
> `.canvas-meta.json`/`.design.json` 为设计工具元数据，保留原位。
> 新增文件前若不确定归属，先询问，不要自作主张放置。
