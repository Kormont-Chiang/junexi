// E2E（puppeteer-core + 系统 Edge，headless）：任务2 地图反查 + 任务3 朝代联动
// 与 _e2e_tasks23.mjs 同一组断言，但自带浏览器实例，不依赖易崩溃的受管浏览器
import puppeteer from 'puppeteer-core';

const BASE = 'http://127.0.0.1:5055';
let pass = 0, fail = 0;
const t = (label, v) => { if (v === true || (v && !v.__err)) { pass++; console.log('[OK  ]', label); } else { fail++; console.log('[FAIL]', label, v && v.__err ? v.__err : v); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
    args: ['--disable-features=msHubApps', '--window-size=1600,900']
});
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900 });
page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 200)));

await page.goto(BASE + '/?e2e=' + Date.now(), { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForFunction(`typeof dynastyKeyForYear === 'function'`, { timeout: 45000 });
console.log('页面就绪');
await sleep(1200);

// 预热：建连 + 坐标缓存
const warmN = await page.evaluate(() => fetch('/api/cbdb/places/nearest?x=112.45&y=34.62').then(r => r.json()).then(d => d.length));
console.log('CBDB 已预热，坐标缓存返回', warmN, '条');

// ── 朝代键单元 ──
const kv = await page.evaluate(() => ({
    k1: dynastyKeyForYear(1086), k2: dynastyKeyForYear(618), k3: dynastyKeyForYear(1127),
    k4: dynastyKeyForYear(907), k5: dynastyKeyForYear(-500), k6: dynastyKeyForYear(8),
    k7: dynastyKeyForYear(1900), k8: CBDB_DYNASTY_NAME_TO_KEY['北宋']
}));
t('1086→song_north', kv.k1 === 'song_north');
t('618→tang', kv.k2 === 'tang');
t('1127→song_south', kv.k3 === 'song_south');
t('907→five_dynasties', kv.k4 === 'five_dynasties');
t('前500→zhou_east', kv.k5 === 'zhou_east');
t('公元8→han_west', kv.k6 === 'han_west');
t('1900→qing', kv.k7 === 'qing');
t('名称兜底 北宋→song_north', kv.k8 === 'song_north');

// 众数优先
await page.evaluate(() => autoSwitchDynastyByYear(960, '唐', true));
await sleep(600);
t('preferName: 960+唐(众数)→tang', await page.evaluate(() => document.querySelector('.dynasty-btn.active')?.dataset.dynasty) === 'tang');
await page.evaluate(() => switchDynasty('none'));
await sleep(400);

// ── 地图 + 反查 ──
await page.evaluate(() => switchTab('map'));
await sleep(1200);
t('反查开关存在', await page.evaluate(() => !!document.getElementById('cbdbRevChip')));
await page.evaluate(() => cbdbToggleReverse());
await sleep(300);
t('反查开启时光标 crosshair', await page.evaluate(() => chgisMap.getContainer().classList.contains('cbdb-rev-on')));
await page.evaluate(() => chgisMap.fire('click', { latlng: L.latLng(34.62, 112.45) }));
let pin = false;
for (let i = 0; i < 12; i++) { await sleep(1000); pin = await page.evaluate(() => !!document.querySelector('.cbdb-rev-pin')); if (pin) break; }
t('点击落下反查图钉', pin === true);
let rows = 0;
for (let i = 0; i < 15; i++) { await sleep(1000); rows = await page.evaluate(() => document.querySelectorAll('.cbdb-map-popup-person').length); if (rows >= 3) break; }
const popupTxt = await page.evaluate(() => (document.querySelector('.leaflet-popup-pane') || { innerText: '' }).innerText || '');
t('弹窗列出附近地名(含洛阳)', /洛/.test(popupTxt));
t('地名候选≥3', rows >= 3);
t('行政层级显示中文标签', /县|府|山|卫/.test(popupTxt));

// ── 闭环：点河南府(明) → CBDB 列表 + 图层联动 ──
await page.evaluate(() => [...document.querySelectorAll('.cbdb-map-popup-person')].find(a => a.getAttribute('onclick').includes('5101'))?.click());
let listTxt = '';
for (let i = 0; i < 12; i++) { await sleep(1000); listTxt = await page.evaluate(() => (document.getElementById('cbdbResults') || { innerText: '' }).innerText || ''); if (listTxt.length > 20 && !/暂无|失败/.test(listTxt)) break; }
t('载入 CBDB 人物列表', listTxt.length > 20 && !/暂无|失败/.test(listTxt));
t('任务3: 河南府存续期联动→ming', await page.evaluate(() => document.querySelector('.dynasty-btn.active')?.dataset.dynasty) === 'ming');

// ── 任务3 E2E：王安石 ──
await page.evaluate(() => { window._cbdbLastPersons = [{ id: 1762, index_year: 1044, birthyear: 1021, deathyear: 1086, dynasty: '北宋', name_chn: '王安石' }]; cbdbShowOnMap(); });
let dy2 = null, orb = false;
for (let i = 0; i < 12; i++) {
    await sleep(1000);
    dy2 = await page.evaluate(() => document.querySelector('.dynasty-btn.active')?.dataset.dynasty || null);
    orb = await page.evaluate(() => !!document.querySelector('.cbdb-orb-marker,.cbdb-orb'));
    if (dy2 === 'song_north' && orb) break;
}
t('任务3: 王安石→song_north', dy2 === 'song_north');
t('人物金珠已标注', orb === true);

await page.screenshot({ path: '_e2e_pp.png' });
console.log('screenshot -> _e2e_pp.png');
await browser.close();
console.log(`\nE2E 结果: ${pass} 通过, ${fail} 失败`);
process.exit(fail ? 1 : 0);
