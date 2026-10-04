/* 六月息 · 读文献页 v5: 顶部缩略图条带选文献, 左栏内嵌PDF, 右栏笔记->Obsidian
 * 数据流: 文献元数据=Zotero, PDF=本地文件流, 笔记=Obsidian vault, JX 只做窗口
 */
(function () {
    var API = '/api/';
    var current = null;

    function el(t, c, h) {
        var e = document.createElement(t);
        if (c) e.className = c;
        if (h != null) e.innerHTML = h;
        return e;
    }
    function esc(s) {
        return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    // WebView2 不响应 zotero:// obsidian://, 走后端调起系统
    function openExternal(u) {
        fetch('/api/open-url?u=' + encodeURIComponent(u)).catch(function () {});
    }
    function fetchTO(url, ms) {
        return Promise.race([
            fetch(url),
            new Promise(function (_, rej) { setTimeout(function () { rej(new Error('timeout')); }, ms); })
        ]);
    }
    var TYPE_ZH = { book: '专著', bookSection: '章节', journalArticle: '论文', conferencePaper: '会议', thesis: '学位论文', newspaperArticle: '报刊', document: '文档', blogPost: '博客' };
    function TYPE(t) { return TYPE_ZH[t] || t || ''; }

    function buildPage() {
        if (document.getElementById('readingPage')) return;
        var main = document.querySelector('main.main-content') || document.querySelector('main');
        if (!main) return;
        var page = el('div');
        page.id = 'reading';
        page.className = 'page';
        page.innerHTML = [
            '<style>',
            '/* 顶部: 搜索 + 缩略条带 */',
            '.rd-toolbar{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--border-color,#2a2e37);flex-wrap:nowrap}',
            '.rd-searchwrap{display:flex;gap:6px;flex-shrink:0}',
            '#rdSearch{padding:6px 10px;border-radius:7px;border:1px solid var(--border-color,#3a3f4a);background:var(--bg,#1e2127);color:var(--text,#e4e0d8);font-size:12.5px;width:150px;outline:none}',
            '#rdSearch:focus{border-color:#c9a96e}',
            '.rd-btn{padding:9px 20px;border:none;border-radius:8px;background:#c9a96e;color:#1e2127;font-size:13.5px;cursor:pointer;text-decoration:none;display:inline-block}',
            '.rd-btn.ghost{background:transparent;border:1px solid var(--border-color,#3a3f4a);color:var(--text,#e4e0d8)}',
            '.rd-btn:disabled{opacity:.5;cursor:wait}',
            '.rd-btn.sm{padding:6px 12px;font-size:12px}',
            '.rd-strip{display:flex;gap:8px;overflow-x:auto;flex:1;padding:2px;scrollbar-width:thin}',
            '.rd-card{flex:0 0 auto;max-width:190px;padding:7px 10px;border:1px solid var(--border-color,#3a3f4a);border-radius:8px;cursor:pointer;transition:border-color .15s;background:var(--panel,#262a32)}',
            '.rd-card:hover{border-color:#c9a96e}',
            '.rd-card.sel{border-color:#c9a96e;background:rgba(201,169,110,.12)}',
            '.rd-card-t{font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.35}',
            '.rd-card-m{font-size:10.5px;color:var(--text-muted,#8a8f9a);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
            '/* 主体: 左PDF右笔记(布局可切换+拖拽调宽) */',
            '.rd-body{display:flex;padding:14px 16px;height:calc(100vh - 168px);gap:0}',
            '.rd-body[data-layout="row"]{flex-direction:row}',
            '.rd-body[data-layout="row-reverse"]{flex-direction:row-reverse}',
            '.rd-body[data-layout="column"]{flex-direction:column}',
            '.rd-body[data-layout="column-reverse"]{flex-direction:column-reverse}',
            '.rd-resizer{flex:0 0 10px;cursor:col-resize;position:relative;z-index:5;border-radius:5px}',
            '.rd-resizer:hover,.rd-resizer.dragging{background:rgba(201,169,110,.22)}',
            '.rd-resizer::after{content:"";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:4px;height:38px;border-radius:2px;background:var(--border-color,#3a3f4a)}',
            '.rd-body[data-layout^="column"] .rd-resizer{cursor:row-resize}',
            '.rd-body[data-layout^="column"] .rd-resizer::after{width:38px;height:4px}',
            '#rdLayoutSel{padding:6px 8px;border-radius:7px;border:1px solid var(--border-color,#3a3f4a);background:var(--bg,#1e2127);color:var(--text,#e4e0d8);font-size:12.5px;outline:none;flex-shrink:0;cursor:pointer}',
            '.rd-pdf{flex:1.25;display:flex;flex-direction:column;min-width:0;border:1px solid var(--border-color,#2a2e37);border-radius:12px;overflow:hidden;background:var(--panel,#262a32)}',
            '.rd-note-wrap{flex:1;display:flex;flex-direction:column;min-width:0;border:1px solid var(--border-color,#2a2e37);border-radius:12px;overflow:hidden;background:var(--panel,#262a32)}',
            '.rd-pane-head{padding:8px 12px;font-size:12.5px;font-weight:600;border-bottom:1px solid var(--border-color,#2a2e37);display:flex;justify-content:space-between;align-items:center;gap:8px}',
            '.rd-pane-sub{font-size:11px;color:var(--text-muted);font-weight:400;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
            '#rdFrame{flex:1;width:100%;border:none;background:#525659;min-height:0}',
            '.rd-pdf-ph{flex:1;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:13px;flex-direction:column;gap:6px}',
            '#rdNote{flex:1;width:100%;min-height:0;resize:none;padding:12px 14px;border:none;background:transparent;color:var(--text,#e4e0d8);font-size:13.5px;line-height:1.8;font-family:inherit;outline:none}',
            '.rd-actions{display:flex;gap:10px;align-items:center;padding:10px 12px;border-top:1px solid var(--border-color,#2a2e37);flex-wrap:wrap}',
            '.rd-status{font-size:12px;color:var(--text-muted)}',
            '/* 底部题录条 */',
            '.rd-meta-bar{display:flex;gap:12px;align-items:center;padding:8px 16px;border-top:1px solid var(--border-color,#2a2e37);font-size:12.5px;color:var(--text-muted);min-height:40px;flex-wrap:wrap}',
            '</style>',
            '<div class="rd-toolbar">',
            '  <div class="rd-searchwrap">',
            '    <input id="rdSearch" placeholder="搜 Zotero…">',
            '    <button class="rd-btn sm" id="rdSearchBtn">搜索</button>',
            '  </div>',
            '  <div class="rd-strip" id="rdStrip"><div class="zot-empty">载入中…</div></div>',
            '  <select id="rdLayoutSel" title="PDF 面板位置">',
            '    <option value="row">📐 PDF在左</option>',
            '    <option value="row-reverse">📐 PDF在右</option>',
            '    <option value="column">📐 PDF在上</option>',
            '    <option value="column-reverse">📐 PDF在下</option>',
            '  </select>',
            '</div>',
            '<div class="rd-body" id="rdBody" data-layout="row">',
            '  <div class="rd-pdf" id="rdPdfPane">',
            '    <div class="rd-pane-head"><span>📄 论文</span><span class="rd-pane-sub" id="rdPdfTitle">← 从上方条带选文献</span></div>',
            '    <div class="rd-pdf-ph" id="rdPh"><div style="font-size:34px">📖</div><div>选中后在这里读</div></div>',
            '    <iframe id="rdFrame" style="display:none"></iframe>',
            '  </div>',
            '  <div class="rd-resizer" id="rdResizer" title="拖拽调整两栏比例"></div>',
            '  <div class="rd-note-wrap" id="rdNotePane">',
            '    <div class="rd-pane-head"><span>✍️ 笔记</span><span class="rd-pane-sub">保存 → Obsidian 文献笔记/</span></div>',
            '    <textarea id="rdNote" placeholder="边读边记…&#10;&#10;保存后变成 Obsidian 里 文献笔记/ 下的 .md，带题录和跳回链接，可双链。"></textarea>',
            '    <div class="rd-actions">',
            '      <button class="rd-btn sm" id="rdSave" disabled>💾 保存到 Obsidian</button>',
            '      <span class="rd-status" id="rdStatus"></span>',
            '    </div>',
            '  </div>',
            '</div>',
            '<div class="rd-meta-bar" id="rdMeta"><span>← 选一篇文献开始；条带可横向滚动</span></div>'
        ].join('\n');
        main.appendChild(page);

        document.getElementById('rdSearchBtn').addEventListener('click', doSearch);
        document.getElementById('rdSearch').addEventListener('keydown', function (e) {
            if (e.key === 'Enter') doSearch();
        });
        document.getElementById('rdSave').addEventListener('click', saveNote);
        setupResizer();
        setupLayout();
        loadRecent();
    }

    function setupResizer() {
        var rz = document.getElementById('rdResizer');
        var body = document.getElementById('rdBody');
        var pdf = document.getElementById('rdPdfPane');
        var note = document.getElementById('rdNotePane');
        rz.addEventListener('mousedown', function (e) {
            e.preventDefault();
            var horiz = (body.dataset.layout || 'row').indexOf('row') === 0;
            var startPos = horiz ? e.clientX : e.clientY;
            var startSize = horiz ? pdf.offsetWidth : pdf.offsetHeight;
            var total = horiz ? body.clientWidth : body.clientHeight;
            if (total < 100) return;
            rz.classList.add('dragging');
            document.body.style.cursor = horiz ? 'col-resize' : 'row-resize';
            document.body.style.userSelect = 'none';
            function onMove(ev) {
                var pos = horiz ? ev.clientX : ev.clientY;
                var pct = (startSize + pos - startPos) / total;
                pct = Math.max(0.15, Math.min(0.85, pct));
                applyRatio(pct);
                try { localStorage.setItem('jx.rd.ratio', String(pct)); } catch (err) {}
            }
            function onUp() {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                rz.classList.remove('dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }

    function applyRatio(pct) {
        var pdf = document.getElementById('rdPdfPane');
        var note = document.getElementById('rdNotePane');
        pdf.style.flex = '0 0 ' + (pct * 100).toFixed(1) + '%';
        note.style.flex = '1 1 0';
    }

    function setupLayout() {
        var body = document.getElementById('rdBody');
        var sel = document.getElementById('rdLayoutSel');
        // 恢复上次设置
        try {
            var lay = localStorage.getItem('jx.rd.layout');
            if (lay && sel.querySelector('option[value="' + lay + '"]')) {
                body.dataset.layout = lay;
                sel.value = lay;
            }
            var ratio = parseFloat(localStorage.getItem('jx.rd.ratio'));
            if (ratio > 0.15 && ratio < 0.85) applyRatio(ratio);
        } catch (e) {}
        sel.addEventListener('change', function () {
            body.dataset.layout = sel.value;
            try { localStorage.setItem('jx.rd.layout', sel.value); } catch (e) {}
        });
    }

    function cardHtml(it) {
        var d = el('div', 'rd-card');
        d.dataset.key = it.key;
        d.title = it.title;
        var meta = [];
        if (it.creators) meta.push(it.creators);
        if (it.year) meta.push(it.year);
        meta.push(TYPE(it.itemType));
        d.innerHTML = '<div class="rd-card-t">' + esc(it.title) + '</div>' +
            '<div class="rd-card-m">' + esc(meta.join(' · ')) + '</div>';
        d.addEventListener('click', function () { select(it); });
        return d;
    }

    function renderStrip(items) {
        var box = document.getElementById('rdStrip');
        if (!box) return;
        box.innerHTML = '';
        if (!items.length) { box.innerHTML = '<div class="zot-empty">无匹配</div>'; return; }
        items.forEach(function (it) { box.appendChild(cardHtml(it)); });
    }

    function loadRecent() {
        var box = document.getElementById('rdStrip');
        if (!box) return;
        box.innerHTML = '<div class="zot-empty">载入中…</div>';
        fetchTO(API + 'zotero/recent?limit=15', 8000).then(function (r) { return r.json(); }).then(function (d) {
            if (d.ok) renderStrip(d.items || []);
            else box.innerHTML = '<div class="zot-empty">Zotero 未运行 <a href="#" id="rdRetry" style="color:#c9a96e">重试</a></div>';
            bindRetry();
        }).catch(function () {
            box.innerHTML = '<div class="zot-empty">读取失败 <a href="#" id="rdRetry" style="color:#c9a96e">重试</a></div>';
            bindRetry();
        });
    }

    function bindRetry() {
        var a = document.getElementById('rdRetry');
        if (a) a.addEventListener('click', function (e) { e.preventDefault(); loadRecent(); });
    }

    function doSearch() {
        var q = document.getElementById('rdSearch').value.trim();
        if (!q) { loadRecent(); return; }
        var box = document.getElementById('rdStrip');
        box.innerHTML = '<div class="zot-empty">检索中…</div>';
        fetchTO(API + 'zotero/search?q=' + encodeURIComponent(q) + '&limit=20', 8000).then(function (r) { return r.json(); }).then(function (d) {
            renderStrip(d.ok ? (d.items || []) : []);
        }).catch(function () { box.innerHTML = '<div class="zot-empty">检索失败</div>'; });
    }

    function select(it) {
        current = it;
        document.querySelectorAll('.rd-card').forEach(function (x) { x.classList.remove('sel'); });
        var node = document.querySelector('.rd-card[data-key="' + it.key + '"]');
        if (node) node.classList.add('sel');
        document.getElementById('rdSave').disabled = false;
        document.getElementById('rdStatus').textContent = '';
        document.getElementById('rdPdfTitle').textContent = it.title;
        document.getElementById('rdNote').value = '';

        // 底部题录条
        var meta = document.getElementById('rdMeta');
        meta.innerHTML = '';
        var info = el('span', null,
            '<b style="color:var(--text,#e4e0d8)">' + esc(it.title) + '</b>' +
            (it.creators ? '　' + esc(it.creators) : '') +
            (it.year ? '　' + esc(it.year) : '') +
            '　' + TYPE(it.itemType));
        meta.appendChild(info);

        // PDF 面板: 占位等待
        var frame = document.getElementById('rdFrame');
        var ph = document.getElementById('rdPh');
        frame.style.display = 'none';
        ph.style.display = 'flex';
        ph.innerHTML = '<div style="font-size:30px">⏳</div><div>查找 PDF…</div>';

        fetchTO(API + 'zotero/item/' + it.key + '/attachments', 8000).then(function (r) { return r.json(); }).then(function (d) {
            var atts = (d.ok && d.attachments) || [];
            var pdf = atts.filter(function (a) { return a.isPdf; });
            var row = document.getElementById('rdMeta');
            // 外部按钮
            if (pdf.length) {
                pdf.forEach(function (a) {
                    var b = el('button', 'rd-btn sm ghost', '外部打开');
                    b.type = 'button';
                    (function (u) { b.addEventListener('click', function () { openExternal(u); }); })(a.open);
                    row.appendChild(b);
                });
            }
            var zs = el('button', 'rd-btn sm ghost', '在 Zotero 查看');
            zs.type = 'button';
            (function (u) { zs.addEventListener('click', function () { openExternal(u); }); })(it.select);
            row.appendChild(zs);

            if (pdf.length) {
                frame.src = '/api/zotero/pdf/' + pdf[0].key;
                frame.onload = function () {
                    frame.style.display = 'block';
                    ph.style.display = 'none';
                };
            } else {
                ph.innerHTML = '<div style="font-size:30px">🗋</div><div>这条没有 PDF 附件</div>';
            }
        }).catch(function () {
            ph.innerHTML = '<div style="font-size:30px">⚠️</div><div>附件查询失败，重选试试</div>';
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
            st.innerHTML = '✅ 已存 Obsidian：' + esc(d.file) + '　';
            var ob = el('button', '', '在 Obsidian 打开');
            ob.type = 'button';
            ob.style.cssText = 'padding:3px 10px;font-size:11.5px;border-radius:6px;border:1px solid #c9a96e;background:transparent;color:#c9a96e;cursor:pointer';
            (function (url) { ob.addEventListener('click', function () { openExternal(url); }); })(d.obsidian);
            st.appendChild(ob);
        }).catch(function (e) {
            btn.disabled = false;
            st.textContent = '请求失败：' + e;
        });
    }

    function init() { buildPage(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
