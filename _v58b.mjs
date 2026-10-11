import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
const errs = [];
page.on('pageerror', e => errs.push(e.message));
await page.goto('http://127.0.0.1:53154', { waitUntil: 'networkidle0', timeout: 30000 });
await page.click('[data-tab="library"]');
await new Promise(r => setTimeout(r, 500));

// Find and click WeChat Reading card
const clicked = await page.evaluate(() => {
    var cards = document.querySelectorAll('#library .db-card');
    for (var c of cards) {
        if (c.textContent.includes('微信读书')) { c.click(); return true; }
    }
    return false;
});
console.log('Clicked weread:', clicked);

// Wait for iframe to load
await new Promise(r => setTimeout(r, 15000));

const state = await page.evaluate(() => {
    var loading = document.getElementById('lvLoading');
    var blocked = document.getElementById('lvBlocked');
    var iframe = document.getElementById('lvFrame');
    return {
        loading: loading ? loading.style.display : 'N/A',
        blocked: blocked ? blocked.style.display : 'N/A',
        iframe: iframe ? iframe.style.display : 'N/A',
        iframeSrc: iframe ? iframe.src.substring(0, 80) : 'N/A'
    };
});
console.log('State:', JSON.stringify(state));
console.log('JS errors:', errs.length, errs.slice(0, 3));
await page.screenshot({ path: '_shots_r44/r58_weread.png' });
await browser.close();
console.log('Done');
