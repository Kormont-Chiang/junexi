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

  await page.goto('http://127.0.0.1:5000/?layout=v6', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3000));
  await page.evaluate(() => switchTab('reading'));
  await page.waitForFunction(() => document.querySelectorAll('#rdStrip .rd-card').length > 0, { timeout: 20000 });
  await page.evaluate(() => document.querySelectorAll('#rdStrip .rd-card')[0].click());
  await page.waitForFunction(() => document.getElementById('rdFrame').style.display !== 'none', { timeout: 20000 });
  await new Promise(r => setTimeout(r, 4000));

  // T1 默认布局: PDF 在左
  const t1 = await page.evaluate(() => {
    const b = document.getElementById('rdBody');
    return { layout: b.dataset.layout, pdfX: document.getElementById('rdPdfPane').getBoundingClientRect().left | 0, noteX: document.getElementById('rdNotePane').getBoundingClientRect().left | 0, resizer: !!document.getElementById('rdResizer') };
  });
  console.log('T1 default row:', JSON.stringify(t1));

  // T2 切到 PDF 在右
  await page.select('#rdLayoutSel', 'row-reverse');
  await new Promise(r => setTimeout(r, 500));
  const t2 = await page.evaluate(() => {
    const b = document.getElementById('rdBody');
    const pdfR = document.getElementById('rdPdfPane').getBoundingClientRect();
    const noteR = document.getElementById('rdNotePane').getBoundingClientRect();
    return { layout: b.dataset.layout, pdfRight: (pdfR.right > noteR.right), noteLeft: (noteR.left < pdfR.left) };
  });
  console.log('T2 row-reverse:', JSON.stringify(t2));

  // T3 切到上下
  await page.select('#rdLayoutSel', 'column');
  await new Promise(r => setTimeout(r, 500));
  const t3 = await page.evaluate(() => {
    const b = document.getElementById('rdBody');
    const pdfB = document.getElementById('rdPdfPane').getBoundingClientRect();
    const noteB = document.getElementById('rdNotePane').getBoundingClientRect();
    return { layout: b.dataset.layout, pdfAbove: (pdfB.bottom < noteB.top), pdfH: pdfB.height | 0, noteH: noteB.height | 0 };
  });
  console.log('T3 column:', JSON.stringify(t3));

  // T4 拖拽调宽(模拟 mousedown/move/up, column 下拖纵向)
  await page.evaluate(() => {
    const rz = document.getElementById('rdResizer');
    const r = rz.getBoundingClientRect();
    const opts = (x, y) => ({ bubbles: true, clientX: x, clientY: y });
    rz.dispatchEvent(new MouseEvent('mousedown', opts(r.left + 5, r.top + 5)));
    document.dispatchEvent(new MouseEvent('mousemove', opts(r.left + 5, r.top + 120)));
    document.dispatchEvent(new MouseEvent('mouseup', opts(r.left + 5, r.top + 120)));
  });
  await new Promise(r => setTimeout(r, 400));
  const t4 = await page.evaluate(() => {
    const saved = localStorage.getItem('jx.rd.ratio');
    const pdfB = document.getElementById('rdPdfPane').getBoundingClientRect();
    return { savedRatio: saved, pdfH: pdfB.height | 0 };
  });
  console.log('T4 drag-resize:', JSON.stringify(t4));

  // T5 持久化: 重新加载页面, 布局与比例应恢复
  await page.goto('http://127.0.0.1:5000/?layout=v6b', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2500));
  await page.evaluate(() => switchTab('reading'));
  await new Promise(r => setTimeout(r, 800));
  const t5 = await page.evaluate(() => ({
    layout: document.getElementById('rdBody').dataset.layout,
    pdfFlex: document.getElementById('rdPdfPane').style.flex,
  }));
  console.log('T5 persisted:', JSON.stringify(t5));
  console.log('errors:', errors.length ? errors.slice(0, 3) : 'none');
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
