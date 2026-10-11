import { launchE2E } from './_e2e_browser.mjs';
const proc = await import('child_process');
const port = proc.execSync('powershell -c "(Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -eq (Get-Process JuneXi | Select-Object -First 1).Id } | Select-Object -First 1).LocalPort"').toString().trim();
console.log('Port:', port);
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:'+port, { waitUntil: 'networkidle0', timeout: 30000 });
const controls = await page.evaluate(() => {
    var theme = document.getElementById('themeSelect');
    var font = document.getElementById('fontFamilySelect');
    var size = document.getElementById('fontSizeSelect');
    var plugins = document.getElementById('navPluginZone');
    return {
        theme: theme ? theme.options.length : 'MISSING',
        font: font ? font.options.length : 'MISSING',
        size: size ? size.options.length : 'MISSING',
        plugins: plugins ? plugins.children.length : 'MISSING',
        topBarHTML: document.querySelector('.top-bar')?.innerHTML?.substring(0, 500)
    };
});
console.log(JSON.stringify(controls, null, 2));
await page.screenshot({ path: '_shots_r44/check_controls.png' });
await browser.close();
