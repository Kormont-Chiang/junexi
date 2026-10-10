// 受控实验2：固定 user-data-dir 复用配置 → 看安全日志是否安静
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const dir = 'C:/Users/Lenovo/.kimi_openclaw/workspace/historia-server/_e2e_profile';
fs.mkdirSync(dir, { recursive: true });
console.log('EXP-2 launch @', new Date().toTimeString().slice(0, 8));
const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
    userDataDir: dir,
    args: ['--disable-features=msHubApps', '--no-first-run', '--no-default-browser-check']
});
const page = await browser.newPage();
await page.goto('http://127.0.0.1:5188/', { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
await sleep(4000);
await browser.close();
console.log('EXP-2 done  @', new Date().toTimeString().slice(0, 8));
process.exit(0);
