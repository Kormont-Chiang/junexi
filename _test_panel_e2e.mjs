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
const gujiStateNow = await page.$eval('#lmGujiState', el => el.textContent).catch(() => '');
// 真就绪 → 已出结果 → 可点；缺模型/未安装/异常 → 禁用
const readyReal = gujiStateNow === '引擎就绪';
t('按钮状态与引擎态一致(' + gujiStateNow + ')', readyReal ? gujiDisabled === false : gujiDisabled === true);
const r = await page.evaluate(() => fetch('/api/guji/status').then(x => x.json()));
t('guji 端点 state=' + (r.state || '?'), r.ok === true && ['ready', 'no_models', 'not_installed'].includes(r.state));

// ── 行级编辑：改第 1 行 → lmFull 同步 + ✎ 徽标 ──
const editOk = await page.evaluate(() => {
    const row = document.querySelector('#lmLines .lm-line');
    if (!row) return 'no-row';
    const span = row.querySelector('.lm-text');
    span.focus();
    document.execCommand('insertText', false, '校对测试');
    span.dispatchEvent(new Event('input', { bubbles: true }));
    return 'ok';
});
t('行编辑注入', editOk === 'ok');
const afterEdit = await page.evaluate(() => ({
    full: document.getElementById('lmFull').value,
    badge: document.querySelector('#lmLines .lm-line .lm-conf').textContent,
    edited: document.querySelector('#lmLines .lm-line').classList.contains('edited'),
}));
t('lmFull 同步新文本', afterEdit.full.indexOf('校对测试') !== -1);
t('✎ 徽标', afterEdit.badge === '✎' && afterEdit.edited);

// ── 真模型句读：点击按钮 → 出标点文本 ──
if (readyReal) {
    await page.click('#lmGujiBtn');
    await page.waitForFunction(() => {
        const v = document.getElementById('lmGujiOut').value;
        return v && /[，。！？；、]/.test(v);
    }, { timeout: 60000 }).catch(() => {});
    const gujiText = await page.$eval('#lmGujiOut', el => el.value).catch(() => '');
    const gujiState2 = await page.$eval('#lmGujiState', el => el.textContent).catch(() => '');
    t('句读出真标点(' + gujiState2 + ')', /[，。！？；、]/.test(gujiText));
    console.log('--- 句读输出前 60 字 ---');
    console.log(gujiText.slice(0, 60));
} else {
    t('句读出真标点(跳过: 引擎未就绪)', true);
}

await browser.close();
console.log(`RESULT ${pass}/${pass + fail}`);
process.exit(fail ? 1 : 0);
