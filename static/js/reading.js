/* 六月息 · 读文献页：Zotero 选文献 → 打开 PDF → 写笔记 → 落盘 Obsidian
 * 数据流: 文献元数据=Zotero, 笔记文件=Obsidian vault, JuneXi 只做操作界面
 */
(function () {
    var API = '/api/';
    var current = null;   // 选中的 zotero item
    var atts = [];

    function el(t, c, h) {
        var e = document.createElement(t);
        if (c) e.className = c;
        if (h != null) e.innerHTML = h;
        return e;
    }
    function esc(s) {
        return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function buildPage() {
        if (document.getElementById('readingPage')) return;
        var main = document.querySelector('main.main-content') || document.querySelector('main');
        if (!main) return;
        var page = el('div');
        page.id = 'reading';
        page.className = 'page';
        page.innerHTML = [
            '<style>',
            '.rd-layout{display:flex;gap:20px;height:calc(100vh - 100px)}',
            '.rd-left{width:360px;flex-shrink:0;display:flex;flex-direction:column;gap:12px;overflow-y:auto}',
            '.rd-right{flex:1;display:flex;flex-direction:column;gap:12px;min-width:0;overflow-y:auto}',
            '.rd-list{display:flex;flex-direction:column;gap:8px;max-height:46vh;overflow-y:auto}',
            '.rd-item{padding:9px 12px;border:1px solid var(--border-color,#3a3f4a);border-radius:9px;cursor:pointer;transition:border-color .15s}',
            '.rd-item:hover{border-color:#c9a96e}',
            '.rd-item.sel{border-color:#c9a96e;background:rgba(201,169,110,.08)}',
            '.rd-item-t{font-size:13px;font-weight:600;line-height:1.4}',
            '.rd-item-m{font-size:11.5px;color:var(--text-muted,#999);margin-top:3px}',
            '.rd-meta{font-size:13px;color:var(--text-muted);line-height:1.9}',
            '.rd-note{width:100%;min-height:280px;resize:vertical;padding:12px 14px;border:1px solid var(--border-color,#3a3f4a);border-radius:10px;background:var(--bg,#1e2127);color:var(--text,#e4e0d8);font-size:13.5px;line-height:1.8;font-family:inherit;outline:none}',
            '.rd-note:focus{border-color:#c9a96e}',
            '.rd-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}',
            '.rd-btn{padding:9px 20px;border:none;border-radius:8px;background:#c9a96e;color:#1e2127;font-size:13.5px;cursor:pointer;text-decoration:none;display:inline-block}',
            '.rd-btn.ghost{background:transparent;border:1px solid var(--border-color,#3a3f4a);color:var(--text,#e4e0d8)}',
            '.rd-btn:disabled{opacity:.5;cursor:wait}',
            '.rd-status{font-size:12.5px;color:var(--text-muted)}',
            '.rd-status a{color:#c9a96e}',
            '</style>',
            '<div class="rd-layout">',
            '  <div class="rd-left">',
            '    <div class="map-panel">',
            '      <div class="map-panel-title">📚 从 Zotero 选文献</div>',
            '      <div style="display:flex;gap:8px;margin-bottom:10px">',
            '        <input id="rdSearch" placeholder="搜标题/作者..." style="flex:1;padding:7px 11px;border-radius:7px;border:1px solid var(--border-color,#3a3f4a);background:var(--bg,#1e2127);color:var(--text,#e4e0d8);font-size:13px">',
            '        <button class="rd-btn" id="rdSearchBtn" style="padding:7px 14px">搜索</button>',
            '      </div>',
            '      <div class="rd-list" id="rdList"><div class="zot-empty">载入最近文献…</div></div>',
            '    </div>',
            '  </div>',
            '  <div class="rd-right">',
            '    <div class="map-panel" id="rdDetail">',
            '      <div class="map-panel-title">📖 文献</div>',
            '      <div class="rd-meta">← 从左侧选一篇文献开始</div>',
            '    </div>',
            '    <div class="map-panel">',
            '      <div class="map-panel-title">✍️ 笔记（保存在 Obsidian）</div>',
            '      <textarea id="rdNote" class="rd-note" placeholder="在这里记笔记…\n\n保存后会变成 Obsidian 里 文献笔记/ 下的一个 .md 文件，带题录 frontmatter，可双链。"></textarea>',
            '      <div class="rd-actions" style="margin-top:10px">',
            '        <button class="rd-btn" id="rdSave" disabled>💾 保存到 Obsidian</button>',
            '        <span class="rd-status" id="rdStatus"></span>',
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('\n');
        main.appendChild(page);

        document.getElementById('rdSearchBtn').addEventListener('click', doSearch);
        document.getElementById('rdSearch').addEventListener('keydown', function (e) {
            if (e.key === 'Enter') doSearch();
        });
        document.getElementById('rdSave').addEventListener('click', saveNote);
        loadRecent();
    }

    function itemHtml(it, cls) {
        var d = el('div', 'rd-item' + (cls ? ' ' + cls : ''));
        d.dataset.key = it.key;
        var meta = [];
        if (it.creators) meta.push(esc(it.creators));
        if (it.year) meta.push(esc(it.year));
        meta.push(TYPE(it.itemType));
        d.innerHTML = '<div class="rd-item-t">' + esc(it.title) + '</div>' +
            '<div class="rd-item-m">' + meta.join(' · ') + '</div>';
        d.addEventListener('click', function () { select(it); });
        return d;
    }

    var TYPE_ZH = { book: '专著', bookSection: '章节', journalArticle: '论文', conferencePaper: '会议', thesis: '学位论文', newspaperArticle: '报刊', document: '文档' };
    function TYPE(t) { return TYPE_ZH[t] || t || ''; }

    function renderList(items) {
        var box = document.getElementById('rdList');
        if (!box) return;
        box.innerHTML = '';
        if (!items.length) { box.innerHTML = '<div class="zot-empty">没有匹配文献</div>'; return; }
        items.forEach(function (it) { box.appendChild(itemHtml(it)); });
    }

    function loadRecent() {
        var box = document.getElementById('rdList');
        if (!box) return;
        box.innerHTML = '<div class="zot-empty">载入最近文献…</div>';
        fetchWithTimeout(API + 'zotero/recent?limit=15', 8000).then(function (r) { return r.json(); }).then(function (d) {
            if (d.ok) renderList(d.items || []);
            else box.innerHTML = '<div class="zot-empty">Zotero 未运行，启动后<a href="#" id="rdRetry" style="color:#c9a96e">重试</a></div>';
            bindRetry();
        }).catch(function () {
            box.innerHTML = '<div class="zot-empty">读取失败，<a href="#" id="rdRetry" style="color:#c9a96e">点击重试</a></div>';
            bindRetry();
        });
    }

    function bindRetry() {
        var a = document.getElementById('rdRetry');
        if (a) a.addEventListener('click', function (e) { e.preventDefault(); loadRecent(); });
    }

    function fetchWithTimeout(url, ms) {
        return Promise.race([
            fetch(url),
            new Promise(function (_, rej) { setTimeout(function () { rej(new Error('timeout')); }, ms); })
        ]);
    }

    function doSearch() {
        var q = document.getElementById('rdSearch').value.trim();
        if (!q) { loadRecent(); return; }
        var box = document.getElementById('rdList');
        box.innerHTML = '<div class="zot-empty">检索中…</div>';
        fetch(API + 'zotero/search?q=' + encodeURIComponent(q) + '&limit=20').then(function (r) { return r.json(); }).then(function (d) {
            renderList(d.ok ? (d.items || []) : []);
        });
    }

    function select(it) {
        current = it;
        document.querySelectorAll('.rd-item').forEach(function (x) { x.classList.remove('sel'); });
        var node = document.querySelector('.rd-item[data-key="' + it.key + '"]');
        if (node) node.classList.add('sel');

        var det = document.getElementById('rdDetail');
        det.innerHTML = '<div class="map-panel-title">📖 ' + esc(it.title) + '</div>' +
            '<div class="rd-meta">' +
            (it.creators ? '作者：' + esc(it.creators) + '<br>' : '') +
            (it.year ? '年份：' + esc(it.year) + '<br>' : '') +
            '类型：' + TYPE(it.itemType) + '</div>' +
            '<div style="margin-top:10px" id="rdPdfRow"><span class="rd-status">查找 PDF…</span></div>';
        document.getElementById('rdSave').disabled = false;

        fetchWithTimeout(API + 'zotero/item/' + it.key + '/attachments', 8000).then(function (r) { return r.json(); }).then(function (d) {
            var row = document.getElementById('rdPdfRow');
            if (!row) return;
            atts = (d.ok && d.attachments) || [];
            var pdf = atts.filter(function (a) { return a.isPdf; });
            if (!pdf.length) { row.innerHTML = '<span class="rd-status">这条没有 PDF 附件（可在 Zotero 里右键找全文）</span>'; return; }
            row.innerHTML = '';
            pdf.forEach(function (a) {
                var b = el('a', 'rd-btn', '打开 PDF');
                b.href = a.open; b.style.marginRight = '8px';
                row.appendChild(b);
            });
            var zs = el('a', 'rd-btn ghost', '在 Zotero 查看');
            zs.href = it.select;
            row.appendChild(zs);
        }).catch(function () {
            var row = document.getElementById('rdPdfRow');
            if (row) row.innerHTML = '<span class="rd-status">附件查询超时，<a href="#" id="rdRetryAtt" style="color:#c9a96e">重试</a></span>';
            var a2 = document.getElementById('rdRetryAtt');
            if (a2) a2.addEventListener('click', function (e) { e.preventDefault(); select(it); });
        });
    }

    function saveNote() {
        if (!current) return;
        var btn = document.getElementById('rdSave');
        var st = document.getElementById('rdStatus');
        var content = document.getElementById('rdNote').value;
        if (!content.trim()) { st.textContent = '笔记还是空的'; return; }
        btn.disabled = true;
        st.textContent = '保存中…';
        fetch(API + 'obsidian/zotero-note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: current.title,
                content: content,
                meta: { creators: current.creators, year: current.year, itemType: current.itemType, zoteroKey: current.key }
            })
        }).then(function (r) { return r.json(); }).then(function (d) {
            btn.disabled = false;
            if (!d.ok) { st.textContent = '保存失败：' + (d.error || ''); return; }
            st.innerHTML = '✅ 已存入 Obsidian：<a href="' + d.obsidian + '">' + esc(d.file) + '</a>';
        }).catch(function (e) {
            btn.disabled = false;
            st.textContent = '请求失败：' + e;
        });
    }

    function init() { buildPage(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
