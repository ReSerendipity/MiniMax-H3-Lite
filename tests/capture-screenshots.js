/**
 * MiniMax H3 - Full Website Screenshot Capture
 *
 * 由 Seedvr2 / Image_MultiModel 的 tests/capture-screenshots.js 复制改造：
 *   - BASE_URL 改为 http://127.0.0.1:18080（MM·H3 工作台默认端口）
 *   - 主题持久化键改为 mmh3_theme（data-theme 属性一致），另有 mmh3_shell(data-shell)
 *   - 页面结构为多页面（Jinja2 服务端渲染）：/ (t2v)、/i2v、/r2v
 *   - 健康检查端点改为 /api/health
 *   - 新增：自动关闭展示壳选择弹窗（mmh3_shell）
 *
 * Prerequisites:
 *   - MiniMax H3 server running (default http://127.0.0.1:18080), start with start.bat
 *   - Playwright chromium installed: npm install && npx playwright install chromium
 *
 * Usage:
 *   node capture-screenshots.js
 *
 * Optional env overrides:
 *   MMH3_BASE_URL  e.g. http://127.0.0.1:18080
 *   MMH3_OUT_DIR   e.g. ./screenshots
 *
 * Output: screenshots/<viewport>/<theme>/<NN>-<name>.png
 *
 * NOTE: 只切换纯 UI 状态（主题）。触发真实后端工作的按钮（生成、上传等）不点击。
 */
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.MMH3_BASE_URL || 'http://127.0.0.1:18080';
const OUTPUT_DIR = process.env.MMH3_OUT_DIR
  ? path.resolve(process.env.MMH3_OUT_DIR)
  : path.join(__dirname, '..', 'screenshots');

const VIEWPORTS = {
  desktop: { width: 1920, height: 1080 },
  tablet: { width: 768, height: 1024, isMobile: true, hasTouch: true },
  mobile: { width: 375, height: 812, isMobile: true, hasTouch: true },
};

const THEMES = ['dark', 'light'];

// 三个页面路由（backend/main.py）：t2v（首页）、i2v、r2v
const PAGES = [
  { num: '01', path: '/', name: 't2v-timeline' },
  { num: '02', path: '/i2v', name: 'i2v-timeline' },
  { num: '03', path: '/r2v', name: 'r2v-timeline' },
];

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

async function screenshotPage(page, name, options = {}) {
  const {
    fullPage = true,
    waitFor = null,
    viewportName = 'desktop',
    theme = 'dark',
  } = options;

  const dir = path.join(OUTPUT_DIR, viewportName, theme);
  ensureDir(dir);

  const filePath = path.join(dir, `${name}.png`);

  if (waitFor) {
    await page.waitForTimeout(waitFor);
  }

  await page.screenshot({ path: filePath, fullPage });
  console.log(`  Captured: ${filePath}`);
}

async function setTheme(page, theme) {
  // 主题持久化键 'mmh3_theme' 是 base.html 内联脚本使用的真实键。
  // 导航前设置 localStorage + data-theme 属性即可正确渲染。
  await page.evaluate((t) => {
    localStorage.setItem('mmh3_theme', t);
    document.documentElement.setAttribute('data-theme', t);
  }, theme);
  await page.waitForTimeout(300);
}

async function capturePage(page, pageDef, viewportName, theme) {
  const label = `${pageDef.num}-${pageDef.name}`;
  console.log(`Capturing Page ${label} (${viewportName}, ${theme})...`);

  await page.goto(`${BASE_URL}${pageDef.path}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  await screenshotPage(page, label, { viewportName, theme });
}

async function captureAllViewports(page, viewports, themes) {
  for (const [vpName, vpSize] of Object.entries(viewports)) {
    console.log(`\n=== Viewport: ${vpName} (${vpSize.width}x${vpSize.height}) ===`);
    await page.setViewportSize({ width: vpSize.width, height: vpSize.height });

    for (const theme of themes) {
      console.log(`\n--- Theme: ${theme} ---`);
      await setTheme(page, theme);

      for (const pageDef of PAGES) {
        await capturePage(page, pageDef, vpName, theme);
      }
    }
  }
}

(async () => {
  console.log('MiniMax H3 - Full Website Screenshot Capture');
  console.log('=============================================');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Output Dir: ${OUTPUT_DIR}`);
  console.log('');

  ensureDir(OUTPUT_DIR);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 自动关闭 MiniMax-H3 展示壳选择弹窗（避免遮挡截图）；默认壳已改为放映机
  await page.addInitScript(() => { localStorage.setItem('mmh3_shell', 'pj'); });

  try {
    console.log('Checking if server is running...');
    try {
      await page.goto(`${BASE_URL}/api/health`, { timeout: 10000 });
      console.log('Server is running!');
    } catch (e) {
      console.error('ERROR: Server is not running at', BASE_URL);
      console.error('Please start the server first with: start.bat');
      process.exit(1);
    }

    await captureAllViewports(page, VIEWPORTS, THEMES);

    console.log('\n=========================================');
    console.log('Screenshot capture complete!');
    console.log(`All screenshots saved to: ${OUTPUT_DIR}`);

  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
