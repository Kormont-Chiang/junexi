import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:58581', { waitUntil: 'networkidle0', timeout: 30000 });
const controls = await page.evaluate(() => {
    return {
        theme: document.getElementById('themeSelect')?.options.length,
        font: document.getElementById('fontFamilySelect')?.options.length,
        size: document.getElementById('fontSizeSelect')?.options.length
    };
});
console.log('Controls:', JSON.stringify(controls));
await page.screenshot({ path: '_shots_r44/check_controls.png' });
await browser.close();
