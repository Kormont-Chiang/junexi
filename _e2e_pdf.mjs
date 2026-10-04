import puppeteer from 'puppeteer-core';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--no-sandbox', '--disable-features=msHubApps'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 950 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  await page.goto('http://127.0.0.1:5000/?pdf=1', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3000));
  await page.evaluate(() => switchTab('reading'));
  await page.waitForFunction(() => document.querySelectorAll('#rdList .rd-item').length > 0, { timeout: 20000 });
  await page.evaluate(() => document.querySelector('#rdList .rd-item').click());
  await page.waitForFunction(() => {
    const pane = document.getElementById('rdPdfPane');
    return pane && pane.querySelector('iframe');
  }, { timeout: 15000 });
  await new Promise(r => setTimeout(r, 5000)); // 等 PDF viewer 渲染

  const r = await page.evaluate(() => {
    const f = document.querySelector('#rdPdfPane iframe');
    return { src: f.src, visible: f.offsetHeight > 100 };
  });
  console.log(JSON.stringify({ ...r, errors: errors.length ? errors.slice(0, 2) : 'none' }, null, 1));
  await page.screenshot({ path: String.raw`C:\Users\Lenovo\AppData\Local\Temp\pdf_embed.png` });
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
