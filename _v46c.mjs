import { launchE2E } from './_e2e_browser.mjs';
const browser = await launchE2E();
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 900 });
await page.setCacheEnabled(false);
await page.goto('http://127.0.0.1:55864', { waitUntil: 'networkidle0', timeout: 30000 });

// Enable debug mode
await page.evaluate(() => { localStorage.setItem('jx-debug', '1'); });

// Trigger a JS error via window.dispatchEvent
await page.evaluate(() => {
    var evt = new ErrorEvent('error', { message: 'Test error for validation', filename: 'test.js', lineno: 1 });
    window.dispatchEvent(evt);
});

// Wait for toast
await new Promise(r => setTimeout(r, 500));
const toast = await page.evaluate(() => {
    var t = document.querySelector('div[style*="JX-Error"], div[style*="c04040"]');
    return t ? t.textContent : 'no toast';
});
console.log('Error toast:', toast);

// Check console errors captured
const errors = await page.evaluate(() => {
    // The error handler logs to console.error, but we can't read console retroactively
    // Just check that the handler exists
    return window.onerror !== null;
});

// Clean up
await page.evaluate(() => { localStorage.removeItem('jx-debug'); });
await browser.close();
console.log('Done');
