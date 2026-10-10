// Enter 检索 E2E：CBDB 人名输入框回车=查询
import puppeteer from 'puppeteer-core';
const BASE = process.env.BASE || 'http://127.0.0.1:5188';
let pass = 0, fail = 0;
const t = (l, v) => { if (v) { pass++; console.log('[OK  ]', l); } else { fail++; console.log('[FAIL]', l); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--disable-features=msHubApps', '--window-size=1400,900']
});
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 160)));
await page.goto(BASE + '/?v=' + Date.now(), { waitUntil: 'domcontentloaded', timeout: 30000 });
await sleep(1200);
// 点导航里的 CBDB 按钮（事件委托，无内联 onclick）
await page.evaluate(() => {
    const b = [...document.querySelectorAll('button.nav-tab')].find(x => /CBDB/i.test(x.textContent || ''));
    if (b) b.click();
});
await sleep(3000);
// 找"查询"按钮所在表单里的文本输入（主查询可能是 textarea，如 cbdbSearchInput）
const probe = await page.evaluate(() => {
    const area = document.getElementById('cbdbSearchArea');
    const btns = [...(area ? area.querySelectorAll('button') : [])];
    const b = btns.find(x => /查询|搜索|检索/.test(x.textContent || ''));
    if (!b) return { err: 'no 查询 button', areaLen: area ? area.innerHTML.length : -1, btnTexts: btns.map(x => (x.textContent || '').trim().slice(0, 8)).slice(0, 6) };
    const form = b.closest('.cbdb-adv-form') || b.parentElement;
    const inp = form.querySelector('textarea, input[type="text"], input:not([type])');
    return { err: null, inpId: inp ? inp.id : null, tag: inp ? inp.tagName : null, hasInlineEnter: inp ? (inp.getAttribute('onkeydown') || '').includes('Enter') : null };
});
t('找到人名输入框', !probe.err && !!probe.inpId);
console.log('  probe:', JSON.stringify(probe));
if (probe.inpId) {
    // 预热：Access 冷库首查约 79s，先点按钮跑一次当暖机
    await page.click('#' + probe.inpId);
    await page.type('#' + probe.inpId, '王安石');
    await page.evaluate(() => {
        const b = [...document.querySelectorAll('#cbdbSearchArea button')].find(x => /查询|搜索|检索/.test(x.textContent || ''));
        if (b) b.click();
    });
    await page.waitForFunction(() => {
        const r = document.getElementById('cbdbResults');
        return r && !r.textContent.includes('查询中') && !r.textContent.includes('正在');
    }, { timeout: 150000 }).catch(() => {});
    // 清场，正式测 Enter
    await page.evaluate(() => {
        const r = document.getElementById('cbdbResults');
        if (r) r.innerHTML = '';
        document.getElementById('cbdbSearchInput').value = '';
    });
    await page.click('#' + probe.inpId);
    await page.type('#' + probe.inpId, '苏轼');
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => {
        const r = document.getElementById('cbdbResults');
        return r && r.children.length > 0 && !r.textContent.includes('查询中') && !r.textContent.includes('正在');
    }, { timeout: 60000 }).catch(() => {});
    const after = await page.evaluate(() => {
        const r = document.getElementById('cbdbResults');
        return { n: r ? r.children.length : -1, txt: r ? r.textContent.slice(0, 60) : '' };
    });
    t('Enter 触发查询出结果', after.n > 0 && /共\s*\d+\s*条/.test(after.txt));
    console.log('  results:', JSON.stringify(after));
}
console.log('RESULT ' + pass + '/' + (pass + fail));
await browser.close();
process.exit(fail ? 1 : 0);
