import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setCacheEnabled(false);

// Test WeChat Reading iframe compatibility
const targets = [
    { name: '微信读书网页版', url: 'https://weread.qq.com/' },
    { name: '微信读书书架', url: 'https://weread.qq.com/web/shelf' },
];

for (const t of targets) {
    try {
        // First check direct response
        const resp = await page.goto(t.url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        const status = resp ? resp.status() : 'no response';
        
        // Check X-Frame-Options
        const headers = resp ? resp.headers() : {};
        const xfo = headers['x-frame-options'] || 'not set';
        const csp = headers['content-security-policy'] || 'not set';
        
        // Check if page loaded content
        const title = await page.title();
        const bodyLen = await page.evaluate(() => document.body ? document.body.innerHTML.length : 0);
        
        console.log(`${t.name}:`);
        console.log(`  Status: ${status}`);
        console.log(`  X-Frame-Options: ${xfo}`);
        console.log(`  Title: ${title}`);
        console.log(`  Body length: ${bodyLen}`);
    } catch (e) {
        console.log(`${t.name}: Error - ${e.message.substring(0, 100)}`);
    }
}

await browser.close();
console.log('Done');
