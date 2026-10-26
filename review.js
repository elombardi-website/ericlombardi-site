// review.js — real-browser capture for the visual audit: clean + guide-overlay screenshots,
// per-page metrics (headings, containers, fonts, overflow candidates, failed requests) and the
// open mobile menu as a separate state. Adapted from the v3 capture helper; uses the project's
// existing puppeteer-core + Chrome setup instead of Playwright.
// Usage: node review.js <outdir> [baseUrl]
const path = require('path');
const fs = require('fs');
const puppeteer = require(path.resolve(__dirname, '../Platform/node_modules/puppeteer-core'));
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT = path.resolve(process.argv[2] || 'build/review');
const BASE = (process.argv[3] || 'http://localhost:8788').replace(/\/$/, '');
const ROUTES = ['/', '/consulting/', '/about/', '/writing/', '/media/', '/policy/', '/contact/',
  '/writing/what-my-policy-survey-says-about-ontario-right-now/'];
const EXTRA = ['/', '/consulting/', '/writing/', '/contact/'];
const WIDTHS = { base: [[1440, 1000], [390, 844]], extra: [[768, 1024], [320, 900]] };

const MEASURE = () => {
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const info = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
    return { tag: el.tagName, id: el.id, classes: String(el.className || ''), text: text.slice(0, 120), x: r.x + scrollX, y: r.y + scrollY, width: r.width, height: r.height, right: r.right + scrollX,
      fontFamily: s.fontFamily, fontSize: s.fontSize, fontWeight: s.fontWeight, lineHeight: s.lineHeight, marginTop: s.marginTop, marginBottom: s.marginBottom, paddingLeft: s.paddingLeft, paddingRight: s.paddingRight }; };
  const heads = [...document.querySelectorAll('h1,h2,h3,h4')].filter(visible).map(info);
  const containers = [...document.querySelectorAll('.wrap,.hero-shell')].filter(visible).map(info);
  const controls = [...document.querySelectorAll('main label,main input,main button,main .btn')].filter(visible).slice(0, 120).map(info);
  const overflowCandidates = [...document.querySelectorAll('body *')].filter(el => { if (!visible(el)) return false; const r = el.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1; }).slice(0, 40).map(info);
  return { url: location.href, title: document.title, viewport: { width: innerWidth, height: innerHeight }, documentWidth: document.documentElement.scrollWidth, documentHeight: document.documentElement.scrollHeight,
    headings: heads, containers, controls, overflowCandidates,
    fonts: [...document.fonts].map(f => ({ family: f.family, weight: f.weight, style: f.style, status: f.status })),
    canelaCheck: document.fonts.check('400 40px Canela'), manropeCheck: document.fonts.check('500 16px Manrope'),
    brokenImages: [...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => ({ src: i.currentSrc || i.src, alt: i.alt })) };
};
const GUIDES = (m) => {
  const ns = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(ns, 'svg');
  const w = m.viewport.width, h = m.documentHeight;
  svg.setAttribute('width', w); svg.setAttribute('height', h); svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('aria-hidden', 'true');
  Object.assign(svg.style, { position: 'absolute', left: '0px', top: '0px', width: w + 'px', height: h + 'px', zIndex: '2147483647', pointerEvents: 'none', overflow: 'hidden' });
  const line = (x1, y1, x2, y2, c, d) => { const e = document.createElementNS(ns, 'line'); for (const [k, v] of Object.entries({ x1, y1, x2, y2, stroke: c, 'stroke-width': 1, 'stroke-dasharray': d })) e.setAttribute(k, String(v)); svg.appendChild(e); };
  const text = (x, y, s, c) => { const t = document.createElementNS(ns, 'text'); t.setAttribute('x', Math.max(3, Math.min(w - 160, x))); t.setAttribute('y', Math.max(13, y)); t.setAttribute('fill', c); t.setAttribute('stroke', 'white'); t.setAttribute('stroke-width', '3'); t.setAttribute('paint-order', 'stroke'); t.setAttribute('font-family', 'Arial,sans-serif'); t.setAttribute('font-size', '10'); t.textContent = s; svg.appendChild(t); };
  const axes = new Map();
  for (const b of m.containers) for (const x of [b.x + (parseFloat(b.paddingLeft) || 0), b.right - (parseFloat(b.paddingRight) || 0)]) { const r = Math.round(x); if (r >= 0 && r <= w) axes.set(r, (axes.get(r) || 0) + 1); }
  [...axes.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).forEach(([x]) => { line(x, 0, x, h, '#d66a00', '5 4'); text(x + 3, 28, `text axis x=${x}`, '#9b4700'); });
  m.headings.slice(0, 80).forEach((b, i) => { const x1 = Math.max(0, b.x), x2 = Math.min(w, b.right); if (x2 <= x1) return; line(x1, b.y, x2, b.y, '#0069ba', '3 3'); text(x1 + 3, b.y + 11, `${i + 1}. ${b.tag} x=${Math.round(b.x)} y=${Math.round(b.y)} ${b.fontFamily.split(',')[0].replace(/"/g, '')} ${b.fontSize}`, '#005493'); });
  text(8, 13, 'ALIGNMENT GUIDES: review aids, not confirmed errors', '#1b2934');
  document.documentElement.appendChild(svg);
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--font-render-hinting=none'] });
  const manifest = [];
  for (const route of ROUTES) {
    const sizes = [...WIDTHS.base, ...(EXTRA.includes(route) ? WIDTHS.extra : [])];
    for (const [w, h] of sizes) {
      const page = await browser.newPage();
      const failures = [];
      page.on('requestfailed', q => failures.append ? failures.append(q.url()) : failures.push({ url: q.url(), failure: q.failure() && q.failure().errorText }));
      await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
      await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 });
      const stem = (route === '/' ? 'home' : route.replace(/^\/|\/$/g, '').replace(/[\/.]/g, '-')) + '-' + w;
      try {
        await page.goto(BASE + route, { waitUntil: 'networkidle0', timeout: 30000 });
        const fontReady = await page.evaluate(() => Promise.race([document.fonts.ready.then(() => true), new Promise(r => setTimeout(() => r(false), 10000))]));
        await page.evaluate(async () => { const limit = Math.min(document.documentElement.scrollHeight, 60000); for (let y = 0; y < limit; y += Math.max(innerHeight, 600)) { scrollTo(0, y); await new Promise(r => setTimeout(r, 45)); } await Promise.race([Promise.all([...document.images].map(i => i.decode().catch(() => {}))), new Promise(r => setTimeout(r, 5000))]); scrollTo(0, 0); });
        await new Promise(r => setTimeout(r, 200));
        const m = await page.evaluate(MEASURE);
        m.fontReadyWithinTimeout = fontReady; m.failedRequests = failures;
        await page.screenshot({ path: path.join(OUT, `${stem}-clean.png`), fullPage: true });
        await page.evaluate(GUIDES, m);
        await page.screenshot({ path: path.join(OUT, `${stem}-guides.png`), fullPage: true });
        fs.writeFileSync(path.join(OUT, `${stem}-metrics.json`), JSON.stringify(m, null, 1));
        manifest.push({ route, width: w, stem, captured: true, fontReady, canela: m.canelaCheck, failedRequests: failures.length, overflowCandidates: m.overflowCandidates.length, brokenImages: m.brokenImages.length, documentWidth: m.documentWidth });
        if (route === '/' && w === 390) {   // open mobile menu as a separate state
          await page.evaluate(() => { document.querySelector('#visual-audit-guides, svg[aria-hidden][style*="2147483647"]')?.remove(); document.querySelector('.burger').click(); });
          await new Promise(r => setTimeout(r, 200));
          await page.screenshot({ path: path.join(OUT, `home-390-menu-open.png`), fullPage: false });
          manifest.push({ route: '/ (menu open)', width: w, stem: 'home-390-menu-open', captured: true });
        }
        console.log('captured', stem);
      } catch (e) {
        manifest.push({ route, width: w, stem, captured: false, error: String(e.message) });
        console.log('NOT captured', stem, e.message);
      }
      await page.close();
    }
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 1));
  const rows = manifest.map(r => `<tr><td>${r.route}</td><td>${r.width}</td><td>${r.captured ? 'yes' : 'NO: ' + r.error}</td><td>${r.fontReady ?? ''}</td><td>${r.canela ?? ''}</td><td>${r.failedRequests ?? ''}</td><td>${r.overflowCandidates ?? ''}</td><td>${r.brokenImages ?? ''}</td><td>${r.documentWidth ?? ''}</td><td><a href="${r.stem}-clean.png">clean</a> <a href="${r.stem}-guides.png">guides</a> <a href="${r.stem}-metrics.json">metrics</a></td></tr>`).join('');
  fs.writeFileSync(path.join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>Capture contact sheet</title><style>body{font:14px/1.4 system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:4px 8px}</style><h1>Real-page captures (${new Date().toISOString()})</h1><p>Guides mark container text axes and heading-box tops. They are review aids, not confirmed errors.</p><table><tr><th>route</th><th>width</th><th>captured</th><th>fonts ready</th><th>Canela</th><th>failed req.</th><th>overflow cand.</th><th>broken img</th><th>doc width</th><th>files</th></tr>${rows}</table>`);
  await browser.close();
  console.log(`${manifest.filter(r => r.captured).length}/${manifest.length} captured -> ${OUT}`);
})();
