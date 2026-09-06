**ADR-0001: 单端口 FastAPI（Jinja2 + API + 静态统一提供）**

- **状态**: Implemented
- **日期**: 2026-08-27
- **决策者**: 项目维护者 + AI 指挥（家族规范审计确认）

---

# 背景与问题

早期架构计划存在"前端构建产物 + 后端 API 分离部署"的形态设想。实测（2026-08-27）为
**单端口单进程**：FastAPI（`backend/main.py`）同时提供 Jinja2 服务端渲染页面（`/`、`/i2v`、`/r2v`）、
`/api/*` 路由（projects / shots / generations / uploads / history / system）与静态资源（`/assets`、`/uploads`）。

# 决策

- 应用形态：单 FastAPI 进程，默认 `HOST=127.0.0.1`、`PORT=18080`（`backend/config.py`，环境变量 `MMH3_HOST`/`MMH3_PORT` 覆盖）。
- 页面前端开发走模板直出（`PATCH` 场景绕开独立前端构建链）。
- 统一引擎配置/规格以 `backend/h3/spec.py` 为单一事实来源（`MODELS` / `SAMPLER_NAME` / `SCHEDULER` / `STEPS` / `DENOISE`）。

# 实施影响

- 启动：`uvicorn backend.main:app`；上传限制与模型规格均集中于 `backend/config.py`（派生于 `spec.py`）。

# 可回滚路径与待验证项

- 如未来拆分前端产物部署，需新 ADR 并标记本 ADR 为 Superseded。
- 待验证：`/api/health` 返回与 `settings` 一致；单端口无跨域白名单（同源访问）。
