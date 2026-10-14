// MM·H3 前端冒烟测试（三模式页 + 展示壳持久化 + G1–G7 交互）
// 运行：npm install && npm run test:frontend（依赖 jsdom）
// 模拟后端数据，不依赖真实服务；断言失败 exit 1。
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
// 改造后前端由 Jinja2 模板渲染，smoke 读取 scripts/render_pages.py 的产物
const RENDERED = path.join(__dirname, '_rendered');
// 页面标识 → 渲染产物文件（t2v/i2v/r2v）
const PAGE_FILE = { t2v: 't2v.html', i2v: 'i2v.html', r2v: 'r2v.html' };
// 官方规格期望值（帧数/像素）——由 backend/h3/spec.py 生成，
// 漂移由 tests/test_frontend_spec_mirror.py 机器拦截，勿手改。
const SPEC_EXPECT = JSON.parse(fs.readFileSync(path.join(__dirname, 'spec_expected.json'), 'utf-8'));

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

function mockFetch(pageId, opts) {
  opts = opts || {};
  const captured = opts.captured;
  const log = opts.requests;              // [{url, method, body}]；FormData 保留原对象供取字段
  let uploadN = 0, taskPollN = 0, cleared = false;
  // 镜头表按项目隔离，POST /shots 会追加 → 模拟真实 CRUD（addShot → loadProjectShots 链）
  // 必须深拷贝：PUT /shots 会就地改字段，浅拷贝会污染 shotsByPage 跨轮传递（同一段代码第二次 boot 读到上一轮改写值）
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const live = Object.assign({ p1: clone(opts.shots || shotsByPage[pageId]), p2: [] }, opts.live ? clone(opts.live) : null);
  const shotOf = (sid) => {
    for (const k of Object.keys(live)) {
      const hit = (live[k] || []).find((s) => s.id === sid);
      if (hit) return hit;
    }
    return null;
  };
  const RE_SHOTS = /^\/api\/projects\/([^/]+)\/shots$/;
  const RE_HISTORY = /^\/api\/projects\/([^/]+)\/history$/;
  const RE_PROJECT = /^\/api\/projects\/([^/]+)$/;
  const RE_TASK = /^\/api\/generations\/([^/]+)$/;
  const find = (re, url) => { const m = re.exec(url); return m ? m[1] : null; };
  return (u, o) => {
    u = String(u);
    const method = ((o && o.method) || 'GET').toUpperCase();
    const body = o && o.body != null ? o.body : null;
    const j = (x, ok) => Promise.resolve({ json: () => Promise.resolve(x), ok: ok !== false, status: ok === false ? 422 : 200 });
    if (log) log.push({ url: u, method, body });
    if (u === '/api/projects' && method === 'GET') return j(cleared ? [] : (opts.projects || [{ id: 'p1', name: 'P', shot_count: 2 }]));
    if (u === '/api/projects/clear' && method === 'POST') {
      Object.keys(live).forEach((k) => { live[k] = []; });
      cleared = true;   /* 真实后端：清库后连项目也不存在，后续 GET /projects 返空 */
      return j(opts.clearReply || { cleared: { projects: 1, shots: 2 }, removed_files: { uploads: 0, assets: 0 }, kept_uploads: false });
    }
    const pid = find(RE_SHOTS, u);
    if (pid !== null) {
      if (method === 'POST') {
        const s = JSON.parse(body);
        const created = Object.assign({ id: 'sNew', project_id: pid, duration: 8, aspect: '16:9', refs: [], params: {} }, s);
        (live[pid] || (live[pid] = [])).push(created);
        return j(created);
      }
      return j(live[pid] || []);
    }
    if (find(RE_HISTORY, u) !== null) return j(opts.history || []);
    const one = find(RE_PROJECT, u);
    if (one !== null) return j(method === 'DELETE' ? { deleted: one } : { id: one, name: 'P' });
    if (u === '/api/health') return j({ model: 'H3' });
    if (u === '/api/engines') return j(opts.engines || { engines: [], locked: false });
    if (u === '/api/engine/switch') return j(opts.switchReply || { name: 'switched' }, opts.switchOk);
    if (u === '/api/upload') {
      const seq = opts.uploadReplies;
      const r = (seq && seq.length) ? seq[(uploadN++) % seq.length]
        : { id: 'aNew' + (++uploadN), kind: 'image', mime: 'image/png', path: 'assets/up.png', meta: { original_name: 'up.png' } };
      // 真实后端会把资产挂到镜头上，后续 GET /shots 返列表可见 —— 同步模拟
      const sid = body && typeof body.get === 'function' ? body.get('shot_id') : null;
      const shot = sid ? shotOf(sid) : null;
      if (shot) (shot.refs || (shot.refs = [])).push({
        id: r.id, kind: r.kind, mime: r.mime,
        name: (r.meta && r.meta.original_name) || r.id,
        paired_video: (typeof body.get === 'function' ? body.get('paired_with') : null) || null
      });
      return j(r);
    }
    const tid = find(RE_TASK, u);
    if (tid !== null) {
      if (!opts.taskFlow) return Promise.reject(new Error('unmocked ' + u));
      const t = taskPollN < opts.taskFlow.length ? opts.taskFlow[taskPollN++] : opts.taskFlow[opts.taskFlow.length - 1];
      return j(t);
    }
    if (u.indexOf('/api/shots/') === 0 && method === 'PUT') {
      /* 真实后端会把补丁写回镜头，后续 GET /shots 可见（i2v 槽位映射依赖这一点） */
      const sid = u.slice('/api/shots/'.length);
      const shot = shotOf(sid);
      if (shot && body) {
        const patch = JSON.parse(body);
        Object.keys(patch).forEach((k) => { if (k !== 'params') shot[k] = patch[k]; });
        if (patch.params) shot.params = patch.params;
      }
      return j(shot || {});
    }
    if (u === '/api/generations' && method === 'POST') {
      if (opts.submitFail) return Promise.reject(new Error('network down'));
      if (captured) captured.push(JSON.parse(body));
      return j(opts.submitReply || { id: 't1', status: 'pending' });
    }
    return Promise.reject(new Error('unmocked ' + u));
  };
}

function boot(pageId, opts) {
  opts = opts || {};
  const errors = [];
  const jsdomErrors = [];
  /* jsdom 的「Not implemented: navigation」等 shell 级噪声走 virtualConsole，
     与页面内未捕获异常（window error 事件）分流，便于单独断言跨页跳转分支。 */
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => jsdomErrors.push(String((e && e.message) || e)));
  const dom = new JSDOM(fs.readFileSync(path.join(RENDERED, PAGE_FILE[pageId]), 'utf-8'), {
    runScripts: 'dangerously', pretendToBeVisual: true, url: opts.url || 'http://localhost/',
    virtualConsole: vc,
    beforeParse(w) {
      w.fetch = mockFetch(pageId, opts);
      w.alert = (m) => { if (opts.logAlerts) console.log('  [alert]', m); if (opts.alerts) opts.alerts.push(String(m)); };
      w.confirm = () => opts.confirmReply !== false;
      w.prompt = () => (opts.promptReply === undefined ? null : opts.promptReply);
      w.addEventListener('error', (e) => errors.push(String((e.error && e.error.message) || e.message)));
      if (opts.storage) {
        w.localStorage.setItem('mmh3_shell', opts.storage.shell || '');
        w.localStorage.setItem('mmh3_theme', opts.storage.theme || '');
      }
      if (opts.agreed) w.localStorage.setItem('mmh3:agreement:v1', '2026-09-15');
    }
  });
  // jsdom 默认不拉取外部脚本：手动注入共享脚本执行
  const s = dom.window.document.createElement('script');
  s.textContent = fs.readFileSync(path.join(ROOT, 'assets/js/shared.js'), 'utf-8');
  dom.window.document.body.appendChild(s);
  return { dom, errors, jsdomErrors };
}

let pass = 0, fail = 0;
function assert(c, m) { if (c) { pass++; console.log('  ok - ' + m); } else { fail++; console.log('  FAIL - ' + m); } }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const click = (d, sel) => d.querySelector(sel).dispatchEvent(new d.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));
const mclick = (dom, el) => el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
const fire = (d, sel, Ev) => d.querySelector(sel).dispatchEvent(new d.defaultView.Event(Ev, { bubbles: true }));
/* jsdom 的 input.files 是只读访问器，只能整体重定义后才能模拟选中文件 */
const setFiles = (dom, el, files) => Object.defineProperty(el, 'files', { value: files, configurable: true });
const mkFile = (dom, name, type) => new dom.window.File(['x'], name, { type: type || 'image/png' });
const toastText = (d) => { const t = d.getElementById('mmh3Toast'); return t ? String(t.textContent) : ''; };

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
    // 历史库面板回归（G-24：直接+委托双监听曾致一次点击 toggle 两次净零，按钮失效）
    click(d, '#historyBtn');
    assert(d.querySelector('#historyPanel').classList.contains('open'), 'history panel opens on one click');
    click(d, '#historyBtn');
    assert(!d.querySelector('#historyPanel').classList.contains('open'), 'history panel closes on second click');
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

  /* ============ 提示词超长：maxlength + 提交硬拦（与后端 422 同阈值同口径） ============ */
  console.log('[prompt-length guard]');
  {
    for (const pid of ['t2v', 'i2v', 'r2v']) {
      const { dom } = boot(pid);
      await sleep(300);
      const ml = dom.window.document.querySelector('#promptInput').getAttribute('maxlength');
      assert(ml === '7000', pid + ': #promptInput maxlength=7000（got ' + ml + '）');
    }
  }
  {
    const captured = [], alerts = [];
    const { dom } = boot('t2v', { captured, alerts });
    const d = dom.window.document;
    await sleep(350);
    const ta = d.querySelector('#promptInput');
    const cc = d.querySelector('#charCount');
    const seg = d.querySelector('#tlSegments .seg[data-id]');
    assert(!!seg, 'guard test: found a timeline seg with data-id');
    seg.classList.add('active');

    const fire = async (text) => {
      const before = captured.length;
      ta.value = text;
      ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      d.querySelector('#genBtn').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
      await sleep(300);
      return captured.length > before;
    };

    // 恰好 7000（无空白）：不标红，且必须真的提交出去
    const sent7000 = await fire('x'.repeat(7000));
    assert(!cc.classList.contains('over'), '7000 chars: no .over flag');
    assert(sent7000 === true, '7000 chars: POST /api/generations WAS issued');
    assert(captured[captured.length - 1].prompt.length === 7000, '7000 chars: submitted prompt length is exactly 7000');

    // 7001：标红 + 必须被拦下（不再新增提交），且给出可读原因
    const sent7001 = await fire('x'.repeat(7001));
    assert(cc.classList.contains('over'), '7001 chars: .over flag raised');
    assert(sent7001 === false, '7001 chars: submission BLOCKED (no POST /api/generations)');
    // G-25：提示走页面内 toast（原生 window.alert 已全量替换——宿主层对话框遮挡自动化且风格割裂）
    const toast = d.getElementById('mmh3Toast');
    assert(!!toast && /7001/.test(toast.textContent) && /7000/.test(toast.textContent),
      '7001 chars: in-page toast names both actual and limit -> ' + (toast ? JSON.stringify(String(toast.textContent).slice(0, 44)) : 'missing'));
    assert(alerts.length === 0, 'no native window.alert calls (all migrated to in-page toast)');

    // 口径修正证据：含空白时 stripped<7000 但 raw>7000，旧逻辑不会标红、后端会 422。
    // 现在以 raw（=后端 len()）为准：必须拦截。
    const ws = ' '.repeat(200) + 'x'.repeat(6900);
    assert(ws.length === 7100 && ws.replace(/\s/g, '').length === 6900, 'whitespace fixture: raw 7100 / stripped 6900');
    const sentWs = await fire(ws);
    assert(cc.classList.contains('over'), 'raw 7100 / stripped 6900: .over raised on raw length (was missed before)');
    assert(sentWs === false, 'raw 7100 / stripped 6900: submission BLOCKED on raw length');

    // 边界另一侧：raw 恰为 7000 且含空白 → 未超，允许提交
    const okWs = ' '.repeat(100) + 'x'.repeat(6900);
    assert(okWs.length === 7000, 'boundary fixture: raw exactly 7000 with whitespace');
    const sentOkWs = await fire(okWs);
    assert(!cc.classList.contains('over'), 'raw 7000 with whitespace: no .over flag');
    assert(sentOkWs === true, 'raw 7000 with whitespace: submission allowed');
    assert(captured.length === 2, 'only the 2 within-limit cases submitted (4 fired, got ' + captured.length + ')');
  }

  /* ============ shared.js 官方规格镜像：framesForDuration / dimsForResolution 全档 ============ */
  console.log('[spec mirror]');
  {
    const { dom, errors } = boot('t2v');
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'spec mirror: init no errors: ' + errors.join(' | '));
    /* syncDurationFrames + 滑块联动：逐档写 #durationInput 并派发 change，读 .dur-frames 彽标 */
    const di = d.querySelector('#durationInput'), ds = d.querySelector('#durationSlider'), badge = d.querySelector('.dur-frames');
    const badF = [];
    Object.keys(SPEC_EXPECT.frames).forEach((k) => {
      di.value = k;
      di.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
      const want = '·' + SPEC_EXPECT.frames[k] + '帧';
      if (badge.textContent !== want) badF.push(k + 's → ' + badge.textContent + ' ≠ ' + want);
      if (String(ds.value) !== k) badF.push(k + 's 滑块未跟随(' + ds.value + ')');
    });
    assert(badF.length === 0, 'framesForDuration×syncDurationFrames: ' + Object.keys(SPEC_EXPECT.frames).length + ' 个时长全与 spec.py 一致' + (badF.length ? ' — ' + badF.join(' | ') : ''));
    /* currentResPreset × currentAspect → syncResPx → #resPx */
    const resSegs = [...d.querySelectorAll('#resFold .fold-body .seg')];
    const aspSegs = [...d.querySelectorAll('#aspectFold .fold-body .seg')];
    assert(resSegs.length === SPEC_EXPECT.presets.length && aspSegs.length === SPEC_EXPECT.ratios.length,
      '折叠组穷举全部档位：' + SPEC_EXPECT.presets.length + ' 分辨率 × ' + SPEC_EXPECT.ratios.length + ' 比例');
    const px = d.querySelector('#resPx');
    const badD = [];
    SPEC_EXPECT.presets.forEach((p) => {
      click(d, '#resFold .fold-body .seg[data-value="' + p + '"]');
      SPEC_EXPECT.ratios.forEach((a) => {
        click(d, '#aspectFold .fold-body .seg[data-value="' + a + '"]');
        const m = /(\d+)×(\d+)/.exec(px.textContent);
        const got = m ? m[1] + 'x' + m[2] : 'n/a';
        if (got !== SPEC_EXPECT.dims[p][a]) badD.push(p + '/' + a + ': ' + got + ' ≠ ' + SPEC_EXPECT.dims[p][a]);
      });
    });
    assert(badD.length === 0, 'dimsForResolution×syncResPx: ' + (SPEC_EXPECT.presets.length * SPEC_EXPECT.ratios.length) + ' 组合全与 spec.py 一致' + (badD.length ? ' — ' + badD.slice(0, 4).join(' | ') : ''));
    /* 旧参数迁移路径之外的交叉校验：非 16:9 走短边换算（0.6M 短边 608 → 4:3 = 832×608） */
    click(d, '#resFold .fold-body .seg[data-value="0.6"]');
    click(d, '#aspectFold .fold-body .seg[data-value="4:3"]');
    assert(/832×608/.test(px.textContent), '4:3 + 0.6M → 832×608（非 16:9 短边换算路径）');
    dom.window.close();
  }

  /* ============ loadEngines / toggleEngineMenu / 引擎切换 ============ */
  console.log('[engines]');
  const ENG = [
    { name: 'comfy', display_name: '本地 · Comfy 内核', external: false, implemented: true, active: true },
    { name: 'vllm-omni', display_name: '远程 · vllm-omni', external: true, implemented: true, active: false },
    { name: 'diffusers', display_name: '本地 · diffusers', external: false, implemented: false, active: false }
  ];
  {
    const requests = [];
    const { dom, errors } = boot('t2v', { engines: { engines: ENG, locked: false }, requests });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'engines: init no errors: ' + errors.join(' | '));
    assert(d.querySelector('#engineText').textContent === 'ENGINE: 本地 · Comfy 内核', 'loadEngines 写入当前引擎显示名');
    assert(!d.querySelector('#engineDot').classList.contains('external'), 'loadEngines: 本地引擎不打 external 点');
    const items = [...d.querySelectorAll('#engineList .engine-item')];
    assert(items.length === 3, 'loadEngines 渲染 3 个引擎项');
    assert(items[0].classList.contains('on') && items[0].getAttribute('aria-checked') === 'true' && !items[0].disabled, '当前引擎 on + checked + 可点');
    assert(items[2].classList.contains('off') && items[2].disabled && items[2].textContent.includes('未实现'), '未实现引擎 off + disabled + 彽标');
    assert(items[1].querySelector('.ei-tag').textContent === '外部服务' && items[0].querySelector('.ei-tag').textContent === '本地进程内', '外部/本地标签分流');
    assert(d.querySelector('#engineNote').textContent.includes('默认「本地 · diffusers」'), '未锁定时的引擎说明');
    click(d, '.eng-switch');
    assert(d.querySelector('#engineMenu').classList.contains('open') && d.querySelector('#engineSwitch').getAttribute('aria-expanded') === 'true', 'toggleEngineMenu 开合 + aria-expanded');
    mclick(dom, items[1]);
    await sleep(60);
    const sw = requests.filter((r) => r.url === '/api/engine/switch');
    assert(sw.length === 1 && JSON.parse(sw[0].body).backend === 'vllm-omni', '切换只 POST 引擎名');
    assert(!d.querySelector('#engineMenu').classList.contains('open') && d.querySelector('#engineSwitch').getAttribute('aria-expanded') === 'false', '切换成功后收菜单');
    mclick(dom, items[2]);
    await sleep(60);
    assert(requests.filter((r) => r.url === '/api/engine/switch').length === 1, '未实现引擎无切换监听，不会发请求');
    click(d, '.eng-switch');
    assert(d.querySelector('#engineMenu').classList.contains('open'), '菜单可再次展开');
    click(d, '#stageArea');
    assert(!d.querySelector('#engineMenu').classList.contains('open'), '点外部兼关闭引擎菜单');
    dom.window.close();
  }
  {
    /* 外部引擎为当前时的 active 分流 + env 锁定时禁切 + 切换失败 toast */
    const extEngines = { engines: ENG.map((e) => Object.assign({}, e, { active: e.name === 'vllm-omni' })), locked: false };
    const { dom } = boot('t2v', { engines: extEngines });
    await sleep(350);
    const d = dom.window.document;
    assert(d.querySelector('#engineText').textContent === 'ENGINE: 远程 · vllm-omni' && d.querySelector('#engineDot').classList.contains('external'), '外部引擎当前 → 显示名 + external 点');
    dom.window.close();
  }
  {
    const requests = [];
    const { dom } = boot('t2v', { engines: { engines: ENG, locked: true }, requests });
    await sleep(350);
    const d = dom.window.document;
    assert(d.querySelector('#engineNote').textContent.includes('MMH3_INFERENCE_BACKEND 锁定'), 'env 锁定说明');
    click(d, '.eng-switch');
    click(d, '#engineList .engine-item:nth-child(2)');
    await sleep(60);
    assert(requests.filter((r) => r.url === '/api/engine/switch').length === 0, '锁定时不绑切换监听（无 POST）');
    dom.window.close();
  }
  {
    const alerts = [];
    const { dom } = boot('t2v', { engines: { engines: ENG, locked: false }, switchOk: false, alerts });
    await sleep(350);
    const d = dom.window.document;
    click(d, '.eng-switch');
    click(d, '#engineList .engine-item:nth-child(2)');
    await sleep(60);
    assert(toastText(d).includes('引擎切换失败'), 'HTTP 非 2xx → toast 引擎切换失败');
    assert(!d.querySelector('#engineMenu').classList.contains('open'), '切换失败也收菜单');
    assert(alerts.length === 0, '引擎失败路径无原生 alert（#G-25）');
    dom.window.close();
  }

  /* ============ pollTask 状态机（processing → completed / failed）+ premiere ============ */
  console.log('[poll task]');
  {
    const { dom, jsdomErrors } = boot('t2v', {
      storage: { shell: 'theater' },
      submitReply: { id: 't1', status: 'pending' },
      taskFlow: [{ id: 't1', status: 'processing', progress: 42 }, { id: 't1', status: 'completed', result_path: 'outputs/t1.mp4' }]
    });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(200);
    assert(d.querySelector('#genStatus').textContent === '生成中 · 推理执行中', '提交受理 → 生成中');
    assert(d.querySelector('#queueItem').textContent === 'QUEUE 1 · 1', '队列彽标占用');
    assert(d.querySelector('#stageScene').classList.contains('genning'), 'setGenState 上生生成态');
    assert(d.querySelector('#previewShell').classList.contains('opened'), '剧场壳：提交即开幕（premiere）');
    assert(d.querySelector('#revealCard .rc-main').textContent === 'SHOT 01 · 首映', 'premiere 写入揭幕卡文案');
    await sleep(1000);
    assert(d.querySelector('#genStatus').textContent === '生成中 · 42%', 'poll processing → 进度百分比');
    await sleep(1100);
    assert(d.querySelector('#genStatus').textContent === '生成完成 ✓' && d.querySelector('#genStatus').classList.contains('done'), 'poll completed → 完成态');
    const v = d.querySelector('#stageScene video');
    assert(!!v && v.getAttribute('src') === '/outputs/t1.mp4' && v.loop === true && v.muted === true, 'completed → 结果视频回填舞台');
    assert(d.querySelector('#queueItem').textContent === 'QUEUE 0 · 0', 'completed → 队列释放');
    await sleep(1500);
    assert(!d.querySelector('#stageScene').classList.contains('genning'), '完成后延时清除 genning');
    assert(!jsdomErrors.some((e) => /Uncaught/.test(e)), '轮询期间无页面未捕获异常：' + jsdomErrors.join('|'));
    dom.window.close();
  }
  {
    const { dom } = boot('t2v', { taskFlow: [{ id: 't1', status: 'failed', error: '模型文件缺失' }] });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(1300);
    assert(d.querySelector('#genStatus').textContent === '生成失败: 模型文件缺失', 'poll failed → 错误文案透传');
    assert(d.querySelector('#genStatus').classList.contains('done') && d.querySelector('#queueItem').textContent === 'QUEUE 0 · 0', 'failed → done 样式 + 队列释放');
    dom.window.close();
  }

  /* ============ loadProjects / switchProject / 重命名 / 删除 / 一键清空 ============ */
  console.log('[projects]');
  {
    const requests = [];
    const projects = [{ id: 'p1', name: '项目A', shot_count: 2 }, { id: 'p2', name: '项目B', shot_count: 0 }];
    const { dom, errors } = boot('t2v', { projects, requests, promptReply: '改名后', live: { p1: shotsByPage.t2v.slice(), p2: [{ id: 's2a', name: 'B镜头', prompt: 'B提示词', mode: 'text', duration: 5, aspect: '16:9', params: { duration: 5 }, refs: [] }] } });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'projects: init no errors: ' + errors.join(' | '));
    const items = [...d.querySelectorAll('#projList .proj-item')];
    assert(items.length === 2, 'loadProjects 渲染 2 个项目');
    assert(items[0].classList.contains('active') && d.querySelector('#projName').textContent === '项目A', '默认选中列表首项');
    assert(items[0].querySelector('.pi-meta').textContent === '2 shots', 'shot_count 上镜');
    assert(d.querySelector('#projMeta').textContent === '2 SHOTS · 12S', 'loadProjectShots 汇总镜头数与总时长');
    assert(d.querySelector('#totalDurSb').textContent === '总时长 12s', 'updateTotals 同步状态栏');
    /* 键盘可达：Enter 开下拉 */
    d.querySelector('#projSwitch').dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    assert(d.querySelector('#projSwitch').classList.contains('open'), 'projSwitch 键盘 Enter 可展开');
    click(d, '#projList .proj-item:nth-child(2)');
    await sleep(250);
    assert(d.querySelector('#projName').textContent === '项目B' && d.querySelector('#projMeta').textContent === '1 SHOTS · 5S', 'switchProject → 切 p2 镜头列表');
    assert(d.querySelector('#tlSegments .seg.active') && d.querySelector('#promptInput').value === 'B提示词', 'p2 首镜头自动选中并回填提示词');
    click(d, '#projList .proj-item:nth-child(1) .pi-ren');
    await sleep(120);
    const ren = requests.filter((r) => r.url === '/api/projects/p1' && r.method === 'PUT');
    assert(ren.length === 1 && JSON.parse(ren[0].body).name === '改名后', '重命名 PUT 去空白后的新名');
    click(d, '#projList .proj-item:nth-child(2) .pi-del');
    await sleep(120);
    assert(requests.some((r) => r.url === '/api/projects/p2' && r.method === 'DELETE'), '删除项走 DELETE /projects/{id}');
    dom.window.close();
  }
  {
    /* confirm 取消 → 不发删除请求（破坏性操作的安全边界） */
    const requests = [];
    const { dom } = boot('t2v', { requests, confirmReply: false });
    await sleep(350);
    const d = dom.window.document;
    click(d, '#projList .proj-item:nth-child(1) .pi-del');
    await sleep(120);
    assert(requests.filter((r) => r.method === 'DELETE').length === 0, '取消 confirm 不删项目');
    click(d, '#projClear');
    await sleep(120);
    assert(requests.filter((r) => r.url === '/api/projects/clear').length === 0, '取消 confirm 不清库');
    dom.window.close();
  }
  {
    /* 一键清空全部：成功分支重置项目名/时间线/总计 */
    const requests = [];
    const { dom } = boot('t2v', { requests });
    await sleep(350);
    const d = dom.window.document;
    click(d, '#projClear');
    await sleep(200);
    const clr = requests.filter((r) => r.url === '/api/projects/clear');
    assert(clr.length === 1 && JSON.parse(clr[0].body).keep_uploads === false, 'projClear → POST /projects/clear');
    assert(d.querySelector('#projClear').disabled === false && d.querySelector('#projClear').textContent.includes('一键清空全部'), '完成后按钮恢复可用');
    assert(d.querySelector('#projName').textContent === '未命名项目_01', '清空后项目名回默认占位');
    assert(d.querySelectorAll('#projList .proj-item').length === 0, '清空后项目下拉排空');
    assert(d.querySelectorAll('#tlSegments .seg[data-shot]').length === 0, '清空后时间线镜头排空');
    assert(d.querySelector('#totalDurSb').textContent === '总时长 0s', '清空后总时长归零');
    assert(toastText(d).includes('已清空'), '清空结果回显在页内 toast');
    dom.window.close();
  }

  /* ============ addShot + URL 预选（loadProjects prefProject/prefShot） ============ */
  console.log('[add shot]');
  {
    const requests = [];
    const { dom } = boot('t2v', { requests, url: 'http://localhost/?project=p2&shot=s2b',
      projects: [{ id: 'p1', name: '项目A', shot_count: 1 }, { id: 'p2', name: '项目B', shot_count: 2 }],
      live: { p1: shotsByPage.t2v.slice(0, 1), p2: [
        { id: 's2a', name: 'B1', prompt: 'p1', mode: 'text', duration: 4, aspect: '16:9', params: {}, refs: [] },
        { id: 's2b', name: 'B2', prompt: 'p2', mode: 'text', duration: 6, aspect: '1:1', params: { duration: 6, seed: 7 }, refs: [] }
      ] } });
    const d = dom.window.document;
    await sleep(400);
    assert(d.querySelector('#projName').textContent === '项目B', 'URL ?project= 预选项目');
    const act = d.querySelector('#tlSegments .seg.active');
    assert(!!act && act.dataset.id === 's2b', 'URL ?shot= 预选镜头');
    assert(d.querySelector('#seedInput').value === '7', '预选镜头参数回填 seed');
    const ta = d.querySelector('#promptInput');
    ta.value = '新镜头提示词';
    ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    click(d, '#addSeg');
    await sleep(200);
    const post = requests.filter((r) => r.url === '/api/projects/p2/shots' && r.method === 'POST');
    assert(post.length === 1, 'addShot → POST /projects/{id}/shots');
    const nb = JSON.parse(post[0].body);
    assert(nb.name === '新镜头 3' && nb.prompt === '新镜头提示词' && nb.mode === 'text' && nb.duration === 8 && nb.aspect === '16:9', 'addShot 请求体：序号命名 + 当前提示词 + 默认参数');
    const segs = [...d.querySelectorAll('#tlSegments .seg[data-shot]')];
    assert(segs.length === 3 && segs[2].classList.contains('active'), '创建后重拉列表并选中新镜头');
    assert(d.querySelector('#projMeta').textContent === '3 SHOTS · 18S', '新镜头（默认 8s）计入总时长');
    dom.window.close();
  }

  /* ============ doUpload / 首末帧上传 / 配对音轨（上传全链） ============ */
  console.log('[upload]');
  {
    const requests = [];
    const { dom, errors } = boot('i2v', {
      requests,
      uploadReplies: [
        { id: 'aNew', kind: 'image', mime: 'image/png', path: 'assets/new.png', meta: { original_name: '新首帧.png' } },
        { id: 'aLast', kind: 'image', mime: 'image/png', path: 'assets/last.png', meta: { original_name: '新末帧.png' } }
      ]
    });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'upload: init no errors: ' + errors.join(' | '));
    click(d, '.fs-upload[data-slot="first"]');
    assert(d.querySelector('#fsInput').dataset.slot === 'first', 'uploadFrame 记录目标槽位');
    setFiles(dom, d.querySelector('#fsInput'), [mkFile(dom, '新首帧.png')]);
    fire(d, '#fsInput', 'change');
    await sleep(300);
    const up = requests.filter((r) => r.url === '/api/upload');
    assert(up.length === 1 && up[0].body.get('shot_id') === 's1' && up[0].body.get('file').name === '新首帧.png',
      'doUpload multipart 携带 file + shot_id');
    const put = requests.filter((r) => r.url === '/api/shots/s1' && r.method === 'PUT');
    assert(put.length === 1 && JSON.parse(put[0].body).params.i2v.first === 'aNew', '上传后回写 i2v.first 映射（PUT /shots）');
    const thumb = d.querySelector('#fs-first .fs-thumb img');
    assert(!!thumb && thumb.getAttribute('src') === '/assets/new.png', 'renderFrameSlots 用会话内 path 出缩略图');
    click(d, '.p-row .seg[data-value="first_last"]');
    click(d, '.fs-upload[data-slot="last"]');
    setFiles(dom, d.querySelector('#fsInput'), [mkFile(dom, '新末帧.png')]);
    fire(d, '#fsInput', 'change');
    await sleep(300);
    const put2 = requests.filter((r) => r.url === '/api/shots/s1' && r.method === 'PUT');
    assert(put2.length === 2 && JSON.parse(put2[put2.length - 1].body).params.i2v.last === 'aLast', '末帧上传回写 i2v.last');
    assert(requests.filter((r) => r.url === '/api/upload' && r.body.get('paired_with') === null).length === 2, '帧上传不带 paired_with');
    dom.window.close();
  }
  {
    const requests = [];
    const { dom } = boot('r2v', {
      requests,
      uploadReplies: [
        { id: 'aAud', kind: 'audio', mime: 'audio/wav', path: 'assets/t.wav', meta: { original_name: '音轨.wav' } },
        { id: 'aPic1', kind: 'image', mime: 'image/png', path: 'assets/p1.png', meta: { original_name: 'pic1.png' } },
        { id: 'aPic2', kind: 'image', mime: 'image/png', path: 'assets/p2.png', meta: { original_name: 'pic2.png' } }
      ]
    });
    const d = dom.window.document;
    await sleep(350);
    assert(d.querySelectorAll('#refList .rm-item').length === 2, 'r2v 初始 2 个参考项');
    click(d, '#refList .rm-item .rm-pair');
    assert(d.querySelector('#pairAudioInput').dataset.pairedWith === 'v1', 'uploadPairedAudio 暂存配对视频 id');
    setFiles(dom, d.querySelector('#pairAudioInput'), [mkFile(dom, '音轨.wav', 'audio/wav')]);
    fire(d, '#pairAudioInput', 'change');
    await sleep(300);
    const up = requests.filter((r) => r.url === '/api/upload');
    assert(up.length === 1 && up[0].body.get('paired_with') === 'v1', '配对音轨 multipart 带 paired_with');
    assert(d.querySelector('#pairAudioInput').dataset.pairedWith === '', '上传后清空 paired_with 暂存');
    click(d, '.ref-add');
    assert(d.querySelector('#refInput'), 'uploadRefs 入口存在');
    setFiles(dom, d.querySelector('#refInput'), [mkFile(dom, 'pic1.png'), mkFile(dom, 'pic2.png')]);
    fire(d, '#refInput', 'change');
    await sleep(300);
    assert(requests.filter((r) => r.url === '/api/upload').length === 3, '多文件上传逐一发 POST /api/upload');
    const items = [...d.querySelectorAll('#refList .rm-item')];
    assert(items.length === 5, 'renderRefs 重绘 5 个参考项');
    assert(items.some((i) => i.textContent.includes('Audio 2') && i.textContent.includes('（音轨）')), '配对音轨按官方序号打标签');
    assert(d.querySelector('#refImgN').textContent === '2' && d.querySelector('#refVidN').textContent === '1' && d.querySelector('#refAudN').textContent === '2', '分类计数刷新 2/1/2');
    const chips = [...d.querySelectorAll('#tagChips .tg-chip')].map((c) => c.textContent);
    assert(chips.join(',') === '<Video 1>,<Audio 1>,<Audio 2>,<Picture 1>,<Picture 2>', '标签芯片按种类序列生成：' + chips.join(','));
    dom.window.close();
  }
  {
    /* 未选项目/镜头时三个上传入口都应拦截（不发请求，只弹 toast） */
    const requests = [];
    const { dom } = boot('r2v', { requests, projects: [] });
    await sleep(350);
    const d = dom.window.document;
    click(d, '.ref-add');
    assert(toastText(d).includes('请先选择项目与镜头'), 'uploadRefs 无镜头守卫');
    assert(requests.filter((r) => r.url === '/api/upload').length === 0, '守卫路径不上传');
    dom.window.close();
  }
  {
    const requests = [];
    const { dom } = boot('i2v', { requests, projects: [] });
    await sleep(350);
    click(dom.window.document, '.fs-upload[data-slot="first"]');
    assert(toastText(dom.window.document).includes('请先选择项目与镜头'), 'uploadFrame 无镜头守卫');
    assert(requests.filter((r) => r.url === '/api/upload').length === 0, '帧上传守卫路径不上传');
    dom.window.close();
  }

  /* ============ submitGeneration 前置校验与失败分支 ============ */
  console.log('[submit guards]');
  {
    const captured = [], requests = [];
    const oneImg = [{ id: 'sG', name: '有图', prompt: 'p', mode: 'first_frame', duration: 8, aspect: '16:9', params: {}, refs: [{ id: 'a1', kind: 'image', mime: 'image/png', name: 'f1.png' }] }];
    const noImg = [{ id: 'sG', name: '无图', prompt: 'p', mode: 'first_frame', duration: 8, aspect: '16:9', params: {}, refs: [] }];
    const { dom } = boot('i2v', { captured, requests, shots: noImg });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(120);
    assert(toastText(d).includes('首帧模式需先上传首帧图像') && captured.length === 0, '首帧模式缺图 → 拦截提交');
    click(d, '.p-row .seg[data-value="last_frame"]');
    click(d, '#genBtn');
    await sleep(120);
    assert(toastText(d).includes('末帧模式需先上传末帧图像') && captured.length === 0, '末帧模式缺图 → 拦截提交');
    click(d, '.p-row .seg[data-value="first_last"]');
    click(d, '#genBtn');
    await sleep(120);
    assert(toastText(d).includes('首尾帧模式需上传首帧与末帧各一张图像') && captured.length === 0, '首尾帧只一张 → 拦截提交');
    assert(d.querySelector('#queueItem').textContent === 'QUEUE 0 · 0', '被拦截时队列不动');
    assert(d.querySelector('#genStatus').textContent === '就绪', '被拦截时不改生成态');
    dom.window.close();
  }
  {
    /* 后端 4xx 拒绝：错误文案上屏 + 队列释放 */
    const captured = [], requests = [];
    const { dom } = boot('i2v', { captured, requests, shots: oneImgFix(), submitReply: { detail: '模型未就绪' } });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(200);
    assert(captured.length === 1 && requests.some((r) => r.url === '/api/shots/sG' && r.method === 'PUT'), '先 PUT 镜头再 POST 生成');
    assert(d.querySelector('#genStatus').textContent === '提交失败: 模型未就绪' && d.querySelector('#genStatus').classList.contains('done'), '后端 detail 透传到生成态');
    assert(d.querySelector('#queueItem').textContent === 'QUEUE 0 · 0' && d.querySelector('#queueItem').style.fontWeight === '', '失败后队列标记复位');
    dom.window.close();
  }
  {
    /* 网络层异常：走 catch 分支 */
    const { dom } = boot('i2v', { shots: oneImgFix(), submitFail: true });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(200);
    assert(d.querySelector('#genStatus').textContent === '提交失败: 后端连接失败', '提交失败兼底文案（后端不可达）');
    assert(d.querySelector('#queueItem').textContent === 'QUEUE 0 · 0', '网络失败也释放队列');
    dom.window.close();
  }
  {
    const captured = [], requests = [];
    const { dom } = boot('r2v', { captured, requests, shots: [{ id: 'sR0', name: '无参考', prompt: 'p', mode: 'ref', duration: 8, aspect: '16:9', params: {}, refs: [] }] });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(120);
    assert(toastText(d).includes('多模态参考模式需要至少 1 个参考素材') && captured.length === 0, 'r2v 零参考 → 拦截提交');
    dom.window.close();
  }
  {
    const captured = [];
    const { dom } = boot('r2v', { captured, shots: [{ id: 'sR1', name: '纯音频', prompt: 'p', mode: 'ref', duration: 8, aspect: '16:9', params: {}, refs: [{ id: 'au1', kind: 'audio', mime: 'audio/wav', name: 'a.wav' }] }] });
    const d = dom.window.document;
    await sleep(350);
    click(d, '#genBtn');
    await sleep(120);
    assert(toastText(d).includes('音频须搭配图像或视频输入') && captured.length === 0, 'r2v 纯音频 → 拦截提交');
    dom.window.close();
  }
  {
    const captured = [];
    const { dom } = boot('t2v', { captured, projects: [] });
    const d = dom.window.document;
    await sleep(350);
    assert(d.querySelectorAll('#tlSegments .seg[data-shot]').length === 0, '无项目时时间线空');
    click(d, '#genBtn');
    await sleep(120);
    assert(toastText(d).includes('请先在项目中选择镜头') && captured.length === 0, '无活跌镜头 → 拦截提交');
    dom.window.close();
  }

  function oneImgFix() {
    return [{ id: 'sG', name: '有图', prompt: 'p', mode: 'first_frame', duration: 8, aspect: '16:9', params: {}, refs: [{ id: 'a1', kind: 'image', mime: 'image/png', name: 'f1.png' }] }];
  }

  /* ============ getActiveParams：时长边界 / 留空不写入 / 档位读取 ============ */
  console.log('[params]');
  {
    const captured = [], requests = [];
    const { dom } = boot('t2v', { captured, requests });
    const d = dom.window.document;
    await sleep(350);
    const putDur = () => {
      const p = requests.filter((r) => r.url === '/api/shots/s1' && r.method === 'PUT');
      return p.length ? JSON.parse(p[p.length - 1].body).duration : null;
    };
    const di = d.querySelector('#durationInput'), ta = d.querySelector('#promptInput');
    ta.value = '测试提示词';
    ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    di.value = '16';
    di.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    click(d, '#genBtn');
    await sleep(200);
    assert(captured.length === 1 && captured[0].params.duration === undefined,
      'duration 16 越界 → params 不携带');
    assert(putDur() === 8, '越界时长 PUT 回退 8s');
    di.value = '3';
    di.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    click(d, '#genBtn');
    await sleep(200);
    assert(captured.length === 2 && captured[1].params.duration === undefined && putDur() === 8,
      'duration 3 越下界 → 丢弃并回退');
    di.value = '15';
    di.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    click(d, '#genBtn');
    await sleep(200);
    assert(captured[2].params.duration === 15 && putDur() === 15, 'duration 15 上界内采纳');
    assert(d.querySelector('.dur-frames').textContent === '·362帧', '15s → 362 帧彽标');
    assert(typeof captured[2].params.seed === 'undefined', '留空 seed 不进 params');
    assert(captured[2].params.steps === 20, '#mainSteps 默认 20 随参数下发');
    assert(typeof captured[2].params.sampler === 'undefined' && typeof captured[2].params.denoise === 'undefined', '高级参数留空不写入');
    d.querySelector('#seedInput').value = '-1';
    d.querySelector('#advSampler').value = 'euler';
    d.querySelector('#advDenoise').value = '0.85';
    click(d, '#genBtn');
    await sleep(200);
    assert(captured[3].params.seed === -1 && captured[3].params.sampler === 'euler' && captured[3].params.denoise === 0.85,
      '负种子/sampler/denoise 均可下传');
    dom.window.close();
  }
  {
    const captured = [];
    const { dom } = boot('i2v', { captured, shots: oneImgFix() });
    const d = dom.window.document;
    await sleep(350);
    click(d, '.p-row .seg[data-value="0.6"]');
    assert(d.querySelector('.p-row .seg.on[data-value="0.6"]'), '分辨率 chip 单选切换');
    click(d, '#genBtn');
    await sleep(200);
    const p = captured[0].params;
    assert(p.resolution === '0.6' && p.size_mode === '0.98M' && p.mode === undefined && captured[0].mode === 'first_frame',
      'i2v 提交体：分辨率/尺寸模式来自 p-row，mode 单独上送');
    dom.window.close();
  }
  {
    const captured = [];
    const { dom } = boot('r2v', { captured });
    const d = dom.window.document;
    await sleep(350);
    click(d, '.ref-size .seg[data-value="match"]');
    click(d, '#genBtn');
    await sleep(200);
    assert(captured[0].params.ref_image_size === 'match', 'r2v ref_image_size 读折叠 chip');
    assert(captured[0].params.scheduler_override === undefined, '留空的 scheduler 不写入');
    dom.window.close();
  }

  /* ============ readbackParams：旧档位迁移 / 脏数据容错 / 跨页跳转 ============ */
  console.log('[readback]');
  {
    const { dom, errors } = boot('i2v', { shots: [
      { id: 'sM', name: '旧档镜头', prompt: 'p', mode: 'first_frame', duration: 8, aspect: '16:9', params: { resolution: '768P', seed: -1, steps: 30 }, refs: [{ id: 'a1', kind: 'image', mime: 'image/png', name: 'f1.png' }] },
      { id: 'sT', name: '跨页镜头', prompt: 't', mode: 'text', duration: 8, aspect: '16:9', params: {}, refs: [] }
    ] });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'readback: init no errors: ' + errors.join(' | '));
    assert(d.querySelector('.p-row .seg.on[data-value="0.98"]'), '旧档位 768P → 回落原生 0.98 chip');
    assert(/1344×768/.test(d.querySelector('#resPx').textContent), '旧档位迁移后像素读数 1344×768');
    assert(d.querySelector('#seedInput').value === '-1', '负种子回填为字符串');
    assert(d.querySelector('#mainSteps').value === '30', 'steps 回填主视图输入框');
    /* 脏 params（JSON 不可解）→ catch 后走默认，不报错 */
    const seg = d.querySelector('#tlSegments .seg[data-shot="0"]');
    seg.dataset.params = '{';
    mclick(dom, seg);
    assert(d.querySelector('#seedInput').value === '' && d.querySelector('.p-row .seg.on[data-value="0.98"]'), '脏 params 不致崩，控件回默认');
    /* 该镜头属其他模式页 → 写 location.href 跳转（载入时自动选中已触发一次，点击再触发一次） */
    const dom2 = boot('i2v', { shots: [{ id: 'sT2', name: '跨页镜头', prompt: 't', mode: 'text', duration: 8, aspect: '16:9', params: {}, refs: [] }] });
    await sleep(350);
    const navBefore = dom2.jsdomErrors.filter((e) => /navigation/i.test(e)).length;
    mclick(dom2.dom, dom2.dom.window.document.querySelector('#tlSegments .seg[data-shot="0"]'));
    await sleep(60);
    assert(navBefore >= 1 && dom2.jsdomErrors.filter((e) => /navigation/i.test(e)).length === navBefore + 1,
      'selectShot 跳模式页 → 写 location.href（jsdom 报 navigation）');
    assert(!dom2.dom.window.document.querySelector('#tlSegments .seg.active'), '跨页镜头不就地选中，而是离开本页');
    dom2.dom.window.close();
    /* i2v 旧值 2K 同理迁移（分辨率 chip + 读数） */
    const dom3 = boot('i2v', { shots: [{ id: 'sK', name: '2K镜头', prompt: 'p', mode: 'first_frame', duration: 8, aspect: '16:9', params: { resolution: '2K' }, refs: [] }] });
    await sleep(350);
    assert(dom3.dom.window.document.querySelector('.p-row .seg.on[data-value="0.98"]'), '旧档位 2K → 0.98');
    dom3.dom.window.close();
    dom.window.close();
  }

  /* ============ runContextIR / playDemo ============ */
  console.log('[prompt tools]');
  {
    const { dom } = boot('t2v');
    const d = dom.window.document;
    await sleep(350);
    const ta = d.querySelector('#promptInput');
    ta.value = '黄昏海岸';
    ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    click(d, '.neg');
    assert(ta.value.indexOf('[Context-IR 优化] 黄昏海岸') === 0 && ta.value.includes('运镜：缓慢推近'), 'runContextIR 在现提示词上拼接优化文案');
    assert(d.querySelector('.neg').textContent === '优化完成 ✓', '.neg 按钮回显完成态');
    assert(d.querySelector('#charCount').textContent.includes('字符'), '优化后字数同步刷新');
    ta.value = '';
    ta.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    click(d, '.neg');
    assert(ta.value.includes('黄昏的海岸线'), '空提示词时用内置示例兼底');
    click(d, '.pb-play');
    assert(d.querySelector('#playbar').classList.contains('playing'), 'playDemo 起播');
    assert(/width 8s linear/.test(d.querySelector('.pb-scrub i').style.transition), 'scrub 动画时长跟随镜头时长');
    const dur = d.querySelector('#durationInput');
    dur.value = '11';
    dur.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    assert(d.querySelector('.dur-frames').textContent === '·277帧', '11s → 277 帧');
    dom.window.close();
  }

  /* ============ LoRA 槽位管理 ============ */
  console.log('[lora]');
  {
    const { dom, errors } = boot('t2v');
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'lora: init no errors: ' + errors.join(' | '));
    assert(d.querySelector('#loraCount').textContent === '0/6', 'LoRA 初始计数 0/6');
    const slot0 = d.querySelector('.lora-slot[data-index="0"]');
    assert(slot0.textContent.includes('未选择') && !slot0.classList.contains('active'), '空槽位显示「未选择」');
    click(d, '.lora-slot-btn[data-slot="2"]');
    const li = d.querySelector('#loraInput');
    assert(typeof li.onchange === 'function', '点槽位按钮挂上文件回调');
    setFiles(dom, li, [mkFile(dom, 'styleA.safetensors', 'application/octet-stream')]);
    fire(d, '#loraInput', 'change');
    await sleep(80);
    const slot2 = d.querySelector('.lora-slot[data-index="2"]');
    assert(slot2.classList.contains('active') && slot2.querySelector('.lora-slot-name').textContent === 'styleA.safetensors', '选中 LoRA 显示文件名');
    assert(slot2.querySelector('.lora-slot-btn').style.display === 'none', '已选槽位隐藏「＋添加」');
    assert(d.querySelector('#loraCount').textContent === '1/6', '计数刷新 1/6');
    const rm = slot2.querySelector('.lora-remove');
    assert(!!rm && rm.style.display === 'block' && rm.textContent.includes('移除'), '动态生成移除按钮');
    mclick(dom, rm);
    await sleep(80);
    assert(d.querySelector('#loraCount').textContent === '0/6' && !d.querySelector('.lora-slot[data-index="2"]').classList.contains('active'), '移除后回到未选择');
    dom.window.close();
  }

  /* ============ 舞台显示控制（标签 / 右下角提示 / 自定义文案） ============ */
  console.log('[stage overlay]');
  {
    const { dom, errors } = boot('t2v');
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'stage overlay: init no errors: ' + errors.join(' | '));
    assert(d.body.classList.contains('ctrl-hide-text') && !d.body.classList.contains('ctrl-hide-tags'), '默认：标签 ON / 右下角提示 OFF');
    const hint = d.querySelector('#stageHint');
    assert(typeof hint._default === 'string' && hint._default.length > 0, '记录默认提示文案：' + hint._default);
    const tagsOpt = d.querySelector('.app-opt[data-app="stagetags"]');
    click(d, '.app-opt[data-app="stagetags"]');
    assert(d.body.classList.contains('ctrl-hide-tags') && tagsOpt.querySelector('.ao-desc').textContent === 'OFF', '关左上标签 → body 类 + OFF');
    click(d, '.app-opt[data-app="stagetags"]');
    assert(!d.body.classList.contains('ctrl-hide-tags') && tagsOpt.querySelector('.ao-desc').textContent === 'ON', '再点恢复 ON');
    click(d, '.app-opt[data-app="stagehint"]');
    assert(!d.body.classList.contains('ctrl-hide-text'), '开右下角提示 → 去掉隐藏类');
    const wm = d.querySelector('#stageWatermarkInput');
    wm.value = '© 2026 MM·H3';
    wm.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    assert(hint.textContent === '© 2026 MM·H3' && hint.title === '自定义水印', '自定义文案写入右下角');
    wm.value = '   ';
    wm.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    assert(hint.textContent === hint._default && hint.title === '', '纯空白回落默认文案');
    dom.window.close();
  }

  /* ============ loadHistory / escapeHtml / 面板开关 ============ */
  console.log('[history]');
  {
    const { dom, errors } = boot('t2v', { history: [
      { name: '<b>粗体名</b>', shot_name: '', mode: 'text', duration: 8, created_at: '2026-10-01 12:00', result_path: 'outputs/h1.mp4' },
      { name: '普通镜头', shot_name: '', mode: 'ref', duration: 4, created_at: '2026-10-02 09:30', result_path: null }
    ] });
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'history: init no errors: ' + errors.join(' | '));
    assert(d.querySelector('#historyCount').textContent === '2 条', 'loadHistory 计数上屏');
    const items = [...d.querySelectorAll('#historyBody .history-item')];
    assert(items.length === 2, '渲染 2 条历史');
    const nameEl = items[0].querySelector('.hi-name');
    assert(!nameEl.querySelector('b') && nameEl.innerHTML.includes('&lt;b&gt;'), 'escapeHtml 转义历史名，不注入标记');
    assert(!!items[0].querySelector('.history-thumb img'), '有结果路径 → 缩略图');
    assert(!items[1].querySelector('.history-thumb img'), '无结果路径 → 空缩略槽');
    assert(items[1].querySelector('.hi-meta').textContent.includes('ref · 4s'), 'meta 行含模式与时长');
    click(d, '#historyBtn');
    assert(d.querySelector('#historyPanel').classList.contains('open'), '历史库一次点击即开（#G-24 回归）');
    click(d, '#historyClose');
    assert(!d.querySelector('#historyPanel').classList.contains('open'), '关闭按钮收起面板');
    dom.window.close();
  }
  {
    const { dom } = boot('t2v', { history: [] });
    await sleep(350);
    const d = dom.window.document;
    assert(d.querySelector('#historyCount').textContent === '0 条' && !!d.querySelector('#historyBody .history-empty'), '空历史占位');
    dom.window.close();
  }

  /* ============ 首次使用协议确认（合规 P1-1，一次性遮罩） ============ */
  console.log('[agreement]');
  {
    const { dom, errors } = boot('t2v');
    const d = dom.window.document;
    await sleep(350);
    assert(errors.length === 0, 'agreement: init no errors: ' + errors.join(' | '));
    const box = d.querySelector('#mmh3Agreement');
    assert(box.style.display === 'flex', '未同意时全屏遮罩弹出');
    const chk = d.querySelector('#mmh3AgreeChk'), btn = d.querySelector('#mmh3AgreeBtn');
    assert(btn.disabled === true && Number(btn.style.opacity) === 0.5, '未勾选时确认按钮禁用（opacity=' + btn.style.opacity + ' disabled=' + btn.disabled + '）');
    chk.checked = true;
    fire(d, '#mmh3AgreeChk', 'change');
    assert(btn.disabled === false && btn.style.opacity === '1', '勾选后按钮启用');
    mclick(dom, btn);
    assert(box.style.display === 'none', '确认后遮罩收起');
    assert(dom.window.localStorage.getItem('mmh3:agreement:v1') === '2026-09-15', '同意版本写入 localStorage');
    dom.window.close();
  }
  {
    /* 已同意过 → 不再弹罩（与 Playwright beforeEach seed 同一口径） */
    const { dom } = boot('t2v', { storage: { shell: 'pj', theme: 'light' }, agreed: true });
    await sleep(350);
    assert(dom.window.document.querySelector('#mmh3Agreement').style.display === 'none', '已同意会话不重复弹罩');
    dom.window.close();
  }

  console.log('\nRESULT: pass=' + pass + ' fail=' + fail);
  process.exit(fail ? 1 : 0);
})();
