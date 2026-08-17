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
  
  test('should display timeline segments', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const segments = page.locator('#tlSegments .seg[data-shot]');
    await expect(segments).toHaveCount(2);  // 默认 2 个演示镜头
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
  
  test('should display reference list', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);
    
    const refItems = page.locator('#refList .rm-item');
    await expect(refItems).toHaveCount(2);
  });
  
  test('should display tag chips for prompt insertion', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);
    
    const tagChips = page.locator('#tagChips .tg-chip');
    await expect(tagChips).toHaveCount(2);
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
  
  test('should have tabindex on timeline segments', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    
    const segments = page.locator('#tlSegments .seg[data-shot]');
    const count = await segments.count();
    for (let i = 0; i < count; i++) {
      await expect(segments.nth(i)).toHaveAttribute('tabindex', '0');
    }
  });
});
