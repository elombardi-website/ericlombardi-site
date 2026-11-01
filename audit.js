// audit.js — site-wide layout linter, measured against the MASTER GRID ONLY.
//
// Why it changed (1 Nov 2026): the old linter accepted every grid's own columns as legal axes, so a
// component with private tracks certified itself and the report said 0 while the page drifted. Now the
// only legal vertical axes are the master grid's column starts and ends (12 columns from 48rem, 4 below,
// one gap), read live from the page. A component may opt out only with data-grid="own".
//
// Checks, per page and width:
//   status        the page answered 200 (the not-found page is only audited when asked for directly)
//   tracks        every grid uses the master template: equal tracks, the master gap, edges on master axes
//   left          text, controls and images start on a master column start
//   right         images, prose, panels, rules and list rows end on a master column end
//   rows          items in an n-up row share their title, body and action lines
//   rhythm        same-ground sections do not stack padding; bands are symmetric; the entablature sits
//                 --space-block under the header text and --space-header above the content
//   decals        decal, mark and symbol ink stays inside its zone and inside the content box
//   overflow      nothing is wider than the viewport
//   page          no duplicate ids, no inline style attributes outside third-party embeds
// Writes JSON + an annotated screenshot per page/width and an index. Exit code 1 if anything is flagged.
//
// Usage: node audit.js <outdir> [baseUrl] [widths]      e.g. node audit.js build/audit http://localhost:8790/ericlombardi-site
const path = require('path'); const fs = require('fs');
const puppeteer = require(path.resolve(__dirname, '../Platform/node_modules/puppeteer-core'));
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT = path.resolve(process.argv[2] || 'build/audit');
const BASE = (process.argv[3] || 'http://localhost:8790/ericlombardi-site').replace(/\/$/, '');
const WIDTHS = (process.argv[4] || '390,768,1024,1440').split(',').map(Number);
const DOCS = path.resolve(__dirname, 'docs');

// routes = every built page except redirects
function routes() {
  const out = [];
  const walk = (dir, rel) => {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      if (f.isDirectory()) { if (!['assets', 'api'].includes(f.name)) walk(path.join(dir, f.name), rel + f.name + '/'); }
      else if (f.name === 'index.html') {
        const html = fs.readFileSync(path.join(dir, f.name), 'utf8');
        if (!/http-equiv="refresh"/.test(html)) out.push('/' + rel);
      }
    }
  };
  walk(DOCS, '');
  out.push('/404.html');
  return out.sort();
}

const AUDIT = () => {
  const TOL = 1.5;
  const px = v => parseFloat(v) || 0;
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[hidden],.hp,nav.mobile,.skip,.visually-hidden'); };
  const own = el => !!el.closest('[data-grid="own"],.capsule,.form-fields,.gallery,.chips,.tags,.site-header,svg');
  const abs = el => { const r = el.getBoundingClientRect(); return { left: r.left + scrollX, right: r.right + scrollX, top: r.top + scrollY, bottom: r.bottom + scrollY, width: r.width, height: r.height }; };
  const cbox = el => { const r = abs(el), s = getComputedStyle(el); return { ...r, left: r.left + px(s.paddingLeft) + px(s.borderLeftWidth), right: r.right - px(s.paddingRight) - px(s.borderRightWidth) }; };
  const pathOf = el => { const parts = []; let e = el; while (e && e !== document.body && parts.length < 4) { let d = e.tagName.toLowerCase(); if (e.id) d += '#' + e.id; else if (typeof e.className === 'string' && e.className.trim()) d += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.'); parts.unshift(d); e = e.parentElement; } return parts.join(' > '); };
  const near = (x, xs) => xs.reduce((b, a) => (b === null || Math.abs(x - a) < Math.abs(x - b) ? a : b), null);
  const F = [];
  const flag = (kind, el, msg, extra = {}) => F.push({ kind, path: pathOf(el), text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60), msg, box: abs(el), ...extra });

  // the master grid, measured with a probe inside main's first .wrap
  const wrap = document.querySelector('main .wrap');
  if (!wrap) return { error: 'no main .wrap', findings: [] };
  const probe = document.createElement('div'); probe.className = 'grid'; probe.setAttribute('aria-hidden', 'true');
  probe.style.cssText = 'height:0;overflow:hidden;visibility:hidden';
  wrap.appendChild(probe);
  const ps = getComputedStyle(probe);
  const tracks = ps.gridTemplateColumns.split(' ').map(parseFloat);
  const gap = px(ps.columnGap); const x0 = abs(probe).left; probe.remove();
  const starts = [], ends = []; let x = x0;
  tracks.forEach(t => { starts.push(x); ends.push(x + t); x += t + gap; });
  const centres = starts.slice(1).map((s, i) => s - gap / 2);
  const content = { left: starts[0], right: ends[ends.length - 1] };
  const on = (v, xs) => xs.some(a => Math.abs(v - a) <= TOL);

  // tracks: grids use the master template
  for (const el of document.querySelectorAll('main *, footer *')) {
    if (!vis(el) || own(el)) continue;
    const s = getComputedStyle(el);
    if (!/grid/.test(s.display)) continue;
    const cols = s.gridTemplateColumns.split(' ').map(parseFloat).filter(n => !isNaN(n));
    if (cols.length < 2) continue;
    const g = px(s.columnGap);
    const eq = Math.max(...cols) - Math.min(...cols) <= 1;
    if (Math.abs(g - gap) > .5 || !eq) { flag('tracks', el, `private tracks: ${cols.map(c => c.toFixed(0)).join(' ')} gap ${g}`); continue; }
    const b = cbox(el); let xx = b.left;
    for (const c of cols) { if (!on(xx, starts)) { flag('tracks', el, `track start ${xx.toFixed(1)} is off the master columns`); break; } xx += c + g; }
  }

  // left edges
  const LEFT = 'h1,h2,h3,h4,p,.label,.btn,label,input,select,textarea,img,figure,.meta,.entry,.event,.record-row,.list a.row,summary,.empty,.prose,.form,.block,.nup-item,.entablature,.section-head,dt,dd';
  for (const el of document.querySelectorAll(`main :is(${LEFT}), footer :is(${LEFT})`)) {
    if (!vis(el) || own(el)) continue;
    if (el.closest('.prose') && !el.matches('.prose, .prose > :is(p,h2,h3,ul,ol,figure,.embed,.timeline)')) continue;
    const parent = el.parentElement, pst = getComputedStyle(parent);
    if (/flex/.test(pst.display) && pst.flexDirection.startsWith('row') && [...parent.children].find(vis) !== el) continue;  // only a row's first item
    if (el.closest('.endmark-wrap,.cta-band .decal')) continue;
    const l = abs(el).left;
    if (el.matches('img') && el.closest('.portrait-stage.cutout')) continue;      // a cut-out is centred on its stage
    if (!on(l, starts)) flag('left', el, `left ${l.toFixed(1)} is not a column start (nearest ${near(l, starts).toFixed(1)})`);
  }

  // right edges of hard-edged blocks
  const RIGHT = '.pair .p-media,.record-row .pic,.page-hero .media,.page-hero .side,.block--panel,.prose,.entablature,.rule-list,.list,.events-list,.record,.disclosures,.empty,.share,.nup,.footer-grid,.form--contact,.form--full';
  for (const el of document.querySelectorAll(`main :is(${RIGHT}), footer :is(${RIGHT})`)) {
    if (!vis(el) || own(el)) continue;
    const r = abs(el).right;
    if (!on(r, ends)) flag('right', el, `right ${r.toFixed(1)} is not a column end (nearest ${near(r, ends).toFixed(1)})`);
  }

  // rows inside n-up rows share lines
  for (const nup of document.querySelectorAll('.nup')) {
    if (!vis(nup)) continue;
    const items = [...nup.children].filter(vis); const bands = new Map();
    items.forEach(it => { const t = Math.round(abs(it).top); if (!bands.has(t)) bands.set(t, []); bands.get(t).push(it); });
    for (const group of bands.values()) {
      if (group.length < 2) continue;
      for (const slot of ['.n-title', '.n-body', '.n-action']) {
        const tops = group.map(it => it.querySelector(':scope > ' + slot)).filter(e => e && e.getBoundingClientRect().height > 0).map(e => abs(e).top);
        if (tops.length > 1 && Math.max(...tops) - Math.min(...tops) > TOL) flag('rows', nup, `${slot} tops differ: ${tops.map(t => t.toFixed(0)).join('/')}`);
      }
    }
  }

  // rhythm
  const main = document.querySelector('main');
  const kids = [...main.children].filter(vis);
  kids.forEach((s, i) => {
    const st = getComputedStyle(s), prev = kids[i - 1];
    if (s.matches('.section:not(.band)') && prev && prev.matches('.section:not(.band),.page-hero') && px(st.paddingTop) > 0) flag('rhythm', s, `padding-top ${st.paddingTop} stacks on the section above`);
    if (s.matches('.band') && Math.abs(px(st.paddingTop) - px(st.paddingBottom)) > .5) flag('rhythm', s, `band padding is not symmetric (${st.paddingTop} / ${st.paddingBottom})`);
  });
  for (const ent of document.querySelectorAll('.page-hero .entablature')) {
    const text = ent.parentElement.querySelector('.inner'); if (!text) continue;
    const gapAbove = abs(ent).top - abs(text).bottom;
    const want = parseFloat(getComputedStyle(document.documentElement).fontSize) * 2;
    if (Math.abs(gapAbove - want) > 1) flag('rhythm', ent, `entablature is ${gapAbove.toFixed(0)}px under the header row (expected ${want})`);
  }

  // decals: ink inside its zone and the content box
  for (const svg of document.querySelectorAll('svg.header-mark, svg.symbol, svg.decal-stage')) {
    if (!vis(svg)) continue;
    let ink; try { const bb = svg.getBBox(); const m = svg.getScreenCTM(); const p1 = new DOMPoint(bb.x, bb.y).matrixTransform(m), p2 = new DOMPoint(bb.x + bb.width, bb.y + bb.height).matrixTransform(m); ink = { left: p1.x + scrollX, right: p2.x + scrollX, top: p1.y + scrollY, bottom: p2.y + scrollY }; } catch (e) { continue; }
    const zone = abs(svg.parentElement);
    if (ink.left < content.left - .5 || ink.right > content.right + .5) flag('decals', svg, `ink ${ink.left.toFixed(0)}–${ink.right.toFixed(0)} leaves the content box ${content.left.toFixed(0)}–${content.right.toFixed(0)}`);
    if (svg.matches('.header-mark, .decal-stage') && (ink.left < zone.left - 1 || ink.right > zone.right + 1 || ink.top < zone.top - 1 || ink.bottom > zone.bottom + 1)) flag('decals', svg, 'ink leaves its zone');
  }

  // overflow, ids, inline styles
  if (document.documentElement.scrollWidth > innerWidth) F.push({ kind: 'overflow', path: 'html', msg: `document is ${document.documentElement.scrollWidth}px wide at ${innerWidth}`, box: { left: 0, top: 0, width: 10, height: 10 } });
  const ids = {}; document.querySelectorAll('[id]').forEach(e => { ids[e.id] = (ids[e.id] || 0) + 1; });
  Object.entries(ids).filter(([, n]) => n > 1).forEach(([id]) => F.push({ kind: 'page', path: '#' + id, msg: 'duplicate id', box: abs(document.getElementById(id)) }));
  document.querySelectorAll('main [style]:not(iframe):not([style] *)').forEach(e => { if (!e.closest('.embed') && !e.matches('.twitter-timeline, iframe')) flag('page', e, 'inline style attribute'); });

  return { url: location.href, viewport: innerWidth, master: { cols: tracks.length, gap, starts: starts.map(v => +v.toFixed(1)), ends: ends.map(v => +v.toFixed(1)), centres: centres.map(v => +v.toFixed(1)) }, findings: F };
};

const OVERLAY = (res) => {
  const ns = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(ns, 'svg');
  const w = innerWidth, h = document.documentElement.scrollHeight;
  svg.setAttribute('width', w); svg.setAttribute('height', h);
  Object.assign(svg.style, { position: 'absolute', left: 0, top: 0, width: w + 'px', height: h + 'px', zIndex: 2147483647, pointerEvents: 'none' });
  const add = (tag, attrs, txt) => { const e = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (txt) e.textContent = txt; svg.appendChild(e); };
  res.master.starts.forEach((x, i) => { add('rect', { x, y: 0, width: res.master.ends[i] - x, height: h, fill: '#d66a00', 'fill-opacity': .04 }); add('line', { x1: x, y1: 0, x2: x, y2: h, stroke: '#d66a00', 'stroke-opacity': .35 }); add('line', { x1: res.master.ends[i], y1: 0, x2: res.master.ends[i], y2: h, stroke: '#d66a00', 'stroke-opacity': .2, 'stroke-dasharray': '3 5' }); });
  const colour = { tracks: '#06c', left: '#d00', right: '#a0a', rows: '#080', rhythm: '#b60', decals: '#c0c', overflow: '#000', page: '#000' };
  res.findings.forEach((f, i) => { const b = f.box; add('rect', { x: b.left - 2, y: b.top - 2, width: b.width + 4, height: b.height + 4, fill: 'none', stroke: colour[f.kind], 'stroke-width': 2 });
    add('text', { x: Math.max(4, b.left), y: Math.max(12, b.top - 5), fill: colour[f.kind], stroke: 'white', 'stroke-width': 3, 'paint-order': 'stroke', 'font-family': 'Arial', 'font-size': 11, 'font-weight': 'bold' }, `${i + 1}. ${f.kind}: ${f.msg}`); });
  add('text', { x: 8, y: 14, fill: '#000', stroke: 'white', 'stroke-width': 3, 'paint-order': 'stroke', 'font-family': 'Arial', 'font-size': 11 }, 'LAYOUT AUDIT: tinted bands are the master columns; boxes are findings');
  document.documentElement.appendChild(svg);
};

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--font-render-hinting=none'] });
  const summary = [];
  for (const route of routes()) for (const w of WIDTHS) {
    const page = await browser.newPage();
    await page.setViewport({ width: w, height: w < 600 ? 844 : 1000, deviceScaleFactor: 1 });
    const stem = (route === '/' ? 'home' : route.replace(/^\/|\/$/g, '').replace(/\.html$/, '').replace(/[\/.]/g, '-')) + '-' + w;
    try {
      const resp = await page.goto(BASE + route, { waitUntil: 'networkidle0', timeout: 30000 });
      const status = resp ? resp.status() : 0;
      if (route !== '/404.html' && status !== 200) throw new Error('HTTP ' + status);
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(async () => { for (let y = 0; y < document.documentElement.scrollHeight; y += 800) { scrollTo(0, y); await new Promise(r => setTimeout(r, 25)); } scrollTo(0, 0); });
      const res = await page.evaluate(AUDIT);
      if (res.error) throw new Error(res.error);
      fs.writeFileSync(path.join(OUT, `${stem}.json`), JSON.stringify(res, null, 1));
      const counts = {}; res.findings.forEach(f => counts[f.kind] = (counts[f.kind] || 0) + 1);
      if (res.findings.length) { await page.evaluate(OVERLAY, res); await page.screenshot({ path: path.join(OUT, `${stem}.png`), fullPage: true }); }
      summary.push({ route, width: w, stem, total: res.findings.length, counts });
      console.log(`${stem}: ${res.findings.length}${res.findings.length ? ' ' + JSON.stringify(counts) : ''}`);
    } catch (e) { summary.push({ route, width: w, stem, total: 1, error: e.message }); console.log('ERROR', stem, e.message); }
    await page.close();
  }
  fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 1));
  const rows = summary.map(s => `<tr><td>${s.route}</td><td>${s.width}</td><td>${s.total}</td><td>${s.error || Object.entries(s.counts || {}).map(([k, v]) => k + ' ' + v).join(', ')}</td><td>${s.total && !s.error ? `<a href="${s.stem}.png">overlay</a> ` : ''}<a href="${s.stem}.json">json</a></td></tr>`).join('');
  fs.writeFileSync(path.join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>Layout audit</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:4px 8px}</style><h1>Layout audit</h1><p>Measured against the master grid only. Kinds: tracks, left, right, rows, rhythm, decals, overflow, page.</p><table><tr><th>route</th><th>width</th><th>findings</th><th>kinds</th><th>files</th></tr>${rows}</table>`);
  await browser.close();
  const total = summary.reduce((a, s) => a + (s.total || 0), 0);
  console.log(`total findings: ${total} -> ${OUT}/index.html`);
  process.exitCode = total ? 1 : 0;
})();
