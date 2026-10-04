// CCTS 疆域叠加层 E2E 快速验证 (puppeteer-core + 系统 Edge headless)
import puppeteer from 'puppeteer-core';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  await page.goto('http://127.0.0.1:5000/?ccts=1', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2500));

  // 切到地图 tab
  await page.evaluate(() => { if (typeof switchTab === 'function') switchTab('map'); });
  await new Promise(r => setTimeout(r, 1200));

  // 检查侧栏控件存在
  const hasSelect = await page.evaluate(() => !!document.getElementById('cctsLayerSelect'));
  console.log('select exists:', hasSelect);

  // 选明朝图层
  await page.evaluate(() => {
    const sel = document.getElementById('cctsLayerSelect');
    sel.value = 'ad1582';
    cctsSetLayer('ad1582');
  });
  await new Promise(r => setTimeout(r, 9000)); // 瓦片慢, 等 9s

  // 验证 tileLayer 存在且有瓦片 img 加载
  const state = await page.evaluate(() => {
    const pane = document.querySelector('.leaflet-tile-pane');
    const imgs = pane ? [...pane.querySelectorAll('img')] : [];
    const ccts = imgs.filter(i => (i.src || '').indexOf('file-exists.php') >= 0);
    return {
      totalTiles: imgs.length,
      cctsTiles: ccts.length,
      cctsLoaded: ccts.filter(i => i.complete && i.naturalWidth > 50).length,
      sample: ccts[0] ? ccts[0].src.slice(-60) : null,
    };
  });
  console.log('overlay tiles:', JSON.stringify(state));

  await page.screenshot({ path: String.raw`C:\Users\Lenovo\AppData\Local\Temp\ccts_test.png` });
  console.log('errors:', errors.length ? errors.slice(0, 5) : 'none');
  await browser.close();
})().catch(e => { console.error('E2E FAIL', e.message); process.exit(1); });
