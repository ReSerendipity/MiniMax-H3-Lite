# 贡献指南（CONTRIBUTING）

感谢关注 MiniMax-H3-lite！本文件给出从克隆到合并的最短路径。

## 1. 环境搭建

```bash
pip install -r requirements.txt
# 启动后端（端口 18080）
python scripts/clean_launch.py
```

模型权重不随仓库分发，见 `NOTICE` 与 `docs/MODEL_LICENSE.md`。

## 2. 本地开发循环

| 场景 | 命令 |
|---|---|
| Lint（flake8） | `flake8 backend` |
| 安全扫描（bandit） | `bandit -r backend` |
| 单测 | `pytest -q` |
| 版本一致性自检 | `pytest tests/test_version_consistency.py -q` |

## 3. 分支与提交规范

- 从最新 `main` 切出：`git checkout -b feat/xxx`。
- **Conventional Commits**：`feat(scope): 描述` / `fix(scope): 描述` / `docs:` / `ci:` / `test:` / `chore:`。
- **DCO 签名**：每个提交必须 `git commit -s`。
- 提交层钩子自动跑 flake8 / bandit / detect-secrets / gitleaks；失败请改代码，禁止 `--no-verify`。

## 4. Pull Request

PR 模板会引导填写变更动机、测试结果、自查项。

## 5. 红线

- `comfy_kernel/` 是 vendored 上游 ComfyUI 源码，禁止修改（保留与上游 diff 的可追溯性）。
- `backend/version.py` 版本号唯一事实来源为 `package.json`，禁止硬编码版本号。
- MiniMax H3 Community License 有营收/地域限制，见 `docs/MODEL_LICENSE.md`。
