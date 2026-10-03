// 候选链接批量真实浏览器验证（修复版 + 新增丰容候选）
import puppeteer from 'puppeteer-core';
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const urls = [
    // 修复候选
    ['爱如生(典海)', 'http://dh.ersjk.com/'],
    ['中华经典古籍库www', 'https://www.gjqk.com/'],
    ['殷契文渊(安阳师院)', 'http://jgw.aynu.edu.cn/'],
    ['国家博物馆', 'https://www.chnmuseum.cn/'],
    ['CHGIS(哈佛CGA)', 'https://gis.harvard.edu/china-historical-gis'],
    ['CHGIS(Dataverse)', 'https://dataverse.harvard.edu/dataverse/chgis_v6'],
    ['国学网http', 'http://www.guoxue.com/'],
    ['简帛网重试', 'http://www.bsm.org.cn/'],
    ['CASHL重试', 'https://www.cashl.edu.cn/'],
    ['nssd远程重试', 'https://ra.nssd.org/'],
    ['读秀重试', 'https://www.duxiu.com/'],
    // 丰容候选
    ['汉籍全文检索(中研院)', 'https://hanchi.ihp.sinica.edu.tw/ihp/hanji.htm'],
    ['两千年中西历转换', 'https://sinocal.sinica.edu.tw/'],
    ['史语所', 'https://www.iis.sinica.edu.tw/'],
    ['Kanripo汉籍', 'https://www.kanripo.org/'],
    ['早稻田古籍', 'https://archive.wul.waseda.ac.jp/'],
    ['IDP敦煌(国图)', 'http://idp.nlc.cn/'],
    ['数字敦煌', 'https://www.e-dunhuang.com/'],
    ['敦煌研究院', 'https://www.dha.ac.cn/'],
    ['西安碑林', 'https://www.beilin-museum.com/'],
    ['方志中国', 'https://www.zgdfz.com/'],
    ['全国报刊索引', 'https://www.cnbksy.com/'],
    ['JSTOR', 'https://www.jstor.org/'],
    ['Project MUSE', 'https://muse.jhu.edu/'],
    ['Internet Archive', 'https://archive.org/'],
    ['HathiTrust', 'https://www.hathitrust.org/'],
    ['Google Books', 'https://books.google.com/'],
    ['国家档案文献导航', 'http://wenxianxue.cn/'],
];
const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--window-size=1400,900'] });
const page = await browser.newPage();
page.on('dialog', async d => { await d.dismiss(); });
for (const [name, url] of urls) {
    let result;
    try {
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 22000 });
        await new Promise(r => setTimeout(r, 1800));
        const title = await page.title().catch(() => '');
        result = `${resp.status()} "${title.slice(0, 42)}"`;
    } catch (e) {
        result = 'NAV-FAIL ' + e.message.split('\n')[0].slice(0, 80);
    }
    console.log(`${name}  =>  ${result}`);
}
await browser.close();
