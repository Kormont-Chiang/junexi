// 地名典原书块 E2E：fixture 数据 → 古今地名面板搜索 → 断言史为乐辞典块渲染
// 跑前需 dev server + data/toolbooks/diming_clean.jsonl fixture（脚本不管制备与清理）
import puppeteer from 'puppeteer-core';

const BASE = 'http://127.0.0.1:5188';
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

await page.goto(BASE + '/?e2e=' + Date.now(), { waitUntil: 'domcontentloaded', timeout: 30000 });
await sleep(1500);

// 端点直连断言（数据在位）
const api = await page.evaluate(() => fetch('/api/tools/diming/book?q=' + encodeURIComponent('二江')).then(r => r.json()));
t('端点命中 fixture', api.ok && api.total >= 1 && api.items.some(it => it.head === '二江'));

// 面板搜索（与真实用户同路径：输入 → 点查询按钮）
await page.evaluate(() => {
    const inp = document.getElementById('placeInput');
    inp.value = '二江';
    document.querySelector('#tool-place button.btn-primary').click();
});
await sleep(1200);

const block = await page.evaluate(() => {
    const b = document.querySelector('#placeResults .era-book-block');
    if (!b) return null;
    return {
        title: b.querySelector('.era-book-title') ? b.querySelector('.era-book-title').textContent : '',
        cards: b.querySelectorAll('.era-book-item').length,
        firstHead: b.querySelector('.era-book-item .result-card-title') ? b.querySelector('.era-book-item .result-card-title').textContent.trim() : '',
        firstNote: b.querySelector('.era-book-item .result-card-value') ? b.querySelector('.era-book-item .result-card-value').textContent.slice(0, 30) : ''
    };
});
t('原书块渲染', !!block);
if (block) {
    t('标题署名史为乐', block.title.includes('史为乐'));
    t('条目卡 ' + block.cards + ' 张', block.cards >= 1);
    t('词头=二江', block.firstHead.startsWith('二江'));
    console.log('--- 首条 ---');
    console.log(block.firstHead, '|', block.firstNote);
}

// 负例：主库与辞典双无 → 提示语
await page.evaluate(() => {
    const inp = document.getElementById('placeInput');
    inp.value = '不存在xyz';
    document.querySelector('#tool-place button.btn-primary').click();
});
await sleep(1200);
const neg = await page.$eval('#placeResults', el => el.textContent);
t('双无提示', neg.includes('未找到'));

await browser.close();
console.log(`RESULT ${pass}/${pass + fail}`);
process.exit(fail ? 1 : 0);
