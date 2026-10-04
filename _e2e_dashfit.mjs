import puppeteer from 'puppeteer-core';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  // 模拟她 JX 窗口的自然尺寸
  await page.setViewport({ width: 1400, height: 860 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  await page.goto('http://127.0.0.1:5000/?dash=fit', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3500));

  // 仪表盘激活即默认 tab
  await new Promise(r => setTimeout(r, 1500));
  const r = await page.evaluate(() => {
    const dash = document.getElementById('dashboard');
    const dr = dash.getBoundingClientRect();
    const doc = document.documentElement;
    const panels = [...document.querySelectorAll('#dashboard .panel')].map(p => {
      const pr = p.getBoundingClientRect();
      const head = p.querySelector('.panel-header');
      return {
        name: head ? head.textContent.trim().slice(0, 10) : '?',
        h: Math.round(pr.height),
        innerScroll: p.scrollHeight > p.clientHeight + 2,
      };
    });
    return {
      viewportH: window.innerHeight,
      dashH: Math.round(dr.height),
      dashBottom: Math.round(dr.bottom),
      pageScrollable: doc.scrollHeight > doc.clientHeight + 2,
      overflowHidden: getComputedStyle(dash).overflow === 'hidden',
      panels,
    };
  });
  console.log(JSON.stringify({ ...r, errors: errors.length ? errors.slice(0, 2) : 'none' }, null, 1));
  await page.screenshot({ path: String.raw`C:\Users\Lenovo\AppData\Local\Temp\dash_fit.png` });
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
