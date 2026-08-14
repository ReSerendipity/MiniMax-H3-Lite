# MM·H3 工作台 · MiniMax H3 视频生成时间线工作台

一个面向开发者的本地视频生成工作台：以**多镜头时间线**编排视频项目，输入提示词 / 参数 / 参考素材，调用本地 **MiniMax H3**（H3-Base）推理服务逐镜头生成视频并预览成片。

结构为「顶部胶片时间线 + 中央舞台预览 + 右侧镜头参数 + 底部提示词坞」，明暗双主题，响应式。

> 当前状态：前端高保真升级已完成（[index.html](index.html)），后端与真实推理接入按 [docs/PRD.md](docs/PRD.md) 实施中。

## 功能特性

- 多镜头时间线编排（镜头段 / 播放头 / 刻度尺 / 加镜头）
- 五类生成模式：文生视频 / 首帧 / 末帧 / 首尾帧 / 多模态参考
- 镜头参数：分辨率（768P）、时长（4/8/10/15s）、六种宽高比、24fps、32kHz 立体声、运镜 / 风格 / 衔接
- 参考素材：图 ≤9 / 视频 ≤3 / 音频 ≤3，混合 ≤12（音频须配图或视频）
- 生成任务队列与状态流转、历史库回看、多项目管理（规划中）
- 明暗双主题 + 响应式

## 目录结构

```
MiniMax-H3/
├── index.html            # 前端工作台（高保真升级版）
├── .design.json          # 设计计划（权威）
├── .canvas-meta.json     # Canvas 元数据
├── server.js             # 前端静态服务器（Node 零依赖）
├── server.bat            # 本地服务器启动（Python 或 Node）
├── start.bat             # 直接打开 index.html
├── docs/
│   ├── PRD.md            # 产品需求文档（产品 + 技术一体，权威 spec）
│   └── TASKS.md          # 实现任务清单
└── _archive/             # 已归档的旧版本原型（片场/影院方向与早期概念稿）
```

## 快速开始

### 前端预览

```bat
start.bat            :: 直接以浏览器打开 index.html
server.bat           :: 启动本地静态服务器 http://localhost:8080
```

或用 Node：

```bat
node server.js
```

### 后端与本地推理（规划中，见 PRD §5–§6）

后端（FastAPI + 任务队列）与本地 H3-Base 推理接入尚未实现，落地后在此补充启动方式。

## 模型与推理说明

- 开源模型：**H3-Base**（FL2VA + Ref2VA），本地 768p 音画一体生成。
- **H3-Context-IR** 与 **H3-Regenerate-2K（2K）** 未开源，本期不实现云端依赖。
- 模型下载：HuggingFace `MiniMaxAI/MiniMax-H3`、魔搭 `MiniMax/MiniMax-H3`、GitHub `MiniMax-AI/MiniMax-H3`（国内优先魔搭）。
- 许可证：MiniMax H3 Community License，商用 / 再分发 / 微调前请确认条款。

## 文档索引

- 设计计划：[.design.json](.design.json)
- 产品需求文档：[docs/PRD.md](docs/PRD.md)
- 实现任务清单：[docs/TASKS.md](docs/TASKS.md)
