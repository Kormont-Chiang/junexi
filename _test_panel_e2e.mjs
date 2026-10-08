// 灵眸 OCR 面板 E2E：puppeteer-core + 系统 Edge headless
// 断言链：页面渲染 → provider 状态 → 上传测试图 → 运行 OCR → 行级结果+全文落位
import puppeteer from 'puppeteer-core';
import path from 'node:path';

const BASE = 'http://127.0.0.1:5188';
const IMG = path.resolve('_panel_test.png');
let pass = 0, fail = 0;
const t = (label, v) => { if (v) { pass++; console.log('[OK  ]', label); } else { fail++; console.log('[FAIL]', label); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
    args: ['--disable-features=msHubApps', '--window-size=1400,900']
});
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 200)));

await page.goto(BASE + '/plugin/lingmu-ocr/page?v=' + Date.now(), { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForSelector('#lmDrop', { timeout: 15000 });
t('面板渲染 #lmDrop', true);

// jx-plugin-page 事件由插件宿主派发；独立通道页面需手动派发（与宿主契约一致）
await page.evaluate(() => { document.dispatchEvent(new CustomEvent('jx-plugin-page')); });
await sleep(800);
const status = await page.$eval('#lmStatus', el => el.textContent).catch(() => '');
t('provider 状态加载: ' + status.slice(0, 40), status.includes('lingmu') || status.includes('灵眸') || status.length > 0);

const input = await page.$('#lmFile');
t('文件输入存在', !!input);
await input.uploadFile(IMG);
await sleep(1500);
const picked = await page.$eval('#lmDrop p', el => el.textContent).catch(() => '');
t('选中反馈: ' + picked.slice(0, 40), picked.includes('已选择'));

const runBtn = await page.$('#lmRun');
t('运行按钮可点', !!runBtn);
await runBtn.click();

await page.waitForFunction(
    () => document.getElementById('lmResult') && document.getElementById('lmResult').style.display !== 'none'
        && document.getElementById('lmLines') && document.getElementById('lmLines').children.length > 0,
    { timeout: 180000, polling: 1000 }
).catch(() => null);
const nLines = await page.$eval('#lmLines', el => el.children.length).catch(() => 0);
const full = await page.$eval('#lmFull', el => el.value).catch(() => '');
t('行级结果 ' + nLines + ' 行', nLines >= 3);
t('全文非空（' + full.length + ' 字）', full.length >= 10);
const headHit = full.includes(u => false) || /地名|辞典|七里川|二江/.test(full);
t('识别含关键词样例', headHit);
console.log('--- 识别前 80 字 ---');
console.log(full.slice(0, 80));

// ── 句读卡（甲言）──
const gujiCardVisible = await page.evaluate(() => {
    const g = document.getElementById('lmGuji');
    return g && getComputedStyle(g).display !== 'none';
});
t('句读卡显示', gujiCardVisible);
await page.waitForFunction(
    () => !/检查中/.test(document.getElementById('lmGujiState').textContent),
    { timeout: 15000 }
).catch(() => {});
const gujiState = await page.$eval('#lmGujiState', el => el.textContent).catch(() => '');
t('状态徽标: ' + gujiState, /就绪|缺模型|未安装|异常|失败/.test(gujiState));
const gujiDisabled = await page.$eval('#lmGujiBtn', el => el.disabled).catch(() => null);
t('缺模型时按钮禁用', gujiDisabled === true);
const r = await page.evaluate(() => fetch('/api/guji/status').then(x => x.json()));
t('guji 端点 state=' + (r.state || '?'), r.ok === true && ['ready', 'no_models', 'not_installed'].includes(r.state));

await browser.close();
console.log(`RESULT ${pass}/${pass + fail}`);
process.exit(fail ? 1 : 0);
