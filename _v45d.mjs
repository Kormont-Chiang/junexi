import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:56380', { waitUntil: 'networkidle0', timeout: 30000 });
await page.screenshot({ path: '_shots_r44/final_check.png' });
await browser.close();
console.log('Done');
