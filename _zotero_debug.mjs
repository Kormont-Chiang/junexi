import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
const errs = [];
page.on('pageerror', e => errs.push(e.message));
await page.goto('http://127.0.0.1:57742', { waitUntil: 'networkidle0', timeout: 45000 });

// Go to reading tab
await page.click('[data-tab="reading"]');
await new Promise(r => setTimeout(r, 3000));

// Check what's displayed
const list = await page.evaluate(() => {
    var el = document.getElementById('rdList');
    return el ? el.textContent.substring(0, 200) : 'NOT FOUND';
});
console.log('rdList:', list);

const meta = await page.evaluate(() => {
    var el = document.getElementById('rdMeta');
    return el ? el.textContent : 'NOT FOUND';
});
console.log('rdMeta:', meta);

await page.screenshot({ path: '_shots_r44/zotero_debug.png' });
console.log('JS errors:', errs.length, errs.slice(0, 3));
await browser.close();
console.log('Done');
