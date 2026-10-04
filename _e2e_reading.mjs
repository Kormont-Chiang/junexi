import puppeteer from 'puppeteer-core';
import fs from 'fs';

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

  await page.goto('http://127.0.0.1:5000/?reading=1', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3000));
  await page.evaluate(() => switchTab('reading'));
  // 等列表真正出现(最多 20s), 不赌固定 sleep
  await page.waitForFunction(() => document.querySelectorAll('#rdList .rd-item').length > 0, { timeout: 20000 });
  await new Promise(r => setTimeout(r, 800));

  // 1) 列表载入
  const listState = await page.evaluate(() => document.querySelectorAll('#rdList .rd-item').length);
  console.log('list items:', listState);

  // 2) 选第一篇, 等 PDF 按钮渲染
  await page.evaluate(() => document.querySelector('#rdList .rd-item').click());
  await page.waitForFunction(() => {
    const row = document.getElementById('rdPdfRow');
    return row && (row.querySelectorAll('a').length > 0 || row.textContent.includes('没有 PDF'));
  }, { timeout: 15000 });
  const det = await page.evaluate(() => {
    return {
      detailTitle: (document.querySelector('#rdDetail .map-panel-title') || {}).textContent,
      pdfBtns: [...document.querySelectorAll('#rdPdfRow a')].map(a => ({ t: a.textContent, h: a.getAttribute('href').slice(0, 42) })),
      saveEnabled: !document.getElementById('rdSave').disabled,
    };
  });
  console.log('detail:', JSON.stringify(det, null, 1));

  // 3) 写笔记保存
  await page.evaluate(() => { document.getElementById('rdNote').value = '测试笔记：流民集团与皇权的关系值得注意。'; });
  await page.evaluate(() => document.getElementById('rdSave').click());
  await new Promise(r => setTimeout(r, 2000));
  const save = await page.evaluate(() => document.getElementById('rdStatus').textContent);
  console.log('save status:', save);

  await page.screenshot({ path: String.raw`C:\Users\Lenovo\AppData\Local\Temp\reading.png` });
  console.log('errors:', errors.length ? errors.slice(0, 3) : 'none');
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
