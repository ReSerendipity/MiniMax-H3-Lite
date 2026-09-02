# Third-Party Notices（第三方组件声明）

> 更新日期：2026-09-02。本清单非穷尽：完整依赖以 `requirements.txt` / `requirements-lock.txt`
> 及安装环境的 `pip freeze` 为准；各组件许可以其官方仓库与包内 LICENSE 为准。

## 项目主许可

MiniMax-H3-lite 项目代码采用 [Apache License 2.0](LICENSE)。
模型权重（MiniMax H3）受其 Community License Agreement 约束，见 [NOTICE](NOTICE)，不由本文件管理。

## 主要 Python 依赖（许可类型为常见归类，以各包 LICENSE 为准）

| 组件 | 常见许可类型 | 说明 |
|---|---|---|
| torch / torchvision / torchaudio | BSD-3-Clause | 推理框架 |
| fastapi | MIT | Web 框架 |
| uvicorn | BSD-3-Clause | ASGI 服务器 |
| pydantic / pydantic-core | MIT | 数据校验 |
| aiohttp | Apache-2.0 | 异步 HTTP 客户端 |
| aiosqlite / sqlite | Apache-2.0 / 公有领域 | 本地数据库 |
| jinja2 | BSD-3-Clause | 模板渲染 |
| pillow | HPND（PIL Software License） | 图像处理 |
| numpy | BSD-3-Clause | 数值计算 |
| safetensors | Apache-2.0 | 模型权重加载 |
| opencv-python-headless | Apache-2.0 | 视觉处理 |
| httpx | BSD-3-Clause | HTTP 客户端 |
| python-multipart | Apache-2.0 | 上传解析 |

## vendored 组件

### ComfyUI 内核（`comfy_kernel/`，进程内复用）

- **组件**: ComfyUI 推理内核源码（vendored，供旧版引擎执行 ComfyUI 工作流）
- **上游**: <https://github.com/Comfy-Org/ComfyUI>（Comfy-Org）
- **许可**: [GNU GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html)
- **分发义务**: 需遵守 GPL-3.0（随附许可文本、提供源码获取方式、保留版权声明）；本地默认仅 loopback 使用

### 官方工作流模板（`workflows/`）

- MiniMax 官方 ComfyUI 模板，受 MiniMax H3 Community License 约束（见 [NOTICE](NOTICE)）

---

*疑问或遗漏请通过 Issues 反馈。*