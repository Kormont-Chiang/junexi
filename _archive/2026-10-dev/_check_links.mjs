// 史料库链接体检：抓取 index.html 里 library 页所有外链，逐个探测状态
import { readFileSync } from 'fs';
const html = readFileSync('templates/index.html', 'utf8');
const libStart = html.indexOf('id="library"');
const libEnd = html.indexOf('id="map"');
const seg = html.slice(libStart, libEnd);
const links = [...seg.matchAll(/<a href="(https?:\/\/[^"]+)"[^>]*class="db-card"[\s\S]*?<div class="db-name">([^<]+)<\/div>/g)]
    .map(m => ({ url: m[1], name: m[2] }));
console.log(`共 ${links.length} 个外链`);
const results = [];
for (const l of links) {
    let status = 'ERR', note = '';
    try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 12000);
        const r = await fetch(l.url, { method: 'GET', redirect: 'follow', signal: ctrl.signal,
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' } });
        clearTimeout(t);
        status = r.status;
        note = r.url !== l.url ? `→ ${new URL(r.url).host}` : '';
    } catch (e) { note = e.name === 'AbortError' ? 'timeout' : (e.cause?.code || e.message).slice(0, 40); }
    results.push({ ...l, status, note });
    const s = typeof status === 'number' ? (status < 400 ? 'OK ' : 'BAD') : 'DEAD';
    console.log(`${s}  ${String(status).padStart(3)}  ${l.name}  ${l.url} ${note}`);
}
const bad = results.filter(r => typeof r.status !== 'number' || r.status >= 400);
console.log(`\n问题链接 ${bad.length}/${results.length}`);
bad.forEach(b => console.log(`  ${b.name}: ${b.status} ${b.note} (${b.url})`));
