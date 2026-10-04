/* 六月息 · Zotero 本地联动模块
 * 依赖: #library 容器 (文献页), 后端 /api/zotero/{status,search}
 * 功能: 探活 → 搜索本地库 → zotero://select 跳回定位
 */
(function () {
    var API = '/api/zotero/';
    var STATUS = { checked: false, ok: false };

    function el(tag, cls, html) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (html != null) e.innerHTML = html;
        return e;
    }

    function injectStyles() {
        if (document.getElementById('zotero-module-style')) return;
        var s = document.createElement('style');
        s.id = 'zotero-module-style';
        s.textContent = [
            '.zot-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}',
            '.zot-dot.on{background:#5a9e6e;box-shadow:0 0 6px rgba(90,158,110,.6)}',
            '.zot-dot.off{background:#999;opacity:.5}',
            '.zot-status{display:inline-flex;align-items:center;font-size:12.5px;color:var(--text-secondary,#888)}',
            '.zot-row{margin:10px 0 4px;display:flex;gap:8px}',
            '.zot-row input{flex:1;padding:8px 12px;border:1px solid var(--border,#3a3f4a);border-radius:8px;background:var(--bg,#1e2127);color:var(--text,#e4e0d8);font-size:13.5px;outline:none}',
            '.zot-row input:focus{border-color:#c9a96e}',
            '.zot-row button{padding:8px 18px;border:none;border-radius:8px;background:#c9a96e;color:#1e2127;font-size:13.5px;cursor:pointer}',
            '.zot-row button:disabled{opacity:.5;cursor:wait}',
            '.zot-hint{font-size:12px;color:var(--text-secondary,#888);margin:2px 0 10px}',
            '.zot-results{display:flex;flex-direction:column;gap:8px;margin-top:6px}',
            '.zot-item{display:block;padding:10px 13px;border:1px solid var(--border,#3a3f4a);border-radius:9px;text-decoration:none;color:inherit;transition:border-color .15s,transform .15s}',
            '.zot-item:hover{border-color:#c9a96e;transform:translateX(3px)}',
            '.zot-item-title{font-size:13.5px;font-weight:600;line-height:1.45}',
            '.zot-item-meta{font-size:12px;color:var(--text-secondary,#999);margin-top:4px}',
            '.zot-item-type{display:inline-block;font-size:11px;padding:1px 7px;border-radius:4px;background:rgba(201,169,110,.15);color:#c9a96e;margin-left:8px}',
            '.zot-empty{font-size:12.5px;color:var(--text-secondary,#888);padding:8px 2px}'
        ].join('\n');
        document.head.appendChild(s);
    }

    function buildSection() {
        var lib = document.getElementById('library');
        if (!lib) return null;
        var sec = el('div', 'db-section');
        sec.id = 'zotero-section';

        var title = el('div', 'db-section-title', '📚 Zotero 联动');
        sec.appendChild(title);

        var grid = el('div', 'db-grid');
        var card = el('div', 'db-card');
        card.style.display = 'block';
        card.style.cursor = 'default';

        var statusLine = el('div', 'zot-status',
            '<span class="zot-dot off" id="zotDot"></span><span id="zotStatusText">检测 Zotero 中…</span>');
        card.appendChild(statusLine);

        var row = el('div', 'zot-row');
        var input = el('input');
        input.id = 'zotSearchInput';
        input.placeholder = '搜索本地 Zotero 库（书名 / 作者 / 关键词）…';
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') doSearch();
        });
        var btn = el('button', null, '搜索');
        btn.id = 'zotSearchBtn';
        btn.addEventListener('click', doSearch);
        row.appendChild(input);
        row.appendChild(btn);
        card.appendChild(row);

        card.appendChild(el('div', 'zot-hint',
            '结果点击即跳回 Zotero 定位条目 · 需 Zotero 客户端运行中'));

        var results = el('div', 'zot-results');
        results.id = 'zotResults';
        card.appendChild(results);

        grid.appendChild(card);
        sec.appendChild(grid);
        lib.appendChild(sec);
        return sec;
    }

    function checkStatus() {
        fetch(API + 'status').then(function (r) { return r.json(); }).then(function (d) {
            STATUS.checked = true;
            STATUS.ok = !!d.ok;
            var dot = document.getElementById('zotDot');
            var txt = document.getElementById('zotStatusText');
            if (!dot || !txt) return;
            dot.className = 'zot-dot ' + (d.ok ? 'on' : 'off');
            txt.textContent = d.ok
                ? 'Zotero 已连接 · 可直接检索本地库'
                : 'Zotero 未运行 · 启动客户端后自动恢复';
        }).catch(function () {
            var dot = document.getElementById('zotDot');
            var txt = document.getElementById('zotStatusText');
            if (dot) dot.className = 'zot-dot off';
            if (txt) txt.textContent = 'Zotero 未运行';
        });
    }

    function esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    var TYPE_ZH = {
        book: '专著', bookSection: '章节', journalArticle: '论文',
        conferencePaper: '会议', thesis: '学位论文', newspaperArticle: '报刊',
        manuscript: '手稿', webpage: '网页', document: '文档',
        attachment: '附件', note: '笔记'
    };
    function typeZh(t) { return TYPE_ZH[t] || t || ''; }

    function doSearch() {
        var input = document.getElementById('zotSearchInput');
        var btn = document.getElementById('zotSearchBtn');
        var box = document.getElementById('zotResults');
        if (!input || !box) return;
        var q = input.value.trim();
        if (!q) { box.innerHTML = '<div class="zot-empty">先输入关键词</div>'; return; }
        btn.disabled = true;
        box.innerHTML = '<div class="zot-empty">检索中…</div>';
        fetch(API + 'search?q=' + encodeURIComponent(q)).then(function (r) {
            return r.json();
        }).then(function (d) {
            btn.disabled = false;
            if (!d.ok) {
                box.innerHTML = '<div class="zot-empty">检索失败：' + esc(d.error || '未知错误') + '</div>';
                return;
            }
            if (!d.items || !d.items.length) {
                box.innerHTML = '<div class="zot-empty">本地库没有匹配条目</div>';
                return;
            }
            box.innerHTML = '';
            d.items.forEach(function (it) {
                var a = el('a', 'zot-item');
                a.href = it.select;
                a.title = '在 Zotero 中定位';
                var meta = [];
                if (it.creators) meta.push(esc(it.creators));
                if (it.year) meta.push(esc(it.year));
                a.innerHTML =
                    '<div class="zot-item-title">' + esc(it.title) +
                    '<span class="zot-item-type">' + esc(typeZh(it.itemType)) + '</span></div>' +
                    '<div class="zot-item-meta">' + meta.join(' · ') + '</div>';
                box.appendChild(a);
            });
        }).catch(function (e) {
            btn.disabled = false;
            box.innerHTML = '<div class="zot-empty">请求失败：' + esc(e) + '</div>';
        });
    }

    function init() {
        injectStyles();
        if (buildSection()) checkStatus();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
