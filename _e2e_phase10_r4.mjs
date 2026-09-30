// R4 E2E：posted 模式姓名补全 + 详情页轨迹入口 + 导出来源跟随
import puppeteer from 'puppeteer-core';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, cond, extra = '') => { cond ? pass++ : fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
const errors = [];
const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1500,950'] });
const page = await browser.newPage();
await page.setCacheEnabled(false);
page.on('dialog', async d => { await d.dismiss(); });
page.on('pageerror', e => errors.push(e.message));
await page.goto('http://127.0.0.1:5055', { waitUntil: 'networkidle0', timeout: 60000 });
await sleep(1200);

// T1: 纯 posted 模式 feature 带姓名/朝代/生卒
const posted = await page.evaluate(async () => {
  const r = await fetch('/api/cbdb/persons/geojson', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: [3767], addr_source: 'posted' })
  });
  const d = await r.json();
  return {
    n: d.features.length,
    allNamed: d.features.every(f => f.properties.name === '蘇軾'),
    allDynasty: d.features.every(f => f.properties.dynasty === '宋'),
    allBirth: d.features.every(f => f.properties.birth === 1036),
  };
});
check('T1 纯posted模式姓名字段补全', posted.allNamed && posted.allDynasty && posted.allBirth,
  `n=${posted.n} named=${posted.allNamed} dyn=${posted.allDynasty} birth=${posted.allBirth}`);

// T2: 详情页有"人生轨迹"按钮，点击进轨迹
await page.evaluate(() => { switchTab('cbdb'); loadCBDBPersonDetail(3767); });
await page.waitForFunction(() => document.getElementById('cbdbDetailPanel')?.textContent.includes('蘇軾'), { timeout: 90000 });
await sleep(800);
const hasBtn = await page.evaluate(() =>
  [...document.querySelectorAll('#cbdbDetailPanel button')].some(b => b.textContent.includes('人生轨迹')));
check('T2 详情页人生轨迹按钮', hasBtn);
await page.evaluate(() => {
  [...document.querySelectorAll('#cbdbDetailPanel button')].find(b => b.textContent.includes('人生轨迹'))?.click();
});
await sleep(7000);
const traj = await page.evaluate(() => ({
  active: document.querySelector('.page.active')?.id,
  nodes: document.querySelectorAll('.cbdb-traj-node:not(.minor)').length,
  toast: document.querySelector('.toast')?.textContent || null,
}));
check('T3 点击后切地图页+轨迹渲染', traj.active === 'map' && traj.nodes >= 15, JSON.stringify(traj));

// T4: 群体 posted 弹窗显示名字
await page.evaluate(() => {
  switchTab('cbdb');
  window._cbdbLastPersons = [{ id: 3767 }, { id: 1762 }];
  window._cbdbMapLastIds = [3767, 1762];
  window._cbdbMapAddrSource = 'posted';
  cbdbPlotGroupOnMap();
});
await sleep(6000);
await page.evaluate(() => {
  let first = null;
  window.cbdbPersonLayer?.eachLayer(l => { if (!first && l.getLatLng) first = l; });
  first?.openPopup();
});
await sleep(800);
const popup = await page.evaluate(() => document.querySelector('.leaflet-popup-content')?.textContent || '');
check('T4 posted 群体弹窗有名字', popup.includes('蘇軾') || popup.includes('王安石'), popup.slice(0, 80));

// T5: 导出请求带 addr_source（拦截验证）
await page.evaluate(() => {
  window._capturedBody = null;
  const orig = window.fetch;
  window.fetch = function (url, opts) {
    if (url === '/api/cbdb/persons/geojson' && opts?.method === 'POST') window._capturedBody = opts.body;
    return orig.apply(this, arguments);
  };
  window._cbdbLastPersons = [{ id: 3767 }];
  window._cbdbMapAddrSource = 'posted';
  cbdbExportGeoJSON();
});
await sleep(3000);
const body = await page.evaluate(() => JSON.parse(window._capturedBody || '{}'));
check('T5 导出带 addr_source', body.addr_source === 'posted', JSON.stringify(body));

console.log(`\n结果: ${pass} 通过, ${fail} 失败`);
console.log('ERRORS:', errors.length ? errors.slice(0, 5) : 'none');
await browser.close();
process.exit(fail ? 1 : 0);
