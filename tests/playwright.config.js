/**
 * MM·H3 工作台 - Playwright E2E 测试配置
 * 
 * 用法:
 *   npm run test:e2e           # 无头模式运行所有测试
 *   npm run test:e2e:headed    # 有头模式（可视化调试）
 *   npm run test:e2e:ui        # UI 模式（交互式）
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // 测试文件位置
  testDir: './frontend/e2e',
  
  // 超时设置
  timeout: 30 * 1000,  // 单测试 30 秒
  expect: {
    timeout: 5000,     // 断言 5 秒
  },
  
  // 失败重试
  retries: 1,
  
  // 并行执行
  workers: 2,
  
  // 报告配置
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  
  // 共享配置
  use: {
    // 基础 URL（本地开发）
    baseURL: 'http://127.0.0.1:18080',
    
    // 截图/视频
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    
    // 浏览器上下文
    viewport: { width: 1920, height: 1080 },
  },
  
  // 浏览器配置
  projects: [
    // 桌面 Chrome
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    
    // 桌面 Firefox
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    
    // 桌面 Safari
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    
    // 移动设备 (iPhone)
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
  
  // Web 服务器（自动拉起后端供 E2E 测试使用）
  webServer: {
    command: 'python -m uvicorn backend.main:app --host 127.0.0.1 --port 18080',
    url: 'http://127.0.0.1:18080/api/health',
    timeout: 120 * 1000,
    reuseExistingServer: true,
  },
});
