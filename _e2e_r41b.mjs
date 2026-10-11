// R41b: 功能块显隐开关 E2E
import { launchE2E } from './_e2e_browser.mjs';

const BASE = 'http://127.0.0.1:56001';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);

let pass = 0, fail = 0;
function check(name, ok) {
    if (ok) { pass++; console.log(`  ✓ ${name}`); }
    else { fail++; console.log(`  ✗ ${name}`); }
}

await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 30000 });
await page.evaluate(() => { localStorage.removeItem('jx-hidden-blocks'); });
await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });

// 1. Dashboard has 7 block-toggle icons
const toggleCount = await page.evaluate(() => {
    return document.querySelectorAll('#dashboard .block-toggle').length;
});
check(`7 block toggles on dashboard (got ${toggleCount})`, toggleCount === 7);

// 2. All dashboard panels have data-block
const blockCount = await page.evaluate(() => {
    return document.querySelectorAll('#dashboard .panel[data-block]').length;
});
check(`7 data-block panels (got ${blockCount})`, blockCount === 7);

// 3. Click toggle on dash-news hides it
await page.evaluate(() => {
    document.querySelector('.block-toggle[data-block="dash-news"]').click();
});
await new Promise(r => setTimeout(r, 300));
const newsHidden = await page.evaluate(() => {
    var el = document.querySelector('[data-block="dash-news"]');
    return el && el.classList.contains('block-hidden');
});
check('dash-news hidden after toggle click', newsHidden);

// 4. Content inside is actually hidden (not just class)
const contentHidden = await page.evaluate(() => {
    var el = document.querySelector('[data-block="dash-news"] .news-list');
    if (!el) return true; // no content to check
    var style = getComputedStyle(el);
    return style.display === 'none';
});
check('dash-news content display:none', contentHidden);

// 5. localStorage saved
const saved = await page.evaluate(() => {
    return localStorage.getItem('jx-hidden-blocks');
});
check('localStorage jx-hidden-blocks has dash-news', saved && saved.includes('dash-news'));

// 6. Reload and verify still hidden
await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
await new Promise(r => setTimeout(r, 500));
const stillHidden = await page.evaluate(() => {
    return document.querySelector('[data-block="dash-news"]').classList.contains('block-hidden');
});
check('dash-news still hidden after reload', stillHidden);

// 7. Click again to show
await page.evaluate(() => {
    document.querySelector('.block-toggle[data-block="dash-news"]').click();
});
await new Promise(r => setTimeout(r, 300));
const nowVisible = await page.evaluate(() => {
    return !document.querySelector('[data-block="dash-news"]').classList.contains('block-hidden');
});
check('dash-news visible after second toggle', nowVisible);

// 8. Hide two blocks simultaneously
await page.evaluate(() => {
    document.querySelector('.block-toggle[data-block="dash-quick"]').click();
    document.querySelector('.block-toggle[data-block="dash-vault"]').click();
});
await new Promise(r => setTimeout(r, 300));
const bothHidden = await page.evaluate(() => {
    return document.querySelector('[data-block="dash-quick"]').classList.contains('block-hidden')
        && document.querySelector('[data-block="dash-vault"]').classList.contains('block-hidden');
});
check('Two blocks hidden simultaneously', bothHidden);

// 9. Verify saved JSON has both
const saved2 = await page.evaluate(() => {
    return JSON.parse(localStorage.getItem('jx-hidden-blocks') || '{}');
});
check('localStorage has both blocks', saved2['dash-quick'] === true && saved2['dash-vault'] === true);

// 10. Panel header still visible when block is hidden
const headerVisible = await page.evaluate(() => {
    var header = document.querySelector('[data-block="dash-quick"] .panel-header');
    var style = getComputedStyle(header);
    return style.display !== 'none';
});
check('Panel header remains visible when collapsed', headerVisible);

// Cleanup
await page.evaluate(() => { localStorage.removeItem('jx-hidden-blocks'); });

await browser.close();
console.log(`\nR41b: ${pass} pass, ${fail} fail`);
process.exit(fail > 0 ? 1 : 0);
