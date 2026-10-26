// Full-page screenshots of every page at desktop + mobile -> build/shots/
// Usage: node shots.js [http://localhost:8788]
const path = require('path');
const fs = require('fs');
const puppeteer = require(path.resolve(__dirname, '../Platform/node_modules/puppeteer-core'));
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ORIGIN = process.argv[2] || 'http://localhost:8788';
const PAGES = ['/', '/consulting/', '/writing/', '/writing/what-my-policy-survey-says-about-ontario-right-now/', '/media/',
  '/policy/', '/policy/ontario-liberal-leadership-2026/', '/policy/more-neighbours-toronto/', '/events/', '/support/',
  '/about/', '/contact/', '/privacy/', '/404.html'];
const VIEWS = [['desktop', 1440, 900], ['wide', 1200, 800], ['laptop', 1024, 800], ['mid', 900, 800], ['tablet', 768, 1024], ['narrow', 600, 900], ['mobile', 390, 844], ['tiny', 320, 568]];
(async () => {
  const out = path.resolve(__dirname, 'build', 'shots'); fs.mkdirSync(out, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--font-render-hinting=none'] });
  const page = await browser.newPage();
  for (const [vname, w, h] of VIEWS) {
    await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 });
    for (const p of PAGES) {
      await page.goto(ORIGIN + p, { waitUntil: 'networkidle0', timeout: 30000 }).catch(e => console.log('warn', p, e.message));
      await page.evaluate(async () => { // trigger lazy images
        await new Promise(res => { let y = 0; const step = () => { window.scrollTo(0, y); y += 800; if (y < document.body.scrollHeight + 800) setTimeout(step, 40); else { window.scrollTo(0, 0); setTimeout(res, 150); } }; step(); });
      });
      const name = (p === '/' ? 'home' : p.replace(/^\/|\/$/g, '').replace(/[\/.]/g, '-')) + '-' + vname + '.png';
      await page.screenshot({ path: path.join(out, name), fullPage: true });
      console.log('shot', name);
    }
  }
  await browser.close();
})();
