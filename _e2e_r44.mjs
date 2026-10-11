// R44 验证：字体+字号+主题+底纹全面截图
import { launchE2E } from './_e2e_browser.mjs';
import fs from 'fs';

const proc = await import('child_process');
const portRes = proc.execSync('powershell -c "(Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -eq (Get-Process JuneXi | Select-Object -First 1).Id } | Select-Object -First 1).LocalPort"').toString().trim();
const BASE = `http://127.0.0.1:${portRes}`;

const OUT = '_shots_r44';
fs.mkdirSync(OUT, { recursive: true });

const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);

let pass = 0, fail = 0;
function check(name, ok) {
    if (ok) { pass++; console.log(`  ✓ ${name}`); }
    else { fail++; console.log(`  ✗ ${name}`); }
}

await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 30000 });

// 1. Font family selector exists and has options
const fontOptions = await page.evaluate(() => {
    return document.getElementById('fontFamilySelect')?.options.length;
});
check(`Font selector has 7 options (got ${fontOptions})`, fontOptions === 7);

// 2. Font size selector exists
const sizeOptions = await page.evaluate(() => {
    return document.getElementById('fontSizeSelect')?.options.length;
});
check(`Size selector has 4 options (got ${sizeOptions})`, sizeOptions === 4);

// 3. Test each font
const fonts = ['system', 'serif', 'kai', 'fang', 'hei', 'li', 'you'];
for (const f of fonts) {
    await page.evaluate((font) => { jxSetFont(font); }, f);
    await new Promise(r => setTimeout(r, 200));
    const actualFont = await page.evaluate(() => {
        return getComputedStyle(document.body).fontFamily;
    });
    const ok = actualFont.length > 0;
    check(`Font ${f}: ${actualFont.substring(0, 50)}`, ok);
}

// 4. Test font size zoom
for (const [size, expected] of [['small', 0.85], ['standard', 1], ['large', 1.15], ['xlarge', 1.3]]) {
    await page.evaluate((s) => { jxSetFontSize(s); }, size);
    await new Promise(r => setTimeout(r, 200));
    const zoom = await page.evaluate(() => document.body.style.zoom);
    const expectedZoom = String(expected);
    check(`Size ${size}: zoom=${zoom} (expect ${expectedZoom})`, zoom === expectedZoom);
}

// 5. Screenshot each font size
await page.evaluate(() => { jxSetFontSize('standard'); jxSetFont('system'); });
await new Promise(r => setTimeout(r, 300));
await page.screenshot({ path: `${OUT}/size_standard.png` });

await page.evaluate(() => { jxSetFontSize('xlarge'); });
await new Promise(r => setTimeout(r, 300));
await page.screenshot({ path: `${OUT}/size_xlarge.png` });

// 6. Screenshot each theme with font
const themes = ['qing', 'hong', 'zao', 'bai'];
for (const t of themes) {
    await page.evaluate((theme) => { jxSetTheme(theme); jxSetFontSize('standard'); }, t);
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: `${OUT}/theme_${t}.png` });
}
check('4 theme screenshots taken', true);

// 7. Test persistence
await page.evaluate(() => {
    jxSetFont('kai');
    jxSetFontSize('large');
    jxSetTheme('hong');
});
await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
await new Promise(r => setTimeout(r, 500));
const persisted = await page.evaluate(() => {
    return {
        font: localStorage.getItem('jx-font'),
        size: localStorage.getItem('jx-font-size'),
        theme: localStorage.getItem('jx-theme'),
        bodyFont: getComputedStyle(document.body).fontFamily,
        zoom: document.body.style.zoom,
        themeAttr: document.documentElement.getAttribute('data-theme')
    };
});
check(`Font persisted: ${persisted.font}`, persisted.font === 'kai');
check(`Size persisted: ${persisted.size}`, persisted.size === 'large');
check(`Theme persisted: ${persisted.theme}`, persisted.theme === 'hong');
check(`Body font is kai: ${persisted.bodyFont}`, persisted.bodyFont.includes('KaiTi') || persisted.bodyFont.includes('楷'));
check(`Zoom is 1.15: ${persisted.zoom}`, persisted.zoom === '1.15');
check(`Theme attr is hong: ${persisted.themeAttr}`, persisted.themeAttr === 'hong');

// Reset to defaults
await page.evaluate(() => {
    jxSetFont('system');
    jxSetFontSize('standard');
    jxSetTheme('qing');
});

await browser.close();
console.log(`\nR44: ${pass} pass, ${fail} fail`);
process.exit(fail > 0 ? 1 : 0);
