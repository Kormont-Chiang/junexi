import { launchE2E } from './_e2e_browser.mjs';
const proc = await import('child_process');
const port = proc.execSync('powershell -c "(Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -eq (Get-Process JuneXi | Select-Object -First 1).Id } | Select-Object -First 1).LocalPort"').toString().trim();
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:'+port, { waitUntil: 'networkidle0', timeout: 30000 });
await page.evaluate(() => { jxSetFontSize('xlarge'); });
await new Promise(r => setTimeout(r, 400));
await page.screenshot({ path: '_shots_r44/xlarge_v2.png' });
const logoOK = await page.evaluate(() => {
    var t = document.querySelector('.logo-text');
    return t ? getComputedStyle(t).whiteSpace : 'missing';
});
console.log('Logo white-space:', logoOK);
await page.evaluate(() => { jxSetFontSize('standard'); });
await browser.close();
