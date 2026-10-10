// 史料库内嵌查看器 E2E：puppeteer-core + 系统 Edge headless
import puppeteer from 'puppeteer-core';

const BASE = process.env.BASE || 'http://127.0.0.1:5188';
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

await page.goto(BASE + '/?v=' + Date.now(), { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForSelector('#library .db-card', { timeout: 15000 });
t('史料库卡片存在', true);

// 点击第一张卡片 → 查看器打开（默认页签需切换到史料库——卡片可能不在当前页签视口，但 DOM 在）
const cardInfo = await page.evaluate(() => {
    const c = document.querySelector('#library .db-card');
    return { href: c.getAttribute('href'), name: (c.querySelector('.db-name') || {}).textContent };
});
t('卡片带外链', /^https?:/.test(cardInfo.href));

await page.evaluate(() => { document.querySelector('#library .db-card').click(); });
await sleep(500);
const opened = await page.evaluate(() => ({
    display: document.getElementById('libViewer').style.display,
    src: document.getElementById('lvFrame').src,
    title: document.getElementById('lvTitle').textContent
}));
t('查看器打开', opened.display === 'flex');
t('iframe 指向卡片链接', opened.src === cardInfo.href);
t('标题=站点名', opened.title === cardInfo.name.trim());

// 笔记：写入 → 存为笔记 → localStorage 落盘 → 列表渲染
await page.type('#lvnEditor', '测试笔记：这个库要从VPN进');
await page.evaluate(() => { document.getElementById('lvnAdd').click(); });
await sleep(400);
const noteState = await page.evaluate(() => ({
    count: document.getElementById('lvnCount').textContent,
    ls: (localStorage.getItem('junxi-libnotes') || ''),
    items: document.querySelectorAll('#lvnList .lvn-item').length,
    editor: document.getElementById('lvnEditor').value
}));
t('笔记已存本机', noteState.count === '1' && noteState.items === 1 && noteState.editor === '');
t('localStorage 落盘', noteState.ls.includes('测试笔记') && noteState.ls.includes(cardInfo.href));

// 删除笔记
await page.evaluate(() => { document.querySelector('#lvnList [data-del]').click(); });
await sleep(300);
const afterDel = await page.evaluate(() => document.getElementById('lvnCount').textContent);
t('删除笔记', afterDel === '0');

// Esc 关闭
await page.keyboard.press('Escape');
await sleep(300);
const closed = await page.evaluate(() => document.getElementById('libViewer').style.display);
t('Esc 关闭查看器', closed === 'none');

// 再开再关（遮罩点击）——验证状态复位
await page.evaluate(() => { document.querySelector('#library .db-card').click(); });
await sleep(400);
const reopen = await page.evaluate(() => ({
    display: document.getElementById('libViewer').style.display,
    count: document.getElementById('lvnCount').textContent
}));
t('重新打开状态复位', reopen.display === 'flex' && reopen.count === '0');
await page.evaluate(() => { document.getElementById('lvClose').click(); });

// 修饰键放行：Ctrl+点击不拦截（保留外部打开习惯）
await page.evaluate(() => {
    const c = document.querySelector('#library .db-card');
    c.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ctrlKey: true }));
});
await sleep(300);
const ctrlPass = await page.evaluate(() => document.getElementById('libViewer').style.display);
t('Ctrl+点击放行（不拦截）', ctrlPass === 'none');

console.log('RESULT ' + pass + '/' + (pass + fail));
await browser.close();
process.exit(fail ? 1 : 0);
