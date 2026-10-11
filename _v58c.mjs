import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:53154', { waitUntil: 'networkidle0', timeout: 30000 });
await page.click('[data-tab="library"]');
await new Promise(r => setTimeout(r, 500));

// Click weread card
await page.evaluate(() => {
    var cards = document.querySelectorAll('#library .db-card');
    for (var c of cards) { if (c.textContent.includes('微信读书')) { c.click(); return; } }
});

// Wait and check what the iframe actually contains
await new Promise(r => setTimeout(r, 12000));

const info = await page.evaluate(() => {
    var iframe = document.getElementById('lvFrame');
    var loading = document.getElementById('lvLoading');
    var blocked = document.getElementById('lvBlocked');
    if (!iframe) return 'no iframe';
    var src = iframe.src;
    var bodyLen = 0, title = '';
    try {
        var doc = iframe.contentDocument;
        if (doc) {
            bodyLen = doc.body ? doc.body.innerHTML.length : 0;
            title = doc.title || '';
        }
    } catch(e) { return { src, error: e.message.substring(0, 80), loading: loading?.style.display, blocked: blocked?.style.display }; }
    return { src: src.substring(0, 80), bodyLen, title, loading: loading?.style.display, blocked: blocked?.style.display };
});
console.log('Iframe info:', JSON.stringify(info));
await browser.close();
console.log('Done');
