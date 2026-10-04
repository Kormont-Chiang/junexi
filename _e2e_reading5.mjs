import puppeteer from 'puppeteer-core';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 950 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  await page.goto('http://127.0.0.1:5000/?layout=v5', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3000));
  await page.evaluate(() => switchTab('reading'));
  await page.waitForFunction(() => document.querySelectorAll('#rdStrip .rd-card').length > 0, { timeout: 20000 });
  await page.evaluate(() => document.querySelectorAll('#rdStrip .rd-card')[0].click());
  await page.waitForFunction(() => {
    const f = document.getElementById('rdFrame');
    return f && f.style.display !== 'none';
  }, { timeout: 20000 });
  await new Promise(r => setTimeout(r, 5000)); // 等 PDF 渲染

  const r = await page.evaluate(() => {
    const f = document.getElementById('rdFrame');
    const pdf = f.getBoundingClientRect();
    const note = document.getElementById('rdNote').getBoundingClientRect();
    return {
      frameSrc: f.src.split('/').pop(),
      pdfLeft: Math.round(pdf.left), pdfW: Math.round(pdf.width), pdfH: Math.round(pdf.height),
      noteLeft: Math.round(note.left), noteW: Math.round(note.width),
      leftRight: pdf.left < note.left,          // 关键断言: PDF 在左, 笔记在右
      metaBtns: [...document.querySelectorAll('#rdMeta button')].map(b => b.textContent),
      cardCount: document.querySelectorAll('#rdStrip .rd-card').length,
      cardH: Math.round(document.querySelector('.rd-card').getBoundingClientRect().height),
      saveEnabled: !document.getElementById('rdSave').disabled,
    };
  });
  console.log(JSON.stringify({ ...r, errors: errors.length ? errors.slice(0, 2) : 'none' }, null, 1));
  await page.screenshot({ path: String.raw`C:\Users\Lenovo\AppData\Local\Temp\reading_v5.png` });
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
