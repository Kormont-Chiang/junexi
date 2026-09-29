// 普通人轨迹二测：分级文案 + 动态图例 + 数据覆盖 + 苏轼回归
import puppeteer from 'puppeteer-core';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const errors = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, cond, extra = '') => { cond ? pass++ : fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${extra}`); };

const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1500,950'] });
const page = await browser.newPage();
await page.setCacheEnabled(false);
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 120)); });

await page.goto('http://127.0.0.1:5055', { waitUntil: 'networkidle0', timeout: 60000 });
await sleep(1200);

const cases = [
  { id: 24672, label: '馬嚴(小人物)', expectMinToast: true },
  { id: 20715, label: '孟猷(中人物)', expectMinToast: true },
  { id: 199177, label: '張時謹(无年份)', expectMinToast: true },
  { id: 3767, label: '苏轼(回归)', expectMinToast: false },
];

for (const c of cases) {
  const r = await page.evaluate(async (pid) => {
    window._cbdbLastPersons = [{ id: pid }];
    window._cbdbMapLastIds = [pid];
    window._cbdbMapCtx = { year: 0, dynastyName: null, preferName: false };
    await cbdbPlotTrajectory();
    await new Promise(r2 => setTimeout(r2, 4500));
    return {
      toast: document.querySelector('.toast')?.textContent || null,
      legendItems: [...document.querySelectorAll('.cbdb-map-trajlegend-item')].map(x => x.textContent.trim()),
      info: document.querySelector('.cbdb-map-trajlegend-info')?.textContent || null,
      nodes: document.querySelectorAll('.cbdb-traj-node').length,
      major: document.querySelectorAll('.cbdb-traj-node:not(.minor)').length,
    };
  }, c.id);
  console.log(`\n=== ${c.label} ===`);
  console.log('toast:', r.toast);
  console.log('legend:', JSON.stringify(r.legendItems), '| info:', r.info);
  const toastOk = c.expectMinToast
    ? (r.toast.includes('无法') || r.toast.includes('仅 1'))
    : r.toast.includes('人生轨迹：21 个节点');
  check(`${c.label} toast 分级正确`, toastOk);
  check(`${c.label} 图例动态类别`, r.legendItems.length >= 1 && r.legendItems.length <= 9, `(${r.legendItems.length} 项)`);
  await page.screenshot({ path: `_p2_${c.id}.png` });
}

// 数据覆盖行：苏轼应有"无坐标未显示"或纯条数
const su = await page.evaluate(async () => {
  const r = await fetch('/api/cbdb/persons/geojson', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: [3767], addr_source: 'all', with_offices: true })
  });
  return (await r.json()).meta;
});
check('meta 含 addr_total', su.addr_total >= 31, JSON.stringify(su));

console.log(`\n结果: ${pass} 通过, ${fail} 失败`);
console.log('ERRORS:', errors.length ? errors.slice(0, 5) : 'none');
await browser.close();
process.exit(fail ? 1 : 0);
