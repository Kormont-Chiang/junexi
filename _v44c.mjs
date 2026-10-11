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
const barHeight = await page.evaluate(() => document.querySelector('.top-bar').style.height);
console.log('XLarge top bar height:', barHeight);
await page.screenshot({ path: '_shots_r44/xlarge_fixed.png' });
const noOverflow = await page.evaluate(() => {
    var tabs = document.querySelectorAll('.nav-tab');
    for (var t of tabs) { if (t.scrollHeight > t.clientHeight + 5) return false; }
    return true;
});
console.log('No nav tab overflow:', noOverflow);
await page.evaluate(() => { jxSetFontSize('standard'); });
await browser.close();
