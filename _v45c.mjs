import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:56380', { waitUntil: 'networkidle0', timeout: 30000 });

const info = await page.evaluate(() => {
    var btn = document.getElementById('themeToggleBtn');
    var fontSel = document.getElementById('fontFamilySelect');
    var sizeSel = document.getElementById('fontSizeSelect');
    var navRight = document.querySelector('.nav-right');
    var topBar = document.querySelector('.top-bar');
    
    function rect(el) {
        if (!el) return null;
        var r = el.getBoundingClientRect();
        return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), visible: r.width > 0 && r.height > 0 && r.x < window.innerWidth };
    }
    
    return {
        themeBtn: rect(btn),
        fontSel: rect(fontSel),
        sizeSel: rect(sizeSel),
        navRight: rect(navRight),
        topBar: rect(topBar),
        innerWidth: window.innerWidth,
        navRightChildren: navRight ? navRight.children.length : 0,
        navRightDisplay: navRight ? getComputedStyle(navRight).display : 'missing',
        btnDisplay: btn ? getComputedStyle(btn).display : 'missing',
        btnParent: btn ? btn.parentElement.className : 'missing'
    };
});
console.log(JSON.stringify(info, null, 2));
await browser.close();
