// audit.js — site-wide alignment linter. Reads each page's real grid geometry in Chrome, collects the
// text axes that the layout actually defines (content edges, every grid column start, every grid
// item's content-box edge), then flags text blocks and controls whose left edge sits on none of them,
// text measures whose right edge is neither the shared measure nor their column, and sibling grid
// areas whose headings/descriptions/actions do not share rows. Writes JSON findings and an annotated
// screenshot (red = flagged, faint orange = axes) per page and width, plus a summary.
// Usage: node audit.js <outdir> [baseUrl] [widths,comma-separated]
const path = require('path'); const fs = require('fs');
const puppeteer = require(path.resolve(__dirname, '../Platform/node_modules/puppeteer-core'));
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT = path.resolve(process.argv[2] || 'build/audit');
const BASE = (process.argv[3] || 'http://localhost:8788').replace(/\/$/, '');
const WIDTHS = (process.argv[4] || '1440,1728,390').split(',').map(Number);
const ROUTES = ['/', '/consulting/', '/about/', '/writing/', '/media/', '/policy/', '/policy/ontario-liberal-leadership-2026/', '/events/', '/support/', '/contact/',
  '/writing/what-my-policy-survey-says-about-ontario-right-now/'];
const TOL = 1.5;

const AUDIT = (TOL) => {
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[hidden],.hp,nav.mobile,.skip,svg'); };
  const px = v => parseFloat(v) || 0;
  const pathOf = el => { const parts = []; let e = el; while (e && e !== document.body && parts.length < 4) { let d = e.tagName.toLowerCase(); if (e.id) d += '#' + e.id; else if (e.className && typeof e.className === 'string') d += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.'); parts.unshift(d); e = e.parentElement; } return parts.join(' > '); };
  const abs = el => { const r = el.getBoundingClientRect(); return { left: r.left + scrollX, right: r.right + scrollX, top: r.top + scrollY, bottom: r.bottom + scrollY, width: r.width, height: r.height }; };
  const contentBox = el => { const r = abs(el), s = getComputedStyle(el); return { left: r.left + px(s.paddingLeft) + px(s.borderLeftWidth), right: r.right - px(s.paddingRight) - px(s.borderRightWidth), top: r.top, bottom: r.bottom }; };
  const near = (x, xs) => { let best = null; for (const a of xs) { const d = Math.abs(x - a); if (best === null || d < best.d) best = { axis: a, d }; } return best; };
  const measurePx = parseFloat(getComputedStyle(document.documentElement).fontSize) * 36;

  // 1. axes the layout defines
  const axes = new Set(); const axisSrc = [];
  const addAxis = (x, why) => { const r = Math.round(x * 2) / 2; if (![...axes].some(a => Math.abs(a - r) <= TOL)) { axes.add(r); axisSrc.push({ x: r, why }); } };
  const wrap = document.querySelector('main .wrap, .wrap');
  if (wrap) { const cb = contentBox(wrap); addAxis(cb.left, 'content-left'); addAxis(cb.right, 'content-right'); }
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue;
    const s = getComputedStyle(el);
    if (s.display === 'grid' || s.display === 'inline-grid') {
      const cb = contentBox(el); const cols = s.gridTemplateColumns.split(' ').map(parseFloat).filter(n => !isNaN(n)); const gap = px(s.columnGap);
      let x = cb.left; cols.forEach((w, i) => { addAxis(x, 'grid-col ' + pathOf(el)); x += w; addAxis(x, 'grid-col-end ' + pathOf(el)); x += gap; });
      for (const ch of el.children) { if (!vis(ch)) continue; const c2 = contentBox(ch); addAxis(c2.left, 'grid-item ' + pathOf(ch)); addAxis(c2.right, 'grid-item-right ' + pathOf(ch)); }
    }
  }
  for (const el of document.querySelectorAll('.panel,.embed-box,.notice,.empty,.datebox,.event > div,details')) { if (!vis(el)) continue; const cb = contentBox(el); addAxis(cb.left, 'component ' + pathOf(el)); }
  const AX = [...axes].sort((a, b) => a - b);
  const heroFindings = [];
  const hc = document.querySelector('.hero-copy'), hp = document.querySelector('.hero-photo img'), hw = document.querySelector('.site-header .wrap');
  if (hc && hw) { const cbw = contentBox(hw), l = abs(hc).left; if (Math.abs(l - cbw.left) > TOL) heroFindings.push({ kind: 'hero', path: '.hero-copy', text: 'hero copy left vs header content left', left: +l.toFixed(1), nearestAxis: +cbw.left.toFixed(1), delta: +Math.abs(l - cbw.left).toFixed(1), box: abs(hc) }); }
  if (hp && hw) { const cbw = contentBox(hw), r = abs(hp).right; if (Math.abs(r - cbw.right) > TOL) heroFindings.push({ kind: 'hero', path: '.hero-photo img', text: 'hero image right vs header content right', left: +r.toFixed(1), nearestAxis: +cbw.right.toFixed(1), delta: +Math.abs(r - cbw.right).toFixed(1), box: abs(hp) }); }

  // 2. left edges of text blocks and controls
  const SEL = 'h1,h2,h3,h4,.label,.lede,p,.btn,.more,label,input:not([type=hidden]),.meta,.list .row,.record-row .when,.pager a,dt,dd,.wordmark,.year-head,details summary,.notice,.empty,.consent-note,.tags,.chips';
  const leftFindings = [];
  for (const el of document.querySelectorAll(SEL)) {
    if (!vis(el)) continue;
    if (el.closest('.prose') && !el.matches('.prose > p, .prose > h2, .prose > h3')) continue;      // inset prose internals are intentional
    if (el.closest('.tags, .chips, .share, .article-meta, .social-list') && !el.matches('.tags,.chips')) continue;
    const parent = el.parentElement; const ps = getComputedStyle(parent);
    if ((ps.display === 'flex' || ps.display === 'inline-flex') && ps.flexDirection.startsWith('row')) {   // only the first item of a row sits on an axis
      const first = [...parent.children].find(vis); if (first !== el) continue;
    }
    if (el.matches('.btn') && el.closest('.actions') && [...el.closest('.actions').children].find(vis) !== el) continue;
    const r = abs(el); const n = near(r.left, AX);
    if (!n || n.d > TOL) leftFindings.push({ kind: 'left-edge', path: pathOf(el), text: (el.textContent || '').trim().slice(0, 60), left: +r.left.toFixed(1), top: +r.top.toFixed(0), nearestAxis: n && n.axis, delta: n && +n.d.toFixed(1), box: r });
  }

  // 3. measures: ledes, prose, section intros, entry/record/area paragraphs
  const MEAS = '.lede,.prose,.section-head,.entry p,.record-row p,.feature-post .summary,.signup-grid p,.area p,.work-item-project p,.event p,details.faq p,.record-line';
  const measureFindings = [];
  for (const el of document.querySelectorAll(MEAS)) {
    if (!vis(el)) continue;
    const r = abs(el); const pc = contentBox(el.parentElement); const colW = pc.right - pc.left;
    const okMeasure = Math.abs(r.width - measurePx) <= TOL, okColumn = Math.abs(r.width - colW) <= TOL;
    if (!okMeasure && !okColumn) measureFindings.push({ kind: 'measure', path: pathOf(el), text: (el.textContent || '').trim().slice(0, 60), width: +r.width.toFixed(1), measure: measurePx, column: +colW.toFixed(1), top: +r.top.toFixed(0), box: r });
  }

  // 4. sibling grid rows: headings, descriptions and actions of areas/columns in the same row must share tops
  const rowFindings = [];
  for (const grid of document.querySelectorAll('.area-grid,.cols,.footer-grid,.two-col.equal,.list-cols')) {   // .feature-grid is designed to differ (featured item carries a large image)
    if (!vis(grid)) continue;
    const items = [...grid.children].filter(vis);
    const rows = new Map();
    for (const it of items) { const t = Math.round(abs(it).top / 4) * 4; if (!rows.has(t)) rows.set(t, []); rows.get(t).push(it); }
    for (const [t, group] of rows) {
      if (group.length < 2) continue;
      for (const part of (grid.matches('.feature-grid') ? ['h2,h3'] : ['h2,h3', 'p', '.more,.actions'])) {
        const tops = group.map(it => { const e = it.querySelector(part); return e && vis(e) ? abs(e).top : null; }).filter(v => v !== null);
        if (tops.length >= 2 && Math.max(...tops) - Math.min(...tops) > TOL) rowFindings.push({ kind: 'row', path: pathOf(grid), part, tops: tops.map(v => +v.toFixed(0)), box: abs(grid) });
      }
    }
  }
  // 5. section rhythm: gap between a section-head and the next block, per section (report only)
  const rhythm = [...document.querySelectorAll('.section-head')].map(h => { const nx = h.nextElementSibling; return nx ? +(abs(nx).top - abs(h).bottom).toFixed(0) : null; }).filter(v => v !== null);
  leftFindings.push(...heroFindings);
  return { url: location.href, viewport: innerWidth, documentWidth: document.documentElement.scrollWidth, measurePx, axes: axisSrc, leftFindings, measureFindings, rowFindings, rhythm,
    canela: document.fonts.check('400 40px Canela') };
};

const OVERLAY = (res) => {
  const ns = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(ns, 'svg');
  const w = innerWidth, h = document.documentElement.scrollHeight;
  svg.setAttribute('width', w); svg.setAttribute('height', h); svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  Object.assign(svg.style, { position: 'absolute', left: 0, top: 0, width: w + 'px', height: h + 'px', zIndex: 2147483647, pointerEvents: 'none' });
  const add = (tag, attrs, txt) => { const e = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (txt) e.textContent = txt; svg.appendChild(e); return e; };
  for (const a of res.axes) if (a.x >= 0 && a.x <= w) add('line', { x1: a.x, y1: 0, x2: a.x, y2: h, stroke: '#d66a00', 'stroke-opacity': .35, 'stroke-dasharray': '4 6' });
  let n = 0;
  const mark = (f, color, label) => { n++; const b = f.box; add('rect', { x: b.left - 2, y: b.top - 2, width: b.width + 4, height: b.height + 4, fill: 'none', stroke: color, 'stroke-width': 2 });
    add('text', { x: Math.max(4, b.left - 2), y: Math.max(12, b.top - 6), fill: color, stroke: 'white', 'stroke-width': 3, 'paint-order': 'stroke', 'font-family': 'Arial', 'font-size': 11, 'font-weight': 'bold' }, `${n}. ${label}`); };
  res.leftFindings.forEach(f => mark(f, '#d00', `left ${f.left} vs axis ${f.nearestAxis} (Δ${f.delta})`));
  res.measureFindings.forEach(f => mark(f, '#a0a', `measure ${f.width} (expected ${f.measure} or column ${f.column})`));
  res.rowFindings.forEach(f => mark(f, '#06c', `rows ${f.part}: ${f.tops.join('/')}`));
  add('text', { x: 8, y: 14, fill: '#000', stroke: 'white', 'stroke-width': 3, 'paint-order': 'stroke', 'font-family': 'Arial', 'font-size': 11 }, 'ALIGNMENT AUDIT: red/purple/blue boxes are flagged; orange lines are the axes the layout defines');
  document.documentElement.appendChild(svg);
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--font-render-hinting=none'] });
  const summary = [];
  for (const route of ROUTES) for (const w of WIDTHS) {
    const page = await browser.newPage();
    await page.setViewport({ width: w, height: w < 500 ? 844 : 1000, deviceScaleFactor: 1 });
    const stem = (route === '/' ? 'home' : route.replace(/^\/|\/$/g, '').replace(/[\/.]/g, '-')) + '-' + w;
    try {
      await page.goto(BASE + route, { waitUntil: 'networkidle0', timeout: 30000 });
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(async () => { for (let y = 0; y < document.documentElement.scrollHeight; y += 800) { scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); } scrollTo(0, 0); });
      const res = await page.evaluate(AUDIT, TOL);
      fs.writeFileSync(path.join(OUT, `${stem}-audit.json`), JSON.stringify(res, null, 1));
      await page.evaluate(OVERLAY, res);
      await page.screenshot({ path: path.join(OUT, `${stem}-audit.png`), fullPage: true });
      const n = res.leftFindings.length + res.measureFindings.length + res.rowFindings.length;
      summary.push({ route, width: w, stem, left: res.leftFindings.length, measure: res.measureFindings.length, rows: res.rowFindings.length, overflow: res.documentWidth > w ? res.documentWidth : 0, canela: res.canela, total: n });
      console.log(`${stem}: ${n} findings (left ${res.leftFindings.length}, measure ${res.measureFindings.length}, rows ${res.rowFindings.length})${res.documentWidth > w ? ' OVERFLOW ' + res.documentWidth : ''}`);
    } catch (e) { summary.push({ route, width: w, stem, error: e.message }); console.log('ERROR', stem, e.message); }
    await page.close();
  }
  fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 1));
  const rows = summary.map(s => `<tr><td>${s.route}</td><td>${s.width}</td><td>${s.left ?? ''}</td><td>${s.measure ?? ''}</td><td>${s.rows ?? ''}</td><td>${s.overflow || ''}</td><td>${s.error || ''}</td><td><a href="${s.stem}-audit.png">overlay</a> <a href="${s.stem}-audit.json">json</a></td></tr>`).join('');
  fs.writeFileSync(path.join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>Alignment audit</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:4px 8px}</style><h1>Alignment audit (${new Date().toISOString()})</h1><p>Left-edge findings: text or controls off every axis the layout defines. Measure findings: text blocks whose width is neither the shared measure nor their column. Row findings: sibling grid areas whose headings, descriptions or actions do not share tops.</p><table><tr><th>route</th><th>width</th><th>left</th><th>measure</th><th>rows</th><th>overflow</th><th>error</th><th>files</th></tr>${rows}</table>`);
  await browser.close();
  const total = summary.reduce((a, s) => a + (s.total || 0), 0);
  console.log(`total findings: ${total} -> ${OUT}/index.html`);
})();
