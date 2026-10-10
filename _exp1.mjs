// 单次受控实验：启动一次 headless Edge → 开本地页 → 5秒后关闭
// 若这次启动在安全日志留下 4625(Advapi/密码错)，即坐实测试工具=撞密码源头
import puppeteer from 'puppeteer-core';
const sleep = ms => new Promise(r => setTimeout(r, ms));
console.log('EXP-1 launch @', new Date().toTimeString().slice(0, 8));
const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--disable-features=msHubApps']
});
const page = await browser.newPage();
await page.goto('http://127.0.0.1:5188/', { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
await sleep(4000);
await browser.close();
console.log('EXP-1 done  @', new Date().toTimeString().slice(0, 8));
process.exit(0);
