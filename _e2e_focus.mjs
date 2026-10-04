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
  await page.goto('http://127.0.0.1:5000/?focus=1', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2500));
  await page.evaluate(() => switchTab('map'));
  await new Promise(r => setTimeout(r, 1500));

  const w1 = await page.evaluate(() => document.querySelector('.map-sidebar').getBoundingClientRect().width);

  // 选明朝疆域层 → 侧栏应收窄
  await page.evaluate(() => { document.getElementById('cctsLayerSelect').value = 'ad1582'; cctsSetLayer('ad1582'); });
  await new Promise(r => setTimeout(r, 600));
  const w2 = await page.evaluate(() => document.querySelector('.map-sidebar').getBoundingClientRect().width);

  // 关掉 → 恢复宽
  await page.evaluate(() => { document.getElementById('cctsLayerSelect').value = ''; cctsSetLayer(''); });
  await new Promise(r => setTimeout(r, 600));
  const w3 = await page.evaluate(() => document.querySelector('.map-sidebar').getBoundingClientRect().width);

  // 选朝代轮廓 → 也收窄
  await page.evaluate(() => { const b = document.querySelector('.dynasty-btn[data-dynasty]:not([data-dynasty="none"])'); if (b) b.click(); });
  await new Promise(r => setTimeout(r, 800));
  const w4 = await page.evaluate(() => ({ w: document.querySelector('.map-sidebar').getBoundingClientRect().width, cls: document.querySelector('.map-layout').className }));
  // 回none
  await page.evaluate(() => { const b = document.querySelector('.dynasty-btn[data-dynasty="none"]'); if (b) b.click(); });
  await new Promise(r => setTimeout(r, 600));
  const w5 = await page.evaluate(() => document.querySelector('.map-sidebar').getBoundingClientRect().width);

  console.log(JSON.stringify({ default: w1, cctsOn: w2, cctsOff: w3, dynastyOn: w4, dynastyOff: w5, errors: errors.slice(0, 3) }));
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
