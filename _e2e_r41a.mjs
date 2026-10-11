// R41a: nav 页签拖拽排序 E2E
import { launchE2E } from './_e2e_browser.mjs';

const BASE = 'http://127.0.0.1:56001';
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

// 1. All nav tabs have draggable=true
const draggables = await page.evaluate(() => {
    return document.querySelectorAll('.nav-tab[draggable="true"]').length;
});
check(`8 nav tabs draggable (got ${draggables})`, draggables === 8);

// 2. Initial order
const initialOrder = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('#navTabs .nav-tab[data-tab]')).map(t => t.dataset.tab);
});
console.log('  Initial order:', initialOrder.join(', '));

// 3. Simulate drag: move "cbdb" to front
await page.evaluate(() => {
    localStorage.removeItem('jx-nav-order');
});
await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
await new Promise(r => setTimeout(r, 800));

const dragResult = await page.evaluate(() => {
    var tabs = document.querySelectorAll('#navTabs .nav-tab[data-tab]');
    var source = null;
    for (var i = 0; i < tabs.length; i++) {
        if (tabs[i].dataset.tab === 'cbdb') { source = tabs[i]; break; }
    }
    var target = null;
    for (var i = 0; i < tabs.length; i++) {
        if (tabs[i].dataset.tab === 'dashboard') { target = tabs[i]; break; }
    }
    if (!source || !target) return null;

    var dt = new DataTransfer();
    source.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
    var rect = target.getBoundingClientRect();
    document.getElementById('navTabs').dispatchEvent(new DragEvent('dragover', {
        bubbles: true, cancelable: true, dataTransfer: dt, clientX: rect.left + 5
    }));
    source.dispatchEvent(new DragEvent('dragend', { bubbles: true, dataTransfer: dt }));

    return Array.from(document.querySelectorAll('#navTabs .nav-tab[data-tab]')).map(t => t.dataset.tab);
});
console.log('  After drag:', dragResult.join(', '));
check('cbdb moved before dashboard', dragResult.indexOf('cbdb') < dragResult.indexOf('dashboard'));

// 4. Verify localStorage saved
const saved = await page.evaluate(() => {
    return localStorage.getItem('jx-nav-order');
});
check('localStorage jx-nav-order exists', saved !== null && saved.includes('cbdb'));
console.log('  Saved order:', saved);

// 5. Reload and verify order persists
await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
const afterReload = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('#navTabs .nav-tab[data-tab]')).map(t => t.dataset.tab);
});
console.log('  After reload:', afterReload.join(', '));
check('Order persists after reload', afterReload.indexOf('cbdb') < afterReload.indexOf('dashboard'));

// 6. switchTab still works after reorder
await page.evaluate(() => {
    document.querySelector('.nav-tab[data-tab="cbdb"]').click();
});
await new Promise(r => setTimeout(r, 500));
const activeTab = await page.evaluate(() => {
    return document.querySelector('.nav-tab.active')?.dataset.tab;
});
check('Click cbdb activates it', activeTab === 'cbdb');

// 7. Reset order
await page.evaluate(() => {
    localStorage.removeItem('jx-nav-order');
});
await page.reload({ waitUntil: 'networkidle0', timeout: 30000 });
const resetOrder = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('#navTabs .nav-tab[data-tab]')).map(t => t.dataset.tab);
});
console.log('  After reset:', resetOrder.join(', '));
// After reset, built-in tabs should be in original relative order, with plugin tabs before them
var builtins = resetOrder.filter(t => ['dashboard','workspace','library','map','tools','cbdb','ai','_plugins'].includes(t));
check('Reset restores builtin order', JSON.stringify(builtins) === JSON.stringify(['dashboard','workspace','library','map','tools','cbdb','ai','_plugins']));

await browser.close();
console.log(`\nR41a: ${pass} pass, ${fail} fail`);
process.exit(fail > 0 ? 1 : 0);
