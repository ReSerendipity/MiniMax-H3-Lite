# MM·H3 工作台 · MiniMax H3 视频生成时间线工作台

[![CI](https://github.com/ReSerendipity/MiniMax-H3-lite/actions/workflows/test.yml/badge.svg)](https://github.com/ReSerendipity/MiniMax-H3-lite/actions) [![gitleaks](https://img.shields.io/badge/secret%20scan-gitleaks%20passing-0080FF?style=for-the-badge)](https://github.com/ReSerendipity/MiniMax-H3-lite/actions/workflows/gitleaks.yml)

一个面向开发者的本地视频生成工作台：以**多镜头时间线**编排视频项目，输入提示词 / 参数 / 参考素材，调用本地 **MiniMax H3**（H3-Base）推理服务逐镜头生成视频并预览成片。

前端按官方三份 ComfyUI 工作流拆分为**三个模式页**（文生 T2V / 图生 I2V / 多模态参考 R2V），由 **FastAPI + Jinja2 单端口服务端渲染**（`backend/templates/`），顶栏一键切换；明暗双主题，响应式。

> 三模式（文生 / 图生 / 多模态参考）生成闭环已可用：从提示词、参数与参考素材出发，经多镜头时间线逐镜头生成并预览成片。2K（H3-Regenerate-2K）等能力待官方开源后跟进，详见下文「功能与限制」。

## 功能特性

- **三模式页**：文生视频（`/`，T2V）/ 图生视频（`/i2v`，首帧/末帧/首尾帧 + 图像槽位）/ 多模态参考（`/r2v`，参考素材管理器 + 标签速查），顶栏切换互跳、当前页高亮；时间线镜头按模式自动跳转到对应页面
- **官方参数规格**：六种宽高比 + 768P 短边（上限 768×1344、32 倍数）实时像素换算；时长 4/8/10/15s 按 17k+5 帧网格显示帧数；噪声种子输入（留空=随机）；i2v 可「跟随首帧图像尺寸」；高级参数可覆盖采样器（Sampler/Scheduler/Steps/Denoise）
- **多模态参考（REF2VA）**：图 ≤9 / 视频 ≤3 / 音频 ≤3，混合 ≤12；参考保真度 match/max；参考视频可配同步音轨；提示词按官方标签（`<Picture N>` / `<Video N>` / `<Audio N>`、`<d>[语言]`、fully_preserved / partially_copy / reference）引导书写
- **输入校验**：格式 / 大小 / 数量上限 / 音频须配图或视频 / 视频与音频每段 2–15s、同类合计 ≤15s
- **生成任务队列**与状态流转、历史库回看、多项目管理、推理引擎切换
- **展示壳**（剧场红 / 电视琉珀 / 放映机青绿）首访引导 + 本地持久化 + 顶栏外观菜单切换；favicon 三件套
- 提示词 ≤7000 字符上限前后端一致校验

## 快速开始

### 一键启动

```bat
start.bat
```

自动探测 Python → 启动后端 FastAPI，单端口 `http://127.0.0.1:18080` 直出页面 + API + 静态资源 → 打开浏览器。端口可用环境变量 `MMH3_PORT` 覆盖。

### 手动启动

```bat
python -m uvicorn backend.main:app --port 18080
```

页面地址：`http://127.0.0.1:18080/`（T2V）、`/i2v`（I2V）、`/r2v`（R2V）。

### Docker 部署（可选）

适合 Linux / GPU 服务器 / 希望隔离依赖的环境。

```bash
# 1) 部署前预检：检查目录与模型文件权限、model/ 子目录结构，并确认模型许可
sudo scripts/preflight.sh
# 2) 预检 compose 挂载源（权重 / 数据 / 上传 / 输出 / comfy_kernel 共 5 个）
python scripts/check_compose_mounts.py
# 3) 构建并启动
docker compose up -d --build
# 4) 健康检查
curl -s http://127.0.0.1:18080/api/health | python -m json.tool
```

启动后访问 `http://127.0.0.1:18080`。

> 镜像**不含** `comfy_kernel/`（ComfyUI 内核，GPL-3.0）。经 `docker compose up` 部署时会自动以只读方式挂载内核；若单独 `docker run`，native 引擎不可用，需手工挂载 `-v ./comfy_kernel:/app/comfy_kernel:ro` 提供内核。这是有意的许可边界取舍，详见 `docs/GPL_COMPLIANCE.md`。
>
> **暴露面告警**：compose 默认仅绑定本机 `127.0.0.1:18080`。切勿改为 `0.0.0.0` 后未加反向代理 + 鉴权即对外——本工作台 API 无内置认证。

**Windows 主机若容器读不到权重**：运行 `pwsh scripts/convert_model_junctions.ps1`（默认 dry-run；需约 213GB 磁盘峰值空间，容量不足请放弃转换）。

### 测试

```bat
python -m pytest tests/ -q          :: 后端单测（公式一致性、上传校验、配对音轨、时长校验）
npm run test:frontend               :: 前端测试（先渲染 Jinja2 模板，再对三模式页跑 jsdom 交互断言）
```

## 功能与限制

| 功能 | 状态 | 说明 |
|---|---|---|
| t2v / i2v（首/末/首尾帧）/ r2v 三任务 | 支持 | 与官方 `MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo` 节点一一对应 |
| 帧数 17k+5 网格、768P 短边 + 1344 上限 + 32 倍数 | 支持 | 像素与帧数公式与官方模板一致 |
| 参考图像尺寸 ref_image_size（match/max） | 支持 | 请求级优先于全局设置；diffusers 后端按语义做 PIL 缩放 |
| 噪声种子 | 支持 | 留空=随机；固定种子可复现（依赖引擎确定性） |
| i2v 跟随首帧尺寸 | 支持 | 上传时记录图像宽高，「生成尺寸=跟随首帧」时按短边 768 换算 |
| 输入片段时长 2–15s / 同类合计 ≤15s | 支持 | 上传时 ffprobe 校验，超限 422 且不留孤儿文件 |
| 参考视频同步音轨（ref_video_audios） | 有边界 | diffusers 后端不支持该参数时自动降级为独立音频参考 |
| 采样参数覆盖 | 有边界 | 请求级优先于全局；diffusers 后端忽略采样器覆盖（前端已标注） |
| 2K（H3-Regenerate-2K） | 未开源 | 前端选项已禁用；仅官方 API 可用，本项目不内置云端依赖 |
| H3-Context-IR | 未开源 | 前端「指令优化」为本地轻量规则增强，非官方等价物 |

## 模型与推理说明

- 开源模型：**H3-Base-FL2VA**（t2v + 首/末帧）与 **H3-Base-Ref2VA**（多模态参考），768p 音画一体生成（24fps / 32kHz 立体声 / 4–15s）
- 后端仅支持本地 diffusers（进程内 `ModularPipeline`），完全脱离 ComfyUI 运行；`workflows/` 三份官方模板仅作参数规格参考，不被执行
- 模型权重：本地路径经 `MMH3_MODEL_PATH` 指定，留空则从 HuggingFace `MiniMaxAI/MiniMax-H3` 拉取；国内下载优先魔搭 `MiniMax/MiniMax-H3`（[官方发布页](https://modelscope.cn/models/MiniMax/MiniMax-H3)）。显存有限时建议官方模板同款 int8 pruned 权重 + `MMH3_QUANTIZATION` 量化档位
- 真实推理前请先完成：安装推理依赖（`requirements.txt` 中 diffusers/transformers 段）、准备权重，随后运行验证脚本 `scripts/smoke_real.py` 验证真实推理链路，再走一遍三模式页生成闭环
- 许可证：MiniMax H3 Community License，商用 / 再分发 / 微调前请确认条款；代码许可 Apache-2.0

## 目录结构（概览）

```
MiniMax-H3-lite/
├── backend/            # FastAPI 单端口服务（页面 + API + 静态资源）
│   └── templates/      # Jinja2 页面模板（base.html + partials/ + t2v / i2v / r2v）
├── assets/             # 共享 CSS/JS + favicon 三件套
├── workflows/          # 官方三份 ComfyUI 工作流模板（t2v / i2v / r2v）
├── comfy_kernel/       # ComfyUI 推理内核（GPL-3.0；Docker 镜像不含，见「Docker 部署」）
├── model/              # 模型权重目录（子目录按「模型与推理说明」下载后生成）
├── tests/              # 后端单测与前端测试
├── scripts/            # 预检 / 部署校验 / 验证脚本
├── docs/               # 文档（含 GPL 合规说明 GPL_COMPLIANCE.md 等）
├── start.bat           # Windows 一键启动
└── config.yaml         # 配置文件
```

## 贡献

参与贡献请遵循 [组织级贡献指南](https://github.com/ReSerendipity/.github/blob/main/CONTRIBUTING.md)（Conventional Commits + DCO 签名）。

## 许可证

项目代码采用 Apache License 2.0 开源；MiniMax H3 模型权重遵循 MiniMax 官方权重协议（含地域条款），使用前请阅读官方许可。
