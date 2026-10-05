// README 截图 v4：表单态/地图默认态/插件页（无搜索交互）
import puppeteer from 'puppeteer-core';
import fs from 'fs';
const PORT = process.argv[2];
const OUT = 'C:/Users/Lenovo/.kimi_openclaw/workspace/historia-server/docs/screenshots';
fs.mkdirSync(OUT, { recursive: true });
const b = await puppeteer.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-sandbox', '--force-device-scale-factor=1.5'], protocolTimeout: 600000 });
const pg = await b.newPage();
await pg.setViewport({ width: 1440, height: 900 });
await pg.setCacheEnabled(false);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const clickVis = (sel, text) => pg.evaluate((sel, text) => {
  const el = Array.from(document.querySelectorAll(sel)).find(x => x.offsetWidth > 0 && x.textContent.includes(text));
  if (el) { el.click(); return true; } return false;
}, sel, text);

await pg.goto(`http://127.0.0.1:${PORT}/?shots=v4`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await sleep(6000);
await pg.screenshot({ path: `${OUT}/01-dashboard.png` });
console.log('dashboard');

await clickVis('button', 'CBDB');
await sleep(1500);
await clickVis('#cbdb button', '人名');
await sleep(1000);
// 填一个名字让表单显得"活着"（不提交）
await pg.evaluate(() => { const i = document.getElementById('cbdbAdvName'); if (i) { i.value = '王安石'; i.dispatchEvent(new Event('input', { bubbles: true })); } });
await sleep(400);
await pg.screenshot({ path: `${OUT}/02-cbdb.png` });
console.log('cbdb');

await clickVis('button', '史料地图');
await sleep(10000);
await pg.screenshot({ path: `${OUT}/03-map.png` });
console.log('map');

await clickVis('button', '插件');
await sleep(1600);
await pg.screenshot({ path: `${OUT}/04-plugins.png` });
console.log('plugins');
await b.close();
