import puppeteer from 'puppeteer-core';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  // dev 5000 端口
  await page.goto('http://127.0.0.1:5000/?recent=1', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3500));

  const r = await page.evaluate(() => {
    const panel = document.getElementById('zotRecentPanel');
    const items = document.querySelectorAll('#zotRecentList .zot-item');
    const first = items[0] ? items[0].textContent.replace(/\s+/g, ' ').slice(0, 50) : null;
    const href = items[0] ? items[0].getAttribute('href') : null;
    return { panel: !!panel, count: items.length, first, href };
  });
  console.log(JSON.stringify({ ...r, errors: errors.slice(0, 3) }, null, 1));
  await page.screenshot({ path: String.raw`C:\Users\Lenovo\AppData\Local\Temp\dash_recent.png`, fullPage: false });
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
