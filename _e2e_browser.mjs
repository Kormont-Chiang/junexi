// 统一 E2E 浏览器：chrome-headless-shell（无身份层，零 Windows 登录副作用）
// 教训：勿用系统 Edge 跑自动化——每次启动=1 次伪失败登录，累积会锁用户账户
import puppeteer from 'puppeteer-core';

export const CHS = 'C:/Users/Lenovo/.kimi_openclaw/workspace/historia-server/_browsers/chrome-headless-shell-win64/chrome-headless-shell.exe';

export function launchE2E(extra = {}) {
    return puppeteer.launch({
        executablePath: CHS,
        headless: 'shell',
        args: ['--window-size=1400,900', ...(extra.args || [])]
    });
}
