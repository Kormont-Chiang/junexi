import puppeteer from 'puppeteer-core';
import fs from 'fs';

const DIR = 'C:\\Users\\Lenovo\\AppData\\Local\\Temp\\jx_audit';
fs.mkdirSync(DIR, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1500, height: 900 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message.slice(0, 120)));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 100)); });

  const port = process.env.JXPORT || '60490';
  await page.goto(`http://127.0.0.1:${port}/?audit=1`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 6000));

  const tabs = await page.evaluate(() => {
    return [...document.querySelectorAll('.tab, .nav-tab, [onclick*="switchTab"], [data-tab]')].map(el => ({
      text: (el.innerText || el.textContent || '').trim().slice(0, 12),
      onclick: el.getAttribute('onclick') || '',
    })).filter(x => x.onclick.includes('switchTab'));
  });
  console.log('TABS:', JSON.stringify(tabs.map(t => t.text)));

  // 逐个切页截图
  const seen = new Set();
  for (const t of tabs) {
    const id = (t.onclick.match(/switchTab\('([^']+)'\)/) || [])[1];
    if (!id || seen.has(id)) continue;
    seen.add(id);
    await page.evaluate((tabId) => { if (typeof switchTab === 'function') switchTab(tabId); }, id);
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: `${DIR}\\tab_${id}.png` });
    console.log(`shot: ${id}`);
  }

  // 仪表盘单独细截: 三栏各一张
  await page.evaluate(() => switchTab('dashboard'));
  await new Promise(r => setTimeout(r, 2000));
  for (const [name, x, w] of [['dash_left', 20, 400], ['dash_mid', 430, 460], ['dash_right', 900, 580]]) {
    await page.screenshot({ path: `${DIR}\\${name}.png`, clip: { x, y: 100, width: w, height: 780 } });
  }
  console.log('dash shots done');

  // 每个 tab 的可见性问题: 检查是否有空面板/错误文案
  const report = await page.evaluate(() => {
    const issues = [];
    document.querySelectorAll('.page').forEach(pg => {
      const id = pg.id;
      const vis = pg.classList.contains('active') || pg.style.display !== 'none';
      const empties = [...pg.querySelectorAll('.panel-body, .panel, [class*=container]')].filter(el =>
        el.children.length === 0 && (el.offsetHeight > 40)).length;
      const errTxt = (pg.innerText.match(/加载失败|出错|错误|undefined|NaN|\[object/g) || []).length;
      if (errTxt) issues.push(`${id}: ${errTxt}处错误文案`);
    });
    return issues;
  });
  console.log('ISSUES:', JSON.stringify(report));
  console.log('ERRORS:', JSON.stringify(errors.slice(0, 8)));
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
