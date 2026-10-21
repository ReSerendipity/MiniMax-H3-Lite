# 提示词治理规范（AI/ML 评估 P2 · 模板库 + 变更留痕）

> 定位：把"提示词引导"从模板内联实现上升为治理规范，明确单一事实源与变更留痕流程。
> 现状：REF2VA 标签引导已在 `backend/templates/r2v.html` 内联实现（无需新写模板），
> 本文档负责将其文档化并约束后续变更。

## 一、单一事实源

| 事实 | 位置 |
| --- | --- |
| 官方标签语法（`<Picture N>` / `<Video N>` / `<Audio N>`、`<d>[语言]`） | `backend/templates/r2v.html` 提示词坞内联引导 + `backend/h3/spec.py`（REF2VA 参考素材上限 9/3/3/12） |
| 保留程度词（`fully_preserved` / `partially_copy` / `reference`） | `backend/templates/r2v.html`（REF2VA 标签引用引导段） |
| Context-IR 组织结构（subject_definitions → summary → retention_analysis → detailed_description → overall_soundscape → non_diegetic_music） | `backend/templates/r2v.html`（注明 H3-Context-IR 未开源，供手写对齐） |
| 提示词长度上限（7000 字符前后端一致） | `backend/config.py`（MAX_PROMPT_CHARS）+ `r2v.html` textarea maxlength + `backend/services/generation_service.py` 422 校验（`generations.py` 为薄路由，校验在 service 层） |
| 轻量指令优化（非 H3-Context-IR 官方等价物） | `backend/templates/r2v.html`（按钮 title 已声明边界） |

**规则**：以上事实若变更，必须同步修改事实源并在本文件登记（见第三节），不得在
前端/后端单侧静默改动造成"特征逻辑双轨"。

## 二、模板库规范

1. 用户提示词为即兴输入（存 `shots.prompt`，随任务 payload 落库可追溯）；引导模板只负责
   "教用户怎么写"，不强制改写用户内容。
2. 参考素材引用必须**按连接顺序编号**（与 `shot_refs` 顺序一致）；视频的同步音轨引用同一
   Audio 标签。
3. ref2va 对措辞敏感：引导强调"先定义主体再写镜头"，保留程度词写入提示词可显著提升遵循度。
4. 变更模板 HTML/JS 必须通过前端测试（`npm run test:frontend`：Jinja2 渲染 + jsdom 交互断言）
   与 `tests/` 后端参数一致性测试，防止标签语法与契约漂移。

## 三、变更留痕流程

1. 每次提示词引导变更（新增标签语法、改保留程度词、改 Context-IR 结构说明）：
   - 在提交信息注明 `prompt-governance` 前缀；
   - 更新本文档对应"单一事实源"行的位置/说明；
   - 若影响参数契约（如新增参考素材上限），同步 `backend/h3/spec.py` 修订记录（SPEC_VERSION +1）。
2. 后端校验与前端引导不一致视为缺陷（例：前端允许但 API 422，或反之），须同批修复。

## 四、审计

- 提示词内容本身不审计（用户即兴输入属创作数据，`shots.prompt` 已落库可追溯）；
- 治理对象是**引导模板与校验契约的一致性**，由上述规则 + 前端测试 + `check_spec_refs.py` 共同保障。
