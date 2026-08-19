/**
 * MM·H3 工作台 - 核心功能冒烟测试
 * 
 * 覆盖场景：
 * - 页面加载无错误
 * - 展示壳选择交互
 * - 时间线渲染
 * - 外观设置持久化
 */

import { test, expect } from '@playwright/test';

// ── 辅助函数 ──────────────────────────────────────────────
async function closeShellModal(page) {
  // 点击第一个展示壳卡片关闭模态框
  await page.click('#shellModal .sm-card.theater');
  await expect(page.locator('#shellModal')).not.toHaveClass(/open/);
}

// ── 通用测试 ──────────────────────────────────────────────
test.describe('Core Functionality', () => {
  
  test.beforeEach(async ({ page }) => {
    // 设置本地存储避免首次弹窗干扰
    await page.addInitScript(() => {
      localStorage.setItem('mmh3_shell', 'theater');
    });
  });
  
  test('should load t2v page without errors', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/MM·H3/);
  });
  
  test('should load i2v page without errors', async ({ page }) => {
    await page.goto('/i2v');
    await expect(page).toHaveTitle(/MM·H3/);
  });
  
  test('should load r2v page without errors', async ({ page }) => {
    await page.goto('/r2v');
    await expect(page).toHaveTitle(/MM·H3/);
  });
});

test.describe('T2V Page', () => {
  
  test('should display mode tabs', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const tabs = page.locator('#modeTabs .mtab');
    await expect(tabs).toHaveCount(3);
    await expect(tabs.first()).toHaveClass(/on/);
  });
  
  test('should render timeline segment container', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    // 时间线容器应存在（镜头数取决于后端数据，不硬编码数量）
    const container = page.locator('#tlSegments');
    await expect(container).toBeVisible();
  });
  
  test('should open appearance menu', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const appBtn = page.locator('.app-btn');
    await appBtn.click();
    await expect(page.locator('#appMenu')).toHaveClass(/open/);
  });
  
  test('should persist shell preference', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    // 验证 localStorage
    const stored = await page.evaluate(() => localStorage.getItem('mmh3_shell'));
    expect(stored).toBe('theater');
    
    // 切换到其他 shell
    await page.click('.app-btn');
    await page.click('.app-opt[data-app="shell"][data-value="pj"]');
    
    const newStored = await page.evaluate(() => localStorage.getItem('mmh3_shell'));
    expect(newStored).toBe('pj');
  });
});

test.describe('I2V Page', () => {
  
  test('should highlight i2v tab', async ({ page }) => {
    await page.goto('/i2v');
    await closeShellModal(page);
    
    const i2vTab = page.locator('#modeTabs .mtab[href="/i2v"]');
    await expect(i2vTab).toHaveClass(/on/);
  });
  
  test('should display frame mode options', async ({ page }) => {
    await page.goto('/i2v');
    await closeShellModal(page);
    
    const frameModes = page.locator('.p-row .seg[data-value]');
    await expect(frameModes.first()).toBeVisible();
  });
  
  test('should display seed input with random button', async ({ page }) => {
    await page.goto('/i2v');
    await closeShellModal(page);
    
    const seedInput = page.locator('#seedInput');
    await expect(seedInput).toBeVisible();
    
    const randBtn = page.locator('#seedRand');
    await expect(randBtn).toBeVisible();
  });
});

test.describe('R2V Page', () => {
  
  test('should highlight r2v tab', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);
    
    const r2vTab = page.locator('#modeTabs .mtab[href="/r2v"]');
    await expect(r2vTab).toHaveClass(/on/);
  });
  
  test('should display engine tag', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);
    
    const engineTag = page.locator('#modeEngine .me-tag');
    await expect(engineTag).toContainText(/REF2VA/);
  });
  
  test('should display reference list container', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);
    
    // 参考列表容器应存在（项目数取决于后端数据）
    const container = page.locator('#refList');
    await expect(container).toBeVisible();
  });
  
  test('should display tag chips container', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);
    
    // 标签芯片容器应存在（芯片数取决于后端数据）
    const container = page.locator('#tagChips');
    await expect(container).toBeVisible();
  });
});

test.describe('Accessibility', () => {
  
  test('should have proper ARIA roles on mode tabs', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const tabList = page.locator('#modeTabs');
    await expect(tabList).toHaveAttribute('role', 'tablist');
    
    const tabs = page.locator('#modeTabs .mtab');
    const count = await tabs.count();
    for (let i = 0; i < count; i++) {
      await expect(tabs.nth(i)).toHaveAttribute('role', 'tab');
    }
  });
  
  test('should have aria-label on icon buttons', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const iconBtns = page.locator('.chrome .icon-btn');
    const count = await iconBtns.count();
    for (let i = 0; i < count; i++) {
      await expect(iconBtns.nth(i)).toHaveAttribute('aria-label');
    }
  });
  
  test('should have tabindex on timeline segments when present', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const segments = page.locator('#tlSegments .seg[data-shot]');
    const count = await segments.count();
    // 仅在有镜头段时验证 tabindex（镜头数取决于后端数据）
    for (let i = 0; i < count; i++) {
      await expect(segments.nth(i)).toHaveAttribute('tabindex', '0');
    }
  });
});
