# MM·H3 工作台 · MiniMax H3 视频生成时间线工作台

一个面向开发者的本地视频生成工作台：以**多镜头时间线**编排视频项目，输入提示词 / 参数 / 参考素材，调用本地 **MiniMax H3**（H3-Base）推理服务逐镜头生成视频并预览成片。

前端按官方三份 ComfyUI 工作流拆分为**三个模式页**（文生 T2V / 图生 I2V / 多模态参考 R2V），由 **FastAPI + Jinja2 单端口服务端渲染**（`backend/templates/`，`base.html` + partials + 三页面模板），顶栏一键切换；展示壳（剧场 / 电视 / 放映机）首次进入引导选择并持久化，切换入口收敛在顶栏「外观」菜单。明暗双主题，响应式。

> 当前状态：前端模板化（Jinja2 单端口）与后端 API 全部就绪，官方工作流能力对齐（G1–G7）已完成，后端单测 29 项 + 前端冒烟 55 项全部通过；**真实模型端到端推理**待本机模型环境就绪后验证（见「模型与推理说明」）。

## 功能特性

- **三模式页**：文生视频（`/`，T2V）/ 图生视频（`/i2v`，首帧/末帧/首尾帧 + 图像槽位）/ 多模态参考（`/r2v`，参考素材管理器 + 标签速查），顶栏切换互跳、当前页高亮；时间线镜头按模式自动跳转到对应页面
- **官方参数对齐**：六种宽高比 + 768P 短边（上限 768×1344、32 倍数）实时像素换算；时长 4/8/10/15s 按 17k+5 帧网格显示帧数；噪声种子输入（留空=随机）；i2v 可「跟随首帧图像尺寸」；高级参数可覆盖采样器（Sampler/Scheduler/Steps/Denoise）
- **多模态参考（REF2VA）**：图 ≤9 / 视频 ≤3 / 音频 ≤3，混合 ≤12；参考保真度 match/max；参考视频可配同步音轨；提示词按官方标签（`<Picture N>` / `<Video N>` / `<Audio N>`、`<d>[语言]`、fully_preserved / partially_copy / reference）引导书写
- **输入校验**：格式 / 大小 / 数量上限 / 音频须配图或视频 / 视频与音频每段 2–15s、同类合计 ≤15s
- 生成任务队列与状态流转、历史库回看、多项目管理、推理引擎切换
- 展示壳（剧场红 / 电视琉珀 / 放映机青绿）首访引导 + 本地持久化 + 顶栏外观菜单切换；明暗双主题；正式 favicon 三件套
- 提示词 ≤7000 字符上限前后端一致校验

## 目录结构

```
MiniMax-H3-lite/
├── backend/
│   ├── main.py           # FastAPI 入口（单端口 18080：Jinja2 页面 + /api + /assets）
│   ├── templates/        # Jinja2 页面模板（base.html + partials/ + t2v/i2v/r2v.html）
│   │   └── partials/     # chrome / stage / timeline / statusbar / history 等板块
│   ├── h3/spec.py        # 参数契约真源（帧公式/分辨率/模型名/上限）
│   └── routers/          # projects / shots / generations / uploads / history / system
├── assets/
│   ├── css/shared.css    # 三页共享样式（令牌/骨架/舞台/展示壳/弹层/响应式）
│   ├── js/shared.js      # 共享逻辑（API/时间线/参数/素材/生成/持久化，页面经 window.MMH3_PAGE 配置化）
│   └── favicon.svg / favicon-32.png / apple-touch-icon.png
├── workflows/            # 官方三份 ComfyUI 模板（t2v / i2v / r2v，能力真源）
├── tests/                # 后端 pytest 单测 + tests/frontend/ 前端冒烟（读 render_pages.py 渲染产物）
├── bin/
│   ├── clean_launch.py   # 一键启动（单端口 uvicorn + 开浏览器）
│   └── render_pages.py   # 渲染 Jinja2 模板 → tests/frontend/_rendered（供前端冒烟）
├── start.bat             # 一键启动（调用 bin/clean_launch.py）
├── docs/                 # PRD.md（权威 spec）/ TASKS.md / IMPLEMENTATION_GAPS.md（补齐指南）
└── _archive/             # 已归档旧原型 + legacy-standalone-html/（改造前独立 HTML）
```

## 快速开始

### 一键启动

```bat
start.bat
```

（自动探测 Python → 启动后端 FastAPI，单端口 `http://127.0.0.1:18080` 直出页面 + API + 静态资源 → 打开浏览器。端口可用环境变量 `MMH3_PORT` 覆盖。）

### 手动启动

```bat
:: 单端口：Jinja2 页面 + /api + /assets 统一由 FastAPI 提供
python -m uvicorn backend.main:app --port 18080
```

页面地址：`http://127.0.0.1:18080/`（T2V）、`/i2v`（I2V）、`/r2v`（R2V）。

### 测试

```bat
:: 后端单测（含公式一致性、上传校验、配对音轨、时长校验）
python -m pytest tests/ -q

:: 前端冒烟（先渲染 Jinja2 模板，再对三模式页跑 jsdom 交互断言）
npm install          :: 首次安装 jsdom（devDependency）
npm run test:frontend   :: 等价于 python bin/render_pages.py && node tests/frontend/smoke.js
```

## 官方能力对齐与已知边界

| 能力 | 状态 | 说明 |
|---|---|---|
| t2v / i2v（首/末/首尾帧）/ r2v 三任务 | ✅ | 与官方 `MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo` 节点一一对应 |
| 帧数 17k+5 网格、768P 短边 + 1344 上限 + 32 倍数 | ✅ | 公式与 `backend/h3/spec.py` 及官方模板一致 |
| ref_image_size（match/max） | ✅ | 请求级优先于全局设置；diffusers 后端按语义做 PIL 缩放 |
| 噪声种子 | ✅ | 留空=随机；固定种子可复现（依赖引擎确定性） |
| 参考视频同步音轨（ref_video_audios） | ✅ 有边界 | diffusers 后端不支持该参数时自动降级为独立音频参考 |
| 采样参数覆盖 | ✅ 有边界 | 请求级优先于全局；diffusers 后端忽略采样器覆盖（前端已标注） |
| 输入片段时长 2–15s / 同类合计 ≤15s | ✅ | 上传时 ffprobe 校验，超限 422 且不留孤儿文件 |
| 2K（H3-Regenerate-2K） | ⛔ 未开源 | 前端选项已禁用；仅官方 API 可用，本项目不内置云端依赖 |
| H3-Context-IR | ⛔ 未开源 | 前端「指令优化」为本地轻量规则增强，非官方等价物 |
| i2v 跟随首帧尺寸 | ✅ | 上传时记录图像宽高，「生成尺寸=跟随首帧」时按短边 768 换算 |

## 模型与推理说明

- 开源模型：**H3-Base-FL2VA**（t2v + 首/末帧）与 **H3-Base-Ref2VA**（多模态参考），768p 音画一体生成（24fps / 32kHz 立体声 / 4–15s）。
- 后端仅支持本地 diffusers（进程内 `ModularPipeline`），完全脱离 ComfyUI 运行；`workflows/` 三份官方模板仅作参数契约参考，不被执行。
- 模型权重：本地路径经 `MMH3_MODEL_PATH` 指定，留空则从 HuggingFace `MiniMaxAI/MiniMax-H3` 拉取；国内下载优先魔搭 `MiniMax/MiniMax-H3`。显存有限时建议官方模板同款 int8 pruned 权重 + `MMH3_QUANTIZATION` 量化档位。
- 真实推理前请先完成：安装推理依赖（`requirements.txt` 中 diffusers/transformers 段）、准备权重，随后执行 `python scripts/smoke_real.py` 冒烟验证，再走一遍三模式页生成闭环。
- 许可证：MiniMax H3 Community License，商用 / 再分发 / 微调前请确认条款。
- 代码许可 Apache-2.0；MiniMax H3 模型权重遵循 MiniMax 官方权重协议（含地域条款），使用前请阅读官方许可。

## 文档索引

- 产品需求文档（权威 spec）：[docs/PRD.md](docs/PRD.md)
- 能力补齐实施指南：[docs/IMPLEMENTATION_GAPS.md](docs/IMPLEMENTATION_GAPS.md)
- 设计计划：[.design.json](.design.json)
- 官方模板（能力真源）：`workflows/` 目录三份 JSON
- 官方发布页：https://modelscope.cn/models/MiniMax/MiniMax-H3
