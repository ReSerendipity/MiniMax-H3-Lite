/**
 * MM·H3 工作台 - 核心功能冒烟测试
 *
 * 覆盖场景：
 * - 页面加载无错误
 * - 展示壳选择交互
 * - 时间线渲染
 * - 外观设置持久化
 * - shared.js 在真浏览器里的代码路径（引擎菜单 / 字数与 toast / 滑块联动 /
 *   折叠换算 / 舞台开关 / 历史库 / 协议罩 / 项目→镜头→参数回填全链）
 *
 * 口径分工：分支级断言（守卫、失败路径、轮询状态机）在 jsdom 冒烟
 * tests/frontend/smoke.js 里拿桩跑；本文件只跑**不依赖后端数据且不会破坏用户数据**
 * 的真机路径，需要数据时在临时项目里自建自清。
 * ⚠️ 绝不在 E2E 点 #projClear（一键清空全部）与 #genBtn（会起真推理）——
 *    前者会删掉本机真实项目数据，后者会撞 GPU 与超时。
 */

import { test, expect } from '@playwright/test';

// 首次使用协议确认（合规整改 2026-09-15）为一次性弹窗：#mmh3Agreement 以
// z-index:9999 + inset:0 全屏遮罩，未同意时会拦截页面所有点击。
// 测试上下文预置“已同意”状态，使 shared.js 跳过弹窗，避免遮罩阻塞交互断言。
// （真实用户首访仍需手动勾选同意，此 seed 仅作用于 E2E 自动化上下文。）
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('mmh3:agreement:v1', '2026-09-15');
  });
});

// ── 辅助函数 ──────────────────────────────────────────────
async function closeShellModal(page) {
  // 点击第一个展示壳卡片关闭模态框
  await page.click('#shellModal .sm-card.theater');
  await expect(page.locator('#shellModal')).not.toHaveClass(/open/);
}

/* 临时项目：E2E 需要数据时自建自清，不碰本机已有项目 */
async function createProject(page, name, shots) {
  const resp = await page.request.post('/api/projects', { data: { name } });
  expect(resp.ok()).toBeTruthy();
  const proj = await resp.json();
  const created = [];
  for (const s of shots) {
    const r = await page.request.post(`/api/projects/${proj.id}/shots`, { data: s });
    expect(r.ok()).toBeTruthy();
    created.push(await r.json());
  }
  return { proj, shots: created };
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

    // 参考列表容器应存在（项目数取决于后端数据）；
    // 初始态 display:none（shared.js 在有参考素材时才显示），断言挂载而非可见。
    const container = page.locator('#refList');
    await expect(container).toHaveCount(1);
  });

  test('should display tag chips container', async ({ page }) => {
    await page.goto('/r2v');
    await closeShellModal(page);

    // 标签芯片容器应存在（芯片数取决于后端数据）；
    // 空容器零尺寸不可见（shared.js 动态填充），断言挂载而非可见。
    const container = page.locator('#tagChips');
    await expect(container).toHaveCount(1);
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

// ── shared.js 真机代码路径（不依赖后端数据） ────────────────
test.describe('shared.js · 外观 / 提示 / 换算', () => {

  test('theme switch repaints root and persists', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    await page.click('.app-btn');
    await page.click('.app-opt[data-app="theme"][data-value="dark"]');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    expect(await page.evaluate(() => localStorage.getItem('mmh3_theme'))).toBe('dark');
    // applyTheme → syncAppMenu：选中项上 on，菜单同时收起
    await expect(page.locator('.app-opt[data-app="theme"][data-value="dark"]')).toHaveClass(/on/);
    await expect(page.locator('#appMenu')).not.toHaveClass(/open/);
  });

  test('over-length prompt flags counter and blocks submit with in-page toast', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    // 直接赋值绕开 maxlength：正是提交守卫要防的程序化超长（insertTag / 指令优化 / 提示词库回填）
    await page.evaluate(() => {
      const ta = document.getElementById('promptInput');
      ta.value = 'x'.repeat(7001);
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await expect(page.locator('#charCount')).toHaveClass(/over/);
    const posts = [];
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/api/generations')) posts.push(r.url()); });
    await page.click('#genBtn');
    await expect(page.locator('#mmh3Toast')).toContainText('7001');
    await expect(page.locator('#mmh3Toast')).toContainText('7000');
    expect(posts.length).toBe(0);   // 守卫在任何请求前返回，不会起真推理
  });

  test('seed random fills a numeric seed', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    await expect(page.locator('#seedInput')).toHaveValue('');
    await page.click('#seedRand');
    await expect(page.locator('#seedInput')).toHaveValue(/^\d+$/);
  });

  test('duration slider, number input and frame badge stay in sync', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    await expect(page.locator('.dur-frames')).toContainText('192帧');
    await page.locator('#durationSlider').fill('10');
    await expect(page.locator('#durationInput')).toHaveValue('10');
    await expect(page.locator('.dur-frames')).toContainText('243帧');
    await page.evaluate(() => {
      const di = document.getElementById('durationInput');
      di.value = '15';
      di.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await expect(page.locator('#durationSlider')).toHaveValue('15');
    await expect(page.locator('.dur-frames')).toContainText('362帧');
  });

  test('aspect fold drives pixel readout, shell ratio and device class', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    // 折叠组默认 data-folded="true"，.fold-body 被表头盖住，先展开再点选项
    await page.click('#aspectFold .fold-header');
    await page.click('#resFold .fold-header');
    await page.click('#aspectFold .fold-body .seg[data-value="9:16"]');
    await expect(page.locator('#aspectCurrent')).toHaveText('9:16');
    await expect(page.locator('#resPx')).toContainText('768×1344');
    const ar = await page.evaluate(() => document.querySelector('.preview-shell').style.getPropertyValue('--shell-ar'));
    expect(ar).toBe('9/16');
    await expect(page.locator('.preview-shell')).toHaveClass(/device-phone/);
    await page.click('#resFold .fold-body .seg[data-value="0.6"]');
    await expect(page.locator('#resPx')).toContainText('608×1088');
    await expect(page.locator('#resFold .fold-body .seg.on')).toHaveText(/0\.6M/);
  });

  test('engine menu renders from live API and closes on outside click', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    await expect(page.locator('#engineText')).toContainText('ENGINE: ');
    await page.click('.eng-switch');
    await expect(page.locator('#engineMenu')).toHaveClass(/open/);
    await expect(page.locator('#engineSwitch')).toHaveAttribute('aria-expanded', 'true');
    expect(await page.locator('#engineList .engine-item').count()).toBeGreaterThanOrEqual(1);
    await expect(page.locator('#engineList .engine-item[aria-checked="true"]')).toHaveCount(1);
    await expect(page.locator('#engineNote')).not.toBeEmpty();
    await page.click('#stageArea');
    await expect(page.locator('#engineMenu')).not.toHaveClass(/open/);
    await expect(page.locator('#engineSwitch')).toHaveAttribute('aria-expanded', 'false');
  });

  test('stage overlay toggles body classes and custom hint text', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    await expect(page.locator('body')).toHaveClass(/ctrl-hide-text/);
    await page.click('.app-btn');
    await page.click('.app-opt[data-app="stagetags"]');
    await expect(page.locator('body')).toHaveClass(/ctrl-hide-tags/);
    await expect(page.locator('.app-opt[data-app="stagetags"] .ao-desc')).toHaveText('OFF');
    await page.click('.app-btn');
    await page.click('.app-opt[data-app="stagehint"]');
    await expect(page.locator('body')).not.toHaveClass(/ctrl-hide-text/);
    await page.click('.app-btn');
    await page.fill('#stageWatermarkInput', 'E2E 自定义提示');
    await expect(page.locator('#stageHint')).toHaveText('E2E 自定义提示');
    await page.fill('#stageWatermarkInput', '');
    await expect(page.locator('#stageHint')).not.toHaveText('E2E 自定义提示');
  });

  test('history panel opens once per click and closes via ✕ (#G-24 regression)', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    await expect(page.locator('#historyPanel')).not.toHaveClass(/open/);
    await page.click('#historyBtn');
    await expect(page.locator('#historyPanel')).toHaveClass(/open/);
    await page.click('#historyBtn');
    await expect(page.locator('#historyPanel')).not.toHaveClass(/open/);
    await page.click('#historyBtn');
    await page.click('#historyClose');
    await expect(page.locator('#historyPanel')).not.toHaveClass(/open/);
  });

  test('mode tabs mark the current page aria-selected', async ({ page }) => {
    await page.goto('/i2v');
    await closeShellModal(page);
    await expect(page.locator('#modeTabs .mtab')).toHaveCount(3);
    await expect(page.locator('#modeTabs .mtab[href="/i2v"]')).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#modeTabs .mtab[href="/"]')).toHaveAttribute('aria-selected', 'false');
  });

  test('fold headers toggle their folded state', async ({ page }) => {
    await page.goto('/');
    await closeShellModal(page);
    const header = page.locator('#aspectFold .fold-header');
    const before = await header.getAttribute('data-folded');
    await header.click();
    await expect(header).not.toHaveAttribute('data-folded', before);
  });
});

// ── 项目→镜头→参数回填全链（临时项目，用完即删） ──────────
test.describe('shared.js · 镜头全链（隔离项目）', () => {
  let pid = null;

  test.afterEach(async ({ page }) => {
    if (pid) {
      await page.request.delete(`/api/projects/${pid}`);
      pid = null;
    }
  });

  test('timeline render → select → readback → addShot against the live API', async ({ page }) => {
    const { proj, shots } = await createProject(page, 'E2E-隔离项目-' + Date.now(), [
      { name: 'E2E首镜头', prompt: '黄昏海岸', mode: 'text', duration: 8, aspect: '16:9', params: { duration: 8, seed: 42, steps: 25 } },
      { name: 'E2E次镜头', prompt: '夜城追车', mode: 'text', duration: 4, aspect: '16:9', params: { duration: 4 } }
    ]);
    pid = proj.id;
    await page.goto(`/?project=${pid}&shot=${shots[1].id}`);
    await closeShellModal(page);

    // loadProjects(prefProject) → switchProject → loadProjectShots
    await expect(page.locator('#projName')).toHaveText(proj.name);
    const segs = page.locator('#tlSegments .seg[data-shot]');
    await expect(segs).toHaveCount(2);
    await expect(page.locator('#projMeta')).toHaveText('2 SHOTS · 12S');
    await expect(page.locator('#totalDurSb')).toHaveText('总时长 12s');

    // URL ?shot= 预选第二镜头 → selectShot 写片头/场记板/播放条
    await expect(segs.nth(1)).toHaveClass(/active/);
    await expect(page.locator('#promptInput')).toHaveValue('夜城追车');
    await expect(page.locator('#shotNo')).toHaveText('02');
    await expect(page.locator('#slateShot')).toHaveText('SHOT 02');
    await expect(page.locator('#pbShot')).toContainText('E2E次镜头');
    await expect(page.locator('#pbTime')).toHaveText('00:00.0 / 00:04');

    // 点第一镜头 → readbackParams 回填 seed / steps / duration
    await segs.nth(0).click();
    await expect(page.locator('#promptInput')).toHaveValue('黄昏海岸');
    await expect(page.locator('#seedInput')).toHaveValue('42');
    await expect(page.locator('#mainSteps')).toHaveValue('25');
    await expect(page.locator('#durationInput')).toHaveValue('8');

    // 键盘选中（bindSeg 的 Enter 分支）
    await segs.nth(1).press('Enter');
    await expect(segs.nth(1)).toHaveClass(/active/);

    // addShot：真实 POST + 重拉列表
    await page.click('#addSeg');
    await expect(segs).toHaveCount(3);
    const list = await (await page.request.get(`/api/projects/${pid}/shots`)).json();
    expect(list.length).toBe(3);
    expect(list[2].name).toBe('新镜头 3');
    await expect(page.locator('#projMeta')).toHaveText('3 SHOTS · 20S');

    // 时间线折叠（tl-collapse 分支）
    await page.click('.tl-collapse');
    await expect(page.locator('#timeline')).toHaveClass(/collapsed/);
    await expect(page.locator('#tlCollapse')).toHaveAttribute('aria-expanded', 'false');
  });
});

// ── 合规：首次使用协议罩（真机首访路径） ────────────────
test.describe('First-run agreement', () => {
  test.beforeEach(async ({ page }) => {
    // 覆盖根 beforeEach 的 seed：本轮要演真实首访（init script 按注册顺序执行）
    await page.addInitScript(() => { localStorage.removeItem('mmh3:agreement:v1'); });
  });

  test('agreement gate blocks the page until checked and confirmed', async ({ page }) => {
    await page.goto('/');
    const box = page.locator('#mmh3Agreement');
    await expect(box).toBeVisible();
    await expect(page.locator('#mmh3AgreeBtn')).toBeDisabled();
    await page.check('#mmh3AgreeChk');
    await expect(page.locator('#mmh3AgreeBtn')).toBeEnabled();
    await page.click('#mmh3AgreeBtn');
    await expect(box).toBeHidden();
    expect(await page.evaluate(() => localStorage.getItem('mmh3:agreement:v1'))).toBe('2026-09-15');
  });
});
