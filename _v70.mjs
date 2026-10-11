import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
const errs = [];
page.on('pageerror', e => errs.push(e.message));

// Test 1: Direct iframe to weread.qq.com
await page.goto('about:blank');
await page.setContent(`
<iframe src="https://weread.qq.com" style="width:100%;height:600px;border:1px solid red"></iframe>
`);
await new Promise(r => setTimeout(r, 8000));
const iframeBody = await page.evaluate(() => {
    var f = document.querySelector('iframe');
    try {
        return f.contentDocument ? f.contentDocument.body.innerHTML.length : 'cross-origin or empty';
    } catch(e) { return 'blocked: ' + e.message; }
});
console.log('Direct iframe bodyLen:', iframeBody);

// Test 2: Via our lib-proxy
await page.goto('about:blank');
await page.setContent(`
<iframe src="http://127.0.0.1:56336/api/lib-proxy?u=https%3A%2F%2Fweread.qq.com" style="width:100%;height:600px;border:1px solid blue"></iframe>
`);
await new Promise(r => setTimeout(r, 8000));
const proxyBody = await page.evaluate(() => {
    var f = document.querySelector('iframe');
    try {
        return f.contentDocument ? f.contentDocument.body.innerHTML.length : 'cross-origin or empty';
    } catch(e) { return 'blocked: ' + e.message; }
});
console.log('Proxy iframe bodyLen:', proxyBody);

await page.screenshot({ path: '_shots_r44/r70_weread.png' });
await browser.close();
console.log('Done');
