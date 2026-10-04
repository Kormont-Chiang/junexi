import puppeteer from 'puppeteer-core';
import fs from 'fs';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true, args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 860 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const openUrlHits = [];
  page.on('request', r => { if (r.url().includes('/api/open-url')) openUrlHits.push(r.url().slice(-60)); });

  await page.goto('http://127.0.0.1:5000/?fix=links', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 4000));

  // T1 CBDB 外链点击 -> 应触发 /api/open-url
  await page.evaluate(() => {
    const links = [...document.querySelectorAll('#dashboard .quick-link')];
    const cbdb = links.find(a => a.textContent.includes('CBDB'));
    if (cbdb) cbdb.click();
  });
  await new Promise(r => setTimeout(r, 1200));

  // T2 快速笔记保存 -> 应写 vault 文件且成功
  await page.evaluate(() => {
    document.getElementById('quickNote').value = '仪表盘快速笔记测试';
    saveQuickNote();
  });
  await new Promise(r => setTimeout(r, 1500));
  const t2 = await page.evaluate(() => document.body.innerText.match(/札记已保存|已存|成功|失败[^\n]*/g));

  // T3 Vault 按钮 -> open-url
  const vaultBtnCount = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('#dashboard .quick-action-btn')];
    const v = btns.find(b => b.textContent.includes('Vault'));
    if (v) { v.click(); return true; }
    return false;
  });
  await new Promise(r => setTimeout(r, 1200));

  // T4 学术动态点击(若有链接)
  const newsClicked = await page.evaluate(() => {
    const n = document.querySelector('#newsList .news-item[onclick]');
    if (n) { n.click(); return true; }
    return false;
  });
  await new Promise(r => setTimeout(r, 1200));

  const dailyFile = String.raw`C:\Users\Lenovo\Documents\obsidian\论文写作\日记` + '\\' + new Date().toISOString().slice(0, 10) + '.md';
  const fileOk = fs.existsSync(dailyFile) ? fs.readFileSync(dailyFile, 'utf-8').includes('仪表盘快速笔记测试') : false;

  console.log(JSON.stringify({
    openUrlHits, t2, vaultBtnCount, newsClicked,
    dailyFileWritten: fileOk,
    errors: errors.length ? errors.slice(0, 3) : 'none',
  }, null, 1));
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
