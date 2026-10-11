// Check actual pattern visibility
import { launchE2E } from './_e2e_browser.mjs';
import fs from 'fs';

const proc = await import('child_process');
const portRes = proc.execSync('powershell -c "(Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -eq (Get-Process JuneXi | Select-Object -First 1).Id } | Select-Object -First 1).LocalPort"').toString().trim();
const BASE = `http://127.0.0.1:${portRes}`;

const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 30000 });

const info = await page.evaluate(() => {
    var pseudo = getComputedStyle(document.body, '::before');
    var bg = pseudo.backgroundImage;
    var op = pseudo.opacity;
    // Force higher opacity temporarily to see if pattern exists
    document.body.style.setProperty('--pattern-opacity', '0.3');
    var pseudo2 = getComputedStyle(document.body, '::before');
    return {
        hasPattern: bg !== 'none',
        bgSnippet: bg.substring(0, 100),
        originalOpacity: op,
        forcedOpacity: pseudo2.opacity,
        bodyBg: getComputedStyle(document.body).backgroundColor
    };
});
console.log('Pattern info:', JSON.stringify(info, null, 2));

// Screenshot with forced high opacity
await new Promise(r => setTimeout(r, 300));
await page.screenshot({ path: '_shots_r42/debug_forced.png' });
console.log('Forced opacity screenshot saved');

// Restore and take normal
await page.evaluate(() => {
    document.body.style.setProperty('--pattern-opacity', '');
});
await new Promise(r => setTimeout(r, 300));
await page.screenshot({ path: '_shots_r42/debug_normal.png' });
console.log('Normal opacity screenshot saved');

await browser.close();
