// R5 E2E：初始视野聚焦密集区 + 全览按钮 + 年份标签屏幕碰撞去重
// 用法: node _e2e_phase10_r5.mjs  （默认 5055；测安装版用 $env:PORT='49318'）
import puppeteer from 'puppeteer-core';
const BASE = 'http://127.0.0.1:' + (process.env.PORT || 5055);
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, cond, extra = '') => { cond ? pass++ : fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };
const errors = [];
const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1500,950'] });
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 1000 });  // 大屏行布局：地图 ~900px 高；800×600 会触发窄屏列布局（地图仅 253px），z>=5 无从谈起
await page.setCacheEnabled(false);
page.on('dialog', async d => { await d.dismiss(); });
page.on('pageerror', e => errors.push(e.message));
await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 60000 });
await sleep(1200);

// T1-T3: 苏轼轨迹（跨海南，大分散样本）
await page.evaluate(() => { switchTab('cbdb'); loadCBDBPersonDetail(3767); });
await page.waitForFunction(() => document.getElementById('cbdbDetailPanel')?.textContent.includes('蘇軾'), { timeout: 90000 });
await page.evaluate(() => {
  [...document.querySelectorAll('#cbdbDetailPanel button')].find(b => b.textContent.includes('人生轨迹'))?.click();
});
// 等轨迹真正渲染出来（安装版 Access 查询时长不稳定，固定 sleep 会假阴性）
await page.waitForFunction(() => (typeof chgisMap !== 'undefined' && !!chgisMap) &&
  document.querySelectorAll('.cbdb-traj-node:not(.minor)').length >= 15, { timeout: 120000 });
await sleep(1500);

const view1 = await page.evaluate(() => {
  const c = chgisMap.getCenter(), z = chgisMap.getZoom();
  const nodes = document.querySelectorAll('.cbdb-traj-node:not(.minor)').length;
  const fitall = document.querySelector('.cbdb-traj-fitall');
  return { lat: c.lat, lng: c.lng, z, nodes, fitall: fitall ? fitall.textContent : null };
});
check('T1 初始视野聚焦密集区(z>=5,中原一带)', view1.z >= 5 && view1.lat > 25 && view1.lat < 38 && view1.lng > 108 && view1.lng < 123, JSON.stringify(view1));
check('T2 全览按钮出现', !!view1.fitall, view1.fitall || 'none');
check('T3 轨迹节点齐(>=15)', view1.nodes >= 15, `nodes=${view1.nodes}`);

// T4: 点全览后视野扩到海南（map bounds 南缘 < 19.5°N 儋州）
await page.evaluate(() => document.querySelector('.cbdb-traj-fitall')?.click());
await page.waitForFunction(() => chgisMap.getBounds().getSouth() < 19.5, { timeout: 30000 });
await sleep(1000);
const view2 = await page.evaluate(() => {
  const b = chgisMap.getBounds();
  return { south: b.getSouth(), north: b.getNorth(), z: chgisMap.getZoom() };
});
check('T4 全览后视野含海南', view2.south < 19.5, JSON.stringify(view2));

// T5: 回到聚焦视野，年份标签无屏幕矩形相交
await page.evaluate(() => {
  // 重新触发聚焦视野：直接再点一次轨迹按钮
  switchTab('cbdb');
  [...document.querySelectorAll('#cbdbDetailPanel button')].find(b => b.textContent.includes('人生轨迹'))?.click();
});
await sleep(6000);
const collide = await page.evaluate(() => {
  const vis = [...document.querySelectorAll('.cbdb-traj-yr')]
    .filter(e => e.offsetParent !== null && e.style.visibility !== 'hidden')
    .map(e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  let hits = 0;
  for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
    const a = vis[i], b = vis[j];
    if (a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y) hits++;
  }
  return { shown: vis.length, hits, z: chgisMap.getZoom() };
});
check('T5 可见标签两两不相交', collide.hits === 0, JSON.stringify(collide));

// T6: 始终点标记仍在
const tags = await page.evaluate(() => ({
  start: !!document.querySelector('.cbdb-traj-node.start'),
  end: !!document.querySelector('.cbdb-traj-node.end'),
}));
check('T6 始终点标记保留', tags.start && tags.end, JSON.stringify(tags));

// T7: 普通人(孟猷 20715) 小数据回归——不炸、无全览按钮也正常
await page.evaluate(() => { window._cbdbLastPersons = [{ id: 20715, index_year: 0, dynasty: '宋' }]; window._cbdbMapLastIds = [20715]; cbdbShowOnMap(); });
// 冷机 Access 查询可能 >20s，固定 sleep 不可靠——轮询等孟猷特征出现（1 主节点+4 小点）
await page.waitForFunction(() => {
  const main = document.querySelectorAll('.cbdb-traj-node:not(.minor)').length;
  const minor = document.querySelectorAll('.cbdb-traj-node.minor').length;
  return main === 1 && minor === 4;
}, { timeout: 90000 });
const normal = await page.evaluate(() => ({
  nodes: document.querySelectorAll('.cbdb-traj-node:not(.minor)').length,
  minors: document.querySelectorAll('.cbdb-traj-node.minor').length,
  fitall: !!document.querySelector('.cbdb-traj-fitall'),
  z: chgisMap.getZoom(),
}));
check('T7 普通人轨迹正常(不炸/全览按钮不误出)', normal.nodes >= 1 && !normal.fitall, JSON.stringify(normal));

// T8: 群体模式回归——清除后全览按钮同步消失
await page.evaluate(() => {
  window._cbdbLastPersons = [{ id: 3767 }, { id: 1762 }];
  window._cbdbMapLastIds = [3767, 1762];
  window._cbdbMapAddrSource = 'bio';
  cbdbPlotGroupOnMap();
});
await page.waitForFunction(() => {
  let markers = 0;
  window.cbdbPersonLayer?.eachLayer(l => { if (l.getLatLng) markers++; });
  return markers > 0 && !document.querySelector('.cbdb-traj-fitall');
}, { timeout: 90000 });
const grp = await page.evaluate(() => ({
  fitallGone: !document.querySelector('.cbdb-traj-fitall'),
  markers: (() => { let n = 0; window.cbdbPersonLayer?.eachLayer(l => { if (l.getLatLng) n++; }); return n; })(),
}));
check('T8 群体模式清除全览按钮+有标注', grp.fitallGone && grp.markers > 0, JSON.stringify(grp));

console.log(`\n结果: ${pass} 通过, ${fail} 失败`);
console.log('ERRORS:', errors.length ? errors.slice(0, 5) : 'none');
await browser.close();
process.exit(fail ? 1 : 0);
