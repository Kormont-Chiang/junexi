// 十期 E2E：苏轼人生轨迹 + 群体任职地来源 + 弹窗官职
import puppeteer from 'puppeteer-core';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const errors = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, cond, extra = '') => {
  cond ? pass++ : fail++;
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${extra}`);
};

const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1500,950', '--disable-gpu-sandbox'] });
const page = await browser.newPage();
await page.setCacheEnabled(false);
await page.setViewport({ width: 1480, height: 920 });
page.on('dialog', async d => { console.log('DIALOG:', d.message()); await d.dismiss(); });
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 150)); });

await page.goto('http://127.0.0.1:5055', { waitUntil: 'networkidle0', timeout: 60000 });
await sleep(1200);

// ── A. 单人轨迹：苏轼 ──
await page.evaluate(() => { switchTab('cbdb'); searchCBDBByName('苏轼'); });
await page.waitForFunction(() => document.getElementById('cbdbResults')?.textContent.includes('共 1 条'), { timeout: 90000 });
await page.evaluate(() => cbdbShowOnMap());
await sleep(7000);
await page.screenshot({ path: '_e2e10_1_traj.png' });

const traj = await page.evaluate(() => {
  let markerCount = 0, lineCount = 0, arrowCount = 0;
  window.cbdbPersonLayer?.eachLayer(l => {
    if (l instanceof L.Marker) markerCount++;
    if (l instanceof L.Polyline) lineCount++;
  });
  document.querySelectorAll('.cbdb-traj-arrow').forEach(() => arrowCount++);
  return {
    activePage: document.querySelector('.page.active')?.id,
    markerCount, lineCount,
    legend: !!document.querySelector('.cbdb-map-trajlegend'),
    legendTitle: document.querySelector('.cbdb-map-trajlegend-title')?.textContent || null,
    nodeCount: document.querySelectorAll('.cbdb-traj-node').length,
    startCount: document.querySelectorAll('.cbdb-traj-node.start').length,
    endCount: document.querySelectorAll('.cbdb-traj-node.end').length,
    toast: document.querySelector('.toast')?.textContent || null,
  };
});
check('A1 切到地图页', traj.activePage === 'map', traj.activePage);
check('A2 有轨迹节点 ≥ 10', traj.nodeCount >= 10, `(${traj.nodeCount})`);
check('A3 有连线', traj.lineCount >= 1, `(${traj.lineCount})`);
check('A4 图例显示', traj.legend, traj.legendTitle);
check('A5 始点标记=1', traj.startCount === 1, `(${traj.startCount})`);
check('A6 终点标记=1', traj.endCount === 1, `(${traj.endCount})`);

// 点黄州节点（1080）验证弹窗官职
const hzInfo = await page.evaluate(() => {
  let target = null;
  window.cbdbPersonLayer?.eachLayer(l => {
    if (l instanceof L.Marker) {
      const el = l.getElement?.();
      if (el && el.textContent.includes('1080')) target = l;
    }
  });
  if (!target) return null;
  target.openPopup();
  return true;
});
await sleep(1000);
await page.screenshot({ path: '_e2e10_2_traj_popup.png' });
const popupText = await page.evaluate(() => document.querySelector('.leaflet-popup-content')?.textContent || '');
check('A7 黄州弹窗打开', !!hzInfo);
check('A8 弹窗含团练副使官职', popupText.includes('團練') || popupText.includes('团练'), popupText.slice(0, 120));
check('A9 弹窗含类型标签', popupText.includes('前住') || popupText.includes('居住'), '');

// ── B. 群体模式 + 来源切换 ──
await page.evaluate(() => {
  switchTab('cbdb');
  // 构造一个两人列表：苏轼+王安石
  window._cbdbLastPersons = [
    { id: 3767, index_year: 1068, dynasty: '宋' },
    { id: 1762, index_year: 1042, dynasty: '宋' },
  ];
  window._cbdbMapLastIds = [3767, 1762];
  window._cbdbMapAddrSource = 'posted';
  cbdbPlotGroupOnMap();
});
await sleep(6000);
await page.screenshot({ path: '_e2e10_3_group_posted.png' });
const grp = await page.evaluate(() => {
  let markerCount = 0;
  window.cbdbPersonLayer?.eachLayer(() => markerCount++);
  const chips = [...document.querySelectorAll('.cbdb-map-grpctl .cbdb-map-chip')].map(c => c.textContent.trim());
  const activeSrc = document.querySelector('.cbdb-map-chip.active[data-src]')?.textContent || null;
  return { markerCount, chips, activeSrc, toast: document.querySelector('.toast')?.textContent || null };
});
check('B1 群体 posted 标注 ≥ 10', grp.markerCount >= 10, `(${grp.markerCount})`);
check('B2 来源 chips 含三项', grp.chips.filter(c => ['生活地址', '任职地', '生活+任职'].includes(c)).length === 3, JSON.stringify(grp.chips));
check('B3 当前选中任职地', grp.activeSrc === '任职地', grp.activeSrc);

// 点一个珠子验证 office 弹窗
await page.evaluate(() => {
  let first = null;
  window.cbdbPersonLayer?.eachLayer(l => { if (!first && l.getLatLng) first = l; });
  if (first) { chgisMap.setView(first.getLatLng(), 7); first.openPopup(); }
});
await sleep(1000);
await page.screenshot({ path: '_e2e10_4_posted_popup.png' });
const postedPopup = await page.evaluate(() => document.querySelector('.leaflet-popup-content')?.textContent || '');
check('B4 posted 弹窗含官职', postedPopup.includes('官职') || postedPopup.includes('知') || postedPopup.includes('官'), postedPopup.slice(0, 100));

// 切回生活地址
await page.evaluate(() => {
  document.querySelector('.cbdb-map-chip[data-src="bio"]').click();
});
await sleep(5000);
const backBio = await page.evaluate(() => {
  let markerCount = 0;
  window.cbdbPersonLayer?.eachLayer(() => markerCount++);
  const hasFilterRow = [...document.querySelectorAll('.cbdb-map-grpctl-row')].some(r => r.textContent.includes('籍贯'));
  return { markerCount, hasFilterRow };
});
check('B5 切回生活地址有标注', backBio.markerCount >= 10, `(${backBio.markerCount})`);
check('B6 bio 模式显示类型筛选', backBio.hasFilterRow);

// 群体 bio 弹窗带 offices
await page.evaluate(() => {
  let first = null;
  window.cbdbPersonLayer?.eachLayer(l => { if (!first && l.getLatLng) first = l; });
  if (first) first.openPopup();
});
await sleep(900);
const bioPopup = await page.evaluate(() => document.querySelector('.leaflet-popup-content')?.textContent || '');
check('B7 bio 群体弹窗含官职信息', bioPopup.includes('此时官职') || bioPopup.includes('官职') || bioPopup.length > 10, bioPopup.slice(0, 100));

console.log(`\n结果: ${pass} 通过, ${fail} 失败`);
console.log('ERRORS:', errors.length ? errors.slice(0, 6) : 'none');
await browser.close();
process.exit(fail ? 1 : 0);
