// R40d: 四主题 × 关键页面截图比对
import { launchE2E } from './_e2e_browser.mjs';
import fs from 'fs';

const BASE = 'http://127.0.0.1:56001';
const THEMES = ['dark', 'light', 'sepia', 'morandi'];
const PAGES = [
    { name: 'dashboard', tab: 'dashboard' },
    { name: 'workspace', tab: 'workspace' },
    { name: 'library', tab: 'library' },
    { name: 'map', tab: 'map' },
    { name: 'tools', tab: 'tools' },
    { name: 'cbdb', tab: 'cbdb' },
    { name: 'ai', tab: 'ai' },
];

const OUT = '_shots_r40d';
fs.mkdirSync(OUT, { recursive: true });

const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);

let pass = 0, fail = 0;
const failures = [];

// Navigate once, then per theme: set localStorage + reload + screenshot each tab
await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 30000 });

for (const theme of THEMES) {
    // Set theme
    await page.evaluate((t) => {
        localStorage.setItem('jx-theme', t);
    }, theme);
    await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
    await new Promise(r => setTimeout(r, 500));

    // Verify data-theme attribute
    const attr = await page.evaluate(() => {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    });
    const themeOk = attr === theme;
    console.log(`Theme ${theme}: data-theme="${attr}" ${themeOk ? 'OK' : 'MISMATCH'}`);

    for (const pg of PAGES) {
        // Switch tab
        await page.evaluate((tab) => {
            const btn = document.querySelector(`.nav-tab[data-tab="${tab}"]`);
            if (btn) btn.click();
        }, pg.tab);
        await new Promise(r => setTimeout(r, 800));

        const file = `${OUT}/${theme}_${pg.name}.png`;
        await page.screenshot({ path: file });
        const size = fs.statSync(file).size;
        const ok = size > 5000; // A valid screenshot should be > 5KB
        if (ok) { pass++; } else { fail++; failures.push(`${theme}_${pg.name} too small (${size})`); }
        console.log(`  ${theme}/${pg.name}: ${size}B ${ok ? 'OK' : 'FAIL'}`);
    }
}

// Color leak check: sample computed background of body and top-bar per theme
for (const theme of THEMES) {
    await page.evaluate((t) => { localStorage.setItem('jx-theme', t); }, theme);
    await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
    await new Promise(r => setTimeout(r, 500));
    const colors = await page.evaluate(() => {
        const bodyBg = getComputedStyle(document.body).backgroundColor;
        const barBg = getComputedStyle(document.querySelector('.top-bar')).backgroundColor;
        const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
        return { bodyBg, barBg, accent };
    });
    console.log(`Colors ${theme}: body=${colors.bodyBg} bar=${colors.barBg} accent=${colors.accent}`);
}

await browser.close();
console.log(`\nR40d: ${pass} pass, ${fail} fail`);
if (failures.length) console.log('Failures:', failures);
process.exit(fail > 0 ? 1 : 0);
