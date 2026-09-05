/**
 * Playwright E2E 配置（tests/frontend）。
 *
 * webServer：用 uvicorn 起真实 FastAPI 后端（backend/main.py 单端口直出页面）。
 * 启动链为轻量纯 Python 依赖（fastapi/uvicorn/jinja2/pydantic）——
 * torch/diffusers 仅在推理执行时函数内延迟导入，浏览器冒烟不需要。
 * 本地运行：仓库根目录执行 `npm run test:e2e`（需 .venv 或含上述依赖的 python）。
 * CI：frontend-smoke job 内安装同等轻量依赖后由 webServer 自动起服。
 */
const { defineConfig, devices } = require('@playwright/test');
const path = require('path');

const PORT = process.env.MMH3_PORT || '18080';

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: { timeout: 5000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 18080',
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
    cwd: path.resolve(__dirname, '..', '..'),
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
