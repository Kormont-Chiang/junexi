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

  await page.goto('http://127.0.0.1:5000/?fix=1', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3000));
  await page.evaluate(() => switchTab('reading'));
  await page.waitForFunction(() => document.querySelectorAll('#rdList .rd-item').length > 0, { timeout: 20000 });
  await page.evaluate(() => document.querySelector('#rdList .rd-item').click());
  await page.waitForFunction(() => {
    const row = document.getElementById('rdPdfRow');
    return row && row.querySelectorAll('button').length > 0;
  }, { timeout: 15000 });

  // 点「打开 PDF」-> 应触发 /api/open-url 请求
  let openUrlReq = null;
  page.on('request', r => { if (r.url().includes('/api/open-url')) openUrlReq = r.url(); });
  await page.evaluate(() => document.querySelector('#rdPdfRow button').click());
  await new Promise(r => setTimeout(r, 1500));

  const btns = await page.evaluate(() => [...document.querySelectorAll('#rdPdfRow button')].map(b => b.textContent));
  console.log(JSON.stringify({ btns, openUrlReq, errors: errors.length ? errors.slice(0, 2) : 'none' }, null, 1));
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
