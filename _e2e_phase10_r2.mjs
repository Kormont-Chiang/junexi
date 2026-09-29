// 十期二轮优化 E2E：无年份小点/类别优先级/年份分级/年龄/籍贯不匹官职
import puppeteer from 'puppeteer-core';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const errors = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, cond, extra = '') => { cond ? pass++ : fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };

const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1500,950'] });
const page = await browser.newPage();
await page.setCacheEnabled(false);
page.on('dialog', async d => { await d.dismiss(); });
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 150)); });

await page.goto('http://127.0.0.1:5055', { waitUntil: 'networkidle0', timeout: 60000 });
await sleep(1200);

await page.evaluate(() => { switchTab('cbdb'); searchCBDBByName('苏轼'); });
await page.waitForFunction(() => document.getElementById('cbdbResults')?.textContent.includes('共 1 条'), { timeout: 90000 });
await page.evaluate(() => cbdbShowOnMap());
await sleep(7000);
await page.screenshot({ path: '_r2_1_default.png' });

const t1 = await page.evaluate(() => {
  let minor = 0, major = 0, yrShown = 0, yrHidden = 0, alt = 0;
  document.querySelectorAll('.cbdb-traj-node').forEach(n => {
    if (n.classList.contains('minor')) minor++; else major++;
    if (!n.classList.contains('minor') && n.classList.contains('alt')) alt++;
  });
  document.querySelectorAll('.cbdb-traj-wrap').forEach(w => {
    const yr = w.querySelector('.cbdb-traj-yr');
    if (!yr) return;
    const vis = getComputedStyle(yr).display !== 'none';
    vis ? yrShown++ : yrHidden++;
  });
  return { total: document.querySelectorAll('.cbdb-traj-node').length, major, minor, yrShown, yrHidden, alt,
           zoom: chgisMap.getZoom() };
});
check('R1 节点总数 ≥ 24（21 主+小点）', t1.total >= 24, JSON.stringify(t1));
check('R2 有小点（无年份/游历）', t1.minor >= 2, `(${t1.minor})`);
check('R3 低缩放隐藏年份标签', t1.yrHidden >= 15, `(show=${t1.yrShown} hide=${t1.yrHidden} zoom=${t1.zoom})`);

// 放大到 zoom 7 → 年份显示 + 交替 class
await page.evaluate(() => chgisMap.setView(chgisMap.getCenter(), 7));
await sleep(1200);
const t2 = await page.evaluate(() => {
  let yrShown = 0, alt = 0;
  document.querySelectorAll('.cbdb-traj-wrap').forEach(w => {
    const yr = w.querySelector('.cbdb-traj-yr');
    if (yr && getComputedStyle(yr).display !== 'none') yrShown++;
  });
  document.querySelectorAll('.cbdb-traj-node.alt').forEach(() => alt++);
  return { yrShown, alt, zoom: chgisMap.getZoom() };
});
check('R4 放大后年份显示', t2.yrShown >= 15, `(show=${t2.yrShown} zoom=${t2.zoom})`);
check('R5 交替方向节点存在', t2.alt >= 5, `(${t2.alt})`);
await page.screenshot({ path: '_r2_2_zoom7.png' });

// 弹窗：年龄 + 类别优先级（黄州=任职红）
await page.evaluate(() => {
  let target = null;
  window.cbdbPersonLayer?.eachLayer(l => {
    const el = l.getElement?.();
    if (el && el.textContent.includes('1080')) target = l;
  });
  target?.openPopup();
});
await sleep(900);
const popup = await page.evaluate(() => document.querySelector('.leaflet-popup-content')?.textContent || '');
check('R6 弹窗含当时年龄', popup.includes('岁'), popup.slice(0, 150));
check('R7 弹窗含官职', popup.includes('團練'), popup.slice(0, 150));
await page.screenshot({ path: '_r2_3_popup.png' });

// 籍贯行自身不带官职（居住行按年份匹配出官职是正确的，如眉山 1066-69 时任开封推官）
await page.evaluate(() => {
  document.querySelector('.leaflet-popup-close-button')?.click();
  let target = null;
  window.cbdbPersonLayer?.eachLayer(l => {
    const el = l.getElement?.();
    if (el && el.textContent.includes('1037')) target = l;
  });
  target?.openPopup();
});
await sleep(900);
const mjCheck = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('.cbdb-traj-popup-row')];
  const jiguanRow = rows.find(r => r.querySelector('.cbdb-traj-popup-type')?.textContent === '籍贯');
  return {
    hasJiguan: !!jiguanRow,
    jiguanHasOffice: !!jiguanRow?.querySelector('.cbdb-map-popup-office'),
    totalRows: rows.length,
  };
});
check('R8 籍贯行自身无官职（居住行可有）', mjCheck.hasJiguan && !mjCheck.jiguanHasOffice, JSON.stringify(mjCheck));

// 后端验证：籍贯记录 offices=[]
const apiCheck = await page.evaluate(async () => {
  const r = await fetch('/api/cbdb/persons/geojson', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: [3767], with_offices: true })
  });
  const d = await r.json();
  const jiguan = d.features.filter(f => f.properties.addr_type_code === 1);
  const huangzhou = d.features.filter(f => f.properties.place === '黃州' && f.properties.firstyear === 1080);
  return {
    jiguanOfficesEmpty: jiguan.every(f => (f.properties.offices || []).length === 0),
    huangzhouHasOffice: huangzhou.some(f => (f.properties.offices || []).some(o => o.office.includes('團練'))),
  };
});
check('R9 后端：籍贯 offices 为空', apiCheck.jiguanOfficesEmpty);
check('R10 后端：黄州 offices 有團練', apiCheck.huangzhouHasOffice);

console.log(`\n结果: ${pass} 通过, ${fail} 失败`);
console.log('ERRORS:', errors.length ? errors.slice(0, 6) : 'none');
await browser.close();
process.exit(fail ? 1 : 0);
