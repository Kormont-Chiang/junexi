// 真实浏览器复核问题链接：加载成功/跳转/浏览器级错误
import puppeteer from 'puppeteer-core';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const urls = [
    ['院馆远程访问', 'https://ra.nssd.org/'],
    ['中国社会科学文库', 'http://www.sklib.cn/'],
    ['CASHL', 'https://www.cashl.edu.cn/'],
    ['爱如生', 'https://www.erslib.com/'],
    ['中华经典古籍库', 'https://gjqk.com/'],
    ['中国哲学书电子化计划', 'https://ctext.org/zh'],
    ['国学网', 'https://www.guoxue.com/'],
    ['谷歌学术', 'https://scholar.google.com/'],
    ['读秀', 'https://www.duxiu.com/'],
    ['简帛网', 'http://www.bsm.org.cn/'],
    ['殷契文渊', 'https://www.jgwz.org/'],
    ['简牍网', 'http://www.jianbo.org/'],
    ['国家博物馆', 'https://www.chinamuseum.org/'],
    ['CHGIS 官网', 'https://chgis.fairbank.fas.harvard.edu/'],
];
const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1400,900'] });
const page = await browser.newPage();
page.on('dialog', async d => { await d.dismiss(); });
for (const [name, url] of urls) {
    let result;
    try {
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await new Promise(r => setTimeout(r, 2500));
        const title = await page.title().catch(() => '');
        result = `${resp.status()} "${title.slice(0, 40)}" final=${page.url().slice(0, 60)}`;
    } catch (e) {
        result = 'NAV-FAIL ' + e.message.split('\n')[0].slice(0, 90);
    }
    console.log(`${name}  =>  ${result}`);
}
await browser.close();
