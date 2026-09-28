// E2E 验证：任务2（地图反查）+ 任务3（朝代图层联动）
const CDP = 'http://127.0.0.1:18690';
const fs = await import('fs');
const tabs = await (await fetch(CDP + '/json/list')).json();
let page = tabs.filter(t => t.type === 'page' && !t.url.startsWith('chrome')).pop();
if (!page) { page = await (await fetch(CDP + '/json/new?url=about:blank', { method: 'PUT' })).json(); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0; const pend = {};
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) { pend[m.id](m); delete pend[m.id]; } };
const send = (method, params = {}) => new Promise(res => { const i = ++id; pend[i] = res; ws.send(JSON.stringify({ id: i, method, params })); });
await new Promise(r => { ws.onopen = r; });
const evl = async (expr, awaitP = false) => {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: awaitP, returnByValue: true });
    if (r.result && r.result.exceptionDetails) return { __err: r.result.exceptionDetails.text + ' ' + JSON.stringify(r.result.exceptionDetails.exception || {}) };
    return r.result && r.result.result ? r.result.result.value : JSON.stringify(r.result);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const t = (label, v) => { if (v && !v.__err) { pass++; console.log('[OK  ]', label); } else { fail++; console.log('[FAIL]', label, v && v.__err ? v.__err : v); } };

await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:5055/?e2e=' + Date.now() });
// 就绪轮询：等 app.js 完全加载（外部 CDN 可能拖慢脚本链）
let ready = false;
for (let i = 0; i < 40; i++) {
    await sleep(1000);
    const ty = await evl(`typeof dynastyKeyForYear`);
    if (ty === 'function') { ready = true; console.log(`页面就绪（${i + 1}s）`); break; }
}
if (!ready) { console.log('页面未就绪，放弃'); process.exit(1); }
await sleep(1500);

// 预热：先唤醒 CBDB 连接并加载坐标缓存（Access 冷启动 + 缓存全量加载可达 30s+）
const warm = await evl(`fetch('/api/cbdb/places/nearest?x=112.45&y=34.62').then(r=>r.json()).then(d=>d.length)`, true);
console.log('CBDB 已预热，坐标缓存', warm, '条');

// ── 任务3 单元：年份→朝代键 ──
const k1 = await evl(`dynastyKeyForYear(1086)`);            t('1086→song_north', k1 === 'song_north');
const k2 = await evl(`dynastyKeyForYear(618)`);             t('618→tang', k2 === 'tang');
const k3 = await evl(`dynastyKeyForYear(1127)`);            t('1127→song_south(边界取小span)', k3 === 'song_south');
const k4 = await evl(`dynastyKeyForYear(907)`);             t('907→five_dynasties', k4 === 'five_dynasties');
const k5 = await evl(`dynastyKeyForYear(-500)`);            t('前500→zhou_east', k5 === 'zhou_east');
const k6 = await evl(`dynastyKeyForYear(8)`);               t('公元8→han_west', k6 === 'han_west');
const k7 = await evl(`dynastyKeyForYear(1900)`);            t('1900→qing', k7 === 'qing');
const k8 = await evl(`CBDB_DYNASTY_NAME_TO_KEY['北宋']`);   t('名称兜底 北宋→song_north', k8 === 'song_north');
// 众数优先规则：混合群体平均年(960)虽落北宋，但名称占多数时优先名称
await evl(`autoSwitchDynastyByYear(960, '唐', true)`); await sleep(600);
const kp = await evl(`document.querySelector('.dynasty-btn.active')?.dataset.dynasty||null`);
t('preferName: 960+唐(众数)→tang 非 song_north', kp === 'tang');
await evl(`switchDynasty('none')`); await sleep(400);

// ── 地图页 + 反查开关 ──
await evl(`switchTab('map')`); await sleep(1200);
const chip = await evl(`!!document.getElementById('cbdbRevChip')`);
t('反查开关存在', chip === true);

// 开启反查 → 合成点击洛阳
await evl(`cbdbToggleReverse()`); await sleep(300);
const xhair = await evl(`chgisMap.getContainer().classList.contains('cbdb-rev-on')`);
t('反查开启时光标 crosshair', xhair === true);
await evl(`chgisMap.fire('click', { latlng: L.latLng(34.62, 112.45) })`);
let pin = false;
for (let i = 0; i < 12; i++) { await sleep(1000); pin = await evl(`!!document.querySelector('.cbdb-rev-pin')`); if (pin) break; }
t('点击落下反查图钉', pin === true);
let rows = 0, popupTxt = '';
for (let i = 0; i < 40; i++) {
    await sleep(1000);
    rows = await evl(`document.querySelectorAll('.cbdb-map-popup-person').length`);
    if (rows >= 3) break;
}
popupTxt = await evl(`(document.querySelector('.leaflet-popup-pane')||{innerText:''}).innerText||''`);
t('弹窗列出附近地名(含洛阳)', /洛/.test(popupTxt));
t('地名候选≥3', rows >= 3);

// ── 任务2闭环：点"河南府(明, 1368-1643, addr 5101 同址单条)" → CBDB 人物列表 ──
// 选它是因为坐标唯一（不受同址合并影响）、存续期明确（mid 1505 → 明）
await evl(`[...document.querySelectorAll('.cbdb-map-popup-person')].find(a=>a.getAttribute('onclick').includes('5101'))?.click()`);
let listTxt = '';
for (let i = 0; i < 10; i++) { await sleep(1000); listTxt = await evl(`(document.getElementById('cbdbResults')||{innerText:''}).innerText||''`); if (listTxt.length > 20 && !/暂无|失败/.test(listTxt)) break; }
t('载入 CBDB 人物列表', listTxt.length > 20 && !/暂无|失败/.test(listTxt));
const activeDy = await evl(`document.querySelector('.dynasty-btn.active')?.dataset.dynasty||null`);
t('任务3: 河南府存续期联动→ming', activeDy === 'ming');

// ── 任务3 E2E：王安石(1021-1086, 指数年1044) 群体上地图 ──
await evl(`window._cbdbLastPersons = [{ id: 1762, index_year: 1044, birthyear: 1021, deathyear: 1086, dynasty: '北宋', name_chn: '王安石' }]; cbdbShowOnMap()`);
let dy2 = null, orb = false;
for (let i = 0; i < 12; i++) {
    await sleep(1000);
    dy2 = await evl(`document.querySelector('.dynasty-btn.active')?.dataset.dynasty||null`);
    orb = await evl(`!!document.querySelector('.cbdb-orb-marker,.cbdb-orb')`);
    if (dy2 === 'song_north' && orb) break;
}
t('任务3: 王安石→song_north', dy2 === 'song_north');
t('人物金珠已标注', orb === true);

// 截图
const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync('_e2e_tasks23.png', Buffer.from(shot.result.data, 'base64'));
console.log('screenshot -> _e2e_tasks23.png');

console.log(`\nE2E 结果: ${pass} 通过, ${fail} 失败`);
process.exit(fail ? 1 : 0);
