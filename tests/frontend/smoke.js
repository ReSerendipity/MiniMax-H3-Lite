// MM·H3 前端冒烟测试（三模式页 + 展示壳持久化 + G1–G7 交互）
// 运行：npm install && npm run test:frontend（依赖 jsdom）
// 模拟后端数据，不依赖真实服务；断言失败 exit 1。
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
// 改造后前端由 Jinja2 模板渲染，smoke 读取 scripts/render_pages.py 的产物
const RENDERED = path.join(__dirname, '_rendered');
// 页面标识 → 渲染产物文件（t2v/i2v/r2v）
const PAGE_FILE = { t2v: 't2v.html', i2v: 'i2v.html', r2v: 'r2v.html' };

/* ============ 模拟后端 ============ */
const shotsByPage = {
  t2v: [
    { id: 's1', name: '镜头A', prompt: '黄昏海岸', mode: 'text', duration: 8, aspect: '16:9', params: { duration: 8, aspect: '16:9' }, refs: [] },
    { id: 's2', name: '镜头B', prompt: '夜城追车', mode: 'first_frame', duration: 4, aspect: '21:9', params: { duration: 4, aspect: '21:9' }, refs: [{ id: 'a1', kind: 'image', mime: 'image/png', name: 'f1.png' }] }
  ],
  i2v: [
    { id: 's1', name: '首帧', prompt: 'p', mode: 'first_frame', duration: 8, aspect: '16:9',
      params: { duration: 8, aspect: '16:9', size_mode: 'follow_first', seed: 123456, sampler: 'euler', steps: 25, denoise: 0.9 },
      refs: [{ id: 'a1', kind: 'image', mime: 'image/png', name: 'f1.png', width: 1080, height: 1920 }] },
    { id: 's2', name: '首尾', prompt: 'p2', mode: 'first_last', duration: 8, aspect: '16:9',
      params: { duration: 8, aspect: '16:9', size_mode: 'follow_first', seed: 123456, sampler: 'euler', steps: 25, denoise: 0.9, i2v: { first: 'a1', last: 'a2' } },
      refs: [{ id: 'a1', kind: 'image', mime: 'image/png', name: 'f1.png' }, { id: 'a2', kind: 'image', mime: 'image/png', name: 'f2.png' }] }
  ],
  r2v: [
    { id: 's1', name: '参考', prompt: 'p', mode: 'ref', duration: 8, aspect: '16:9',
      params: { duration: 8, aspect: '16:9', ref_image_size: 'max', seed: 777 },
      refs: [
        { id: 'v1', kind: 'video', mime: 'video/mp4', name: 'clip.mp4' },
        { id: 'a1', kind: 'audio', mime: 'audio/wav', name: 'track.wav', paired_video: 'v1' }
      ] },
    { id: 's2', name: '文生', prompt: 'p2', mode: 'text', duration: 4, aspect: '16:9', params: { duration: 4, aspect: '16:9' }, refs: [] }
  ]
};

function mockFetch(pageId, captured) {
  return (u, o) => {
    u = String(u); const method = (o && o.method) || 'GET';
    const j = (x) => Promise.resolve({ json: () => Promise.resolve(x), ok: true, status: 200 });
    if (u.endsWith('/api/projects') && method === 'GET') return j([{ id: 'p1', name: 'P', shot_count: 2 }]);
    if (u.endsWith('/api/projects/p1/shots')) return j(shotsByPage[pageId]);
    if (u.endsWith('/api/health')) return j({ model: 'H3' });
    if (u.endsWith('/api/engines')) return j({ engines: [], locked: false });
    if (u.endsWith('/api/projects/p1/history')) return j([]);
    if (u.includes('/api/shots/') && method === 'PUT') return j({});
    if (u.endsWith('/api/generations') && method === 'POST') { if (captured) captured.push(JSON.parse(o.body)); return j({ id: 't1', status: 'pending' }); }
    return Promise.reject(new Error('unmocked ' + u));
  };
}

function boot(pageId, opts) {
  opts = opts || {};
  const errors = [];
  const dom = new JSDOM(fs.readFileSync(path.join(RENDERED, PAGE_FILE[pageId]), 'utf-8'), {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/',
    beforeParse(w) {
      w.fetch = mockFetch(pageId, opts.captured);
      w.alert = (m) => { if (opts.logAlerts) console.log('  [alert]', m); };
      w.confirm = () => true; w.prompt = () => null;
      w.addEventListener('error', (e) => errors.push(String((e.error && e.error.message) || e.message)));
      if (opts.storage) {
        w.localStorage.setItem('mmh3_shell', opts.storage.shell || '');
        w.localStorage.setItem('mmh3_theme', opts.storage.theme || '');
      }
    }
  });
  // jsdom 默认不拉取外部脚本：手动注入共享脚本执行
  const s = dom.window.document.createElement('script');
  s.textContent = fs.readFileSync(path.join(ROOT, 'assets/js/shared.js'), 'utf-8');
  dom.window.document.body.appendChild(s);
  return { dom, errors };
}

let pass = 0, fail = 0;
function assert(c, m) { if (c) { pass++; console.log('  ok - ' + m); } else { fail++; console.log('  FAIL - ' + m); } }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const click = (d, sel) => d.querySelector(sel).dispatchEvent(new d.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));

(async () => {
  /* ============ t2v：骨架/弹层/换算/外观/时间线 ============ */
  console.log('[t2v]');
  {
    const { dom, errors } = boot('t2v');
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors: ' + errors.join(' | '));
    const tabs = [...d.querySelectorAll('#modeTabs .mtab')];
    assert(tabs.length === 3 && tabs[0].classList.contains('on'), '3 mode tabs, t2v highlighted');
    assert(tabs[1].getAttribute('href') === '/i2v' && tabs[2].getAttribute('href') === '/r2v', 'tab links correct');
    assert(d.querySelector('#shellModal').classList.contains('open'), 'first-visit shell modal shown');
    // 展示壳现为 theater/pj 两档（SHELL_META 已移除第三档），曾为 3
    assert(d.querySelectorAll('#shellModal .sm-card').length === 2, '2 shell cards (theater/pj)');
    click(d, '#shellModal .sm-card.theater');
    assert(!d.querySelector('#shellModal').classList.contains('open'), 'modal closes after choice');
    assert(dom.window.localStorage.getItem('mmh3_shell') === 'theater', 'shell persisted');
    // 时长控件已由分段按钮(.seg[data-value="8s"])改版为滑块+数字输入，帧徽标跟随当前值
    const durSlider = d.querySelector('#durationSlider'), durInput = d.querySelector('#durationInput');
    assert(!!(durSlider && durInput) && durInput.value === '8', 'duration control defaults to 8s');
    assert(!!durSlider && durSlider.getAttribute('min') === '4' && durSlider.getAttribute('max') === '15', 'duration range 4-15s');
    const durBadge = d.querySelector('.dur-frames');
    assert(!!durBadge && durBadge.textContent.includes('192帧'), 'frame badge (8s → 192帧, 17k+5 @24fps)');
    assert(/1344×768/.test(d.querySelector('#resPx').textContent), 'resPx default 16:9 → 1344×768');
    // 比例控件已迁入 #aspectFold 折叠组（原在 .p-row）
    click(d, '#aspectFold .fold-body .seg[data-value="9:16"]');
    assert(/9:16 → 768×1344/.test(d.querySelector('#resPx').textContent), 'aspect click → 9:16 768×1344');
    const ta = d.querySelector('#promptInput');
    ta.value = 'x'.repeat(7100);
    ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    assert(d.querySelector('#charCount').classList.contains('over'), '7000-char warning');
    click(d, '.app-btn');
    assert(d.querySelector('#appMenu').classList.contains('open'), 'appearance menu opens');
    click(d, '.app-opt[data-app="shell"][data-value="pj"]');
    assert(d.documentElement.getAttribute('data-shell') === 'pj' && dom.window.localStorage.getItem('mmh3_shell') === 'pj', 'menu switches shell (pj) + persists');
    const segs = [...d.querySelectorAll('#tlSegments .seg[data-shot]')];
    assert(segs.length === 2 && segs[0].querySelector('.seg-mode').textContent === 'T2V', 'timeline segs + mode badge');
  }

  /* ============ i2v：持久化预置 / 帧模式 / 槽位 / G2/G5/G7 ============ */
  console.log('[i2v]');
  {
    const captured = [];
    const { dom, errors } = boot('i2v', { storage: { shell: 'tv', theme: 'dark' }, captured });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors: ' + errors.join(' | '));
    assert(d.documentElement.getAttribute('data-shell') === 'tv' && d.documentElement.getAttribute('data-theme') === 'dark', 'stored shell/theme pre-applied');
    assert(!d.querySelector('#shellModal').classList.contains('open'), 'no modal when shell persisted');
    assert([...d.querySelectorAll('#modeTabs .mtab')][1].classList.contains('on'), 'i2v tab highlighted');
    assert(d.querySelector('.p-row .seg.on[data-value="first_frame"]'), 'frame mode 首帧 on by shot');
    assert(d.querySelector('#fs-first').textContent.includes('f1.png'), 'first slot shows uploaded image name');
    click(d, '.p-row .seg[data-value="last_frame"]');
    assert(d.querySelector('#i2vNote').textContent.includes('末帧模式'), 'frame mode note updates');
    assert(d.querySelector('#fs-first').classList.contains('disabled') && !d.querySelector('#fs-last').classList.contains('disabled'), 'slots toggle per frame mode');
    click(d, '.seg[data-shot="1"]');
    assert(d.querySelector('.p-row .seg.on[data-value="first_last"]') && d.querySelector('#fs-last').textContent.includes('f2.png'), 'first_last readback + slot mapping');
    assert(d.querySelector('#seedInput').value === '123456', 'seed readback');
    // #advSteps 已废除，Steps 现为 #mainSteps（数字输入+滑块）
    assert(d.querySelector('#advSampler').value === 'euler' && d.querySelector('#mainSteps').value === '25' && d.querySelector('#advDenoise').value === '0.9', 'advanced params readback');
    const sizeRow = [...d.querySelectorAll('.p-row')].find(r => r.querySelector('.k') && r.querySelector('.k').textContent.trim() === '生成尺寸');
    assert(sizeRow && sizeRow.querySelector('.seg.on').dataset.value === 'follow_first', 'size_mode readback');
    click(d, '#seedRand');
    assert(/^\d+$/.test(d.querySelector('#seedInput').value), 'seed random fills numeric value');
    click(d, '#genBtn');
    await sleep(50);
    const req = captured[0];
    assert(!!req && typeof req.params.seed === 'number' && req.params.sampler === 'euler' && req.params.steps === 25 && req.params.denoise === 0.9, 'payload: seed + sampling overrides');
    assert(req.params.size_mode === 'follow_first', 'payload: size_mode');
  }

  /* ============ r2v：标签体系 / ref_image_size / 配对音轨 / G6 指南 ============ */
  console.log('[r2v]');
  {
    const captured = [];
    const { dom, errors } = boot('r2v', { captured });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'init no errors: ' + errors.join(' | '));
    assert([...d.querySelectorAll('#modeTabs .mtab')][2].classList.contains('on'), 'r2v tab highlighted');
    assert(d.querySelector('#modeEngine .me-tag').textContent === 'REF2VA', 'engine tag REF2VA');
    assert(d.querySelector('.m-kind.on').textContent.includes('REF2VA'), 'model list highlights REF2VA');
    const items = [...d.querySelectorAll('#refList .rm-item')];
    assert(items.length === 2, '2 ref items');
    assert(items[0].textContent.includes('Video 1') && items[1].textContent.includes('Audio 1'), 'official tags per kind');
    const videoItem = items.find(i => i.textContent.includes('clip.mp4'));
    assert(!!videoItem && !!videoItem.querySelector('.rm-pair'), 'video item has 配同步音轨 button');
    assert(items.find(i => i.textContent.includes('track.wav')).textContent.includes('（音轨）'), 'paired audio label');
    assert(d.querySelector('#refImgN').textContent === '0' && d.querySelector('#refVidN').textContent === '1' && d.querySelector('#refAudN').textContent === '1', 'ref counts');
    assert(d.querySelector('.ref-size .seg.on').dataset.value === 'max', 'ref_image_size readback');
    const chips = [...d.querySelectorAll('#tagChips .tg-chip')];
    assert(chips.length === 2 && chips[0].textContent === '<Video 1>', 'tag chips rendered');
    chips[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
    assert(d.querySelector('#promptInput').value.includes('<Video 1>'), 'chip inserts tag');
    const guide = d.querySelector('#tagGuide').textContent;
    assert(guide.includes('<d>') && guide.includes('中文') && guide.includes('阿拉伯'), 'dialogue tag + 11 languages');
    assert(guide.includes('fully_preserved') && guide.includes('partially_copy') && guide.includes('reference'), 'retention labels');
    assert(guide.includes('subject_definitions') && guide.includes('non_diegetic_music'), 'Context-IR structure');
    click(d, '#genBtn');
    await sleep(50);
    const req = captured[0];
    assert(!!req && req.mode === 'ref' && req.ref_ids.length === 2 && req.ref_ids[0] === 'v1', 'ref_ids ordered video-first');
    assert(req.params.ref_image_size === 'max' && req.params.seed === 777, 'payload: ref_image_size + seed');
    assert([...d.querySelectorAll('.seg[data-shot]')][1].querySelector('.seg-mode').textContent === 'T2V', 'cross-mode seg badge');
  }

  /* ============ 可访问性抽查（aria / role / 键盘可达） ============ */
  console.log('[a11y spot-check]');
  {
    const { dom, errors } = boot('t2v');
    const d = dom.window.document;
    await sleep(300);
    assert(errors.length === 0, 'init no errors');
    assert(d.querySelector('#modeTabs').getAttribute('role') === 'tablist', 'mode tabs role=tablist');
    assert([...d.querySelectorAll('#modeTabs .mtab')].every(t => t.getAttribute('role') === 'tab'), 'mode tab role=tab');
    const iconBtns = [...d.querySelectorAll('.chrome .icon-btn')];
    assert(iconBtns.length >= 3 && iconBtns.every(b => b.getAttribute('aria-label')), 'chrome icon buttons have aria-label');
    assert(d.querySelector('#projSwitch').getAttribute('role') === 'button', 'project switch role=button');
    const segs = [...d.querySelectorAll('#tlSegments .seg[data-shot]')];
    assert(segs.every(s => s.getAttribute('role') === 'button' && s.getAttribute('tabindex') === '0'), 'timeline segs role=button + tabindex');
    // 展示壳现为 theater/pj 两档
    assert(d.querySelectorAll('#shellModal .sm-card').length === 2 && [...d.querySelectorAll('#shellModal .sm-card')].every(c => c.tagName === 'BUTTON'), 'shell cards are buttons');
    click(d, '#shellModal .sm-card.theater');
    assert(d.querySelectorAll('.app-opt').length >= 5 && [...d.querySelectorAll('.app-opt')].every(o => o.type === 'button'), 'appearance options are buttons');
  }

  console.log('\nRESULT: pass=' + pass + ' fail=' + fail);
  process.exit(fail ? 1 : 0);
})();
