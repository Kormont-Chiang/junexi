// R42: 底纹截图验证
import { launchE2E } from './_e2e_browser.mjs';
import fs from 'fs';

const BASE = 'http://127.0.0.1:56002';
const THEMES = ['dark', 'light', 'sepia', 'morandi'];
const OUT = '_shots_r42';
fs.mkdirSync(OUT, { recursive: true });

const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);

await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 30000 });

for (const theme of THEMES) {
    await page.evaluate((t) => { localStorage.setItem('jx-theme', t); }, theme);
    await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
    await new Promise(r => setTimeout(r, 600));

    const attr = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    
    // Check body::before has background-image
    const pattern = await page.evaluate(() => {
        var el = document.body;
        var pseudo = getComputedStyle(el, '::before');
        return {
            hasBg: pseudo.backgroundImage !== 'none',
            opacity: pseudo.opacity,
            bgUrl: pseudo.backgroundImage.substring(0, 80)
        };
    });
    
    const file = `${OUT}/${theme}_pattern.png`;
    await page.screenshot({ path: file });
    const size = fs.statSync(file).size;
    
    console.log(`${theme}: attr="${attr}" hasPattern=${pattern.hasBg} opacity=${pattern.opacity} shot=${size}B ${size > 5000 ? 'OK' : 'FAIL'}`);
}

await browser.close();
console.log('Done');
