/**
 * 六月息 · 历史学学术面板前端
 * API 驱动的交互逻辑
 */

const API_BASE = '';
const VAULT_NAME = '论文写作';

// ── Toast 通知 ─────────────────────────────────────────
let toastContainer = null;
function showToast(message, type = 'info', duration = 3000) {
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ️'}</span><span class="toast-msg">${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ── 标签页切换 ─────────────────────────────────────────
function initTabs() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
}

let _pluginTabs = {}; // tabId -> plugin id

function loadPluginNav() {
    fetch('/api/plugins').then(r => r.json()).then(d => {
        const zone = document.getElementById('navPluginZone');
        if (!zone) return;
        _pluginTabs = {};
        zone.innerHTML = (d.nav || []).map(n => {
            _pluginTabs[n.tab] = n.plugin;
            return '<button class="nav-tab" data-tab="' + n.tab + '" onclick="switchTab(\'' + n.tab + '\')">' + (n.icon || '🧩') + ' ' + escapeHtml(n.label) + '</button>';
        }).join('');
        // 插件静态资源注入: css 进 head, js 按序 append(每插件每文件一次)
        const assets = d.assets || {};
        Object.entries(assets).forEach(([pid, as]) => {
            (as.css || []).forEach(url => {
                if (document.querySelector('link[data-jx-plugin="' + url + '"]')) return;
                const l = document.createElement('link');
                l.rel = 'stylesheet'; l.href = url; l.setAttribute('data-jx-plugin', url);
                document.head.appendChild(l);
            });
            (as.js || []).forEach(url => {
                if (document.querySelector('script[data-jx-plugin="' + url + '"]')) return;
                const s = document.createElement('script');
                s.src = url; s.setAttribute('data-jx-plugin', url);
                document.body.appendChild(s);
            });
        });
    }).catch(() => {});
}

async function loadPluginPage(tabId) {
    const pid = _pluginTabs[tabId];
    if (!pid) return;
    let pageEl = document.getElementById(tabId);
    if (!pageEl) {
        const main = document.querySelector('main');
        if (!main) return;
        pageEl = document.createElement('div');
        pageEl.id = tabId;
        pageEl.className = 'page';
        main.appendChild(pageEl);
        // 晚于 switchTab 的 class 切换创建: 手动对齐激活状态
        document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === tabId));
    }
    if (pageEl.dataset.loaded === '1') return;
    try {
        const res = await fetch('/plugin/' + pid + '/page');
        pageEl.innerHTML = res.ok
            ? '<div class="plugin-page-wrap">' + await res.text() + '</div>'
            : '<div class="empty-hint">插件页面加载失败（HTTP ' + res.status + '）</div>';
        pageEl.dataset.loaded = '1';
        // 插件页面就绪事件: 插件 js 可监听后初始化（innerHTML 不执行 inline script）
        document.dispatchEvent(new CustomEvent('jx-plugin-page', { detail: { pid, tabId } }));
    } catch (e) {
        pageEl.innerHTML = '<div class="empty-hint">插件页面加载失败</div>';
    }
}

async function loadPluginManager() {
    const list = document.getElementById('pluginList');
    if (!list) return;
    try {
        const d = await (await fetch('/api/plugins')).json();
        const ps = d.plugins || [];
        if (!ps.length) {
            list.innerHTML = '<div class="pm-empty">plugins/ 目录还没有插件——把带 manifest.json 的文件夹放进去，重启即装。</div>';
            return;
        }
        const running = ps.filter(p => p.loaded).length;
        const html = ps.map(p => {
            const on = !!p.loaded;
            const enabled = !!p.enabled;
            const dot = on ? '<span class="pm-dot on"></span>运行中' : (enabled ? '<span class="pm-dot warn"></span>待重启' : '<span class="pm-dot"></span>已停用');
            const icon = (p.icon || '🧩');
            return '<div class="pm-row' + (on ? '' : ' off') + '">' +
                '<div class="pm-icon">' + icon + '</div>' +
                '<div class="pm-main">' +
                    '<div class="pm-title"><span class="pm-name">' + escapeHtml(p.name) + '</span>' +
                    '<span class="pm-ver">' + escapeHtml(String(p.version || '')) + '</span>' +
                    '<span class="pm-status">' + dot + '</span></div>' +
                    '<div class="pm-desc">' + escapeHtml(p.desc || '(无描述)') + '</div>' +
                    (p.skip_reason ? '<div class="pm-skip">' + escapeHtml(p.skip_reason) + '</div>' : '') +
                '</div>' +
                '<label class="pm-switch"><input type="checkbox" ' + (enabled ? 'checked' : '') + ' onchange="togglePlugin(\'' + p.id + '\')"><span></span></label>' +
                (p.source === 'user' ? ('<button class="btn btn-sm pm-uninstall" onclick="uninstallPlugin(\'' + p.id + '\')" title="卸载">🗑</button>') : '') +
            '</div>';
        }).join('');
        list.innerHTML = '<div class="pm-summary">已安装 ' + ps.length + ' 个插件 · ' + running + ' 个运行中</div>' + html;
    } catch (e) {
        list.innerHTML = '<div class="pm-empty">插件清单加载失败</div>';
    }
}
window.loadPluginManager = loadPluginManager;

async function installPluginFromUrl() {
    const url = (document.getElementById('pmInstallUrl')?.value || '').trim();
    const msg = document.getElementById('pmInstallMsg');
    if (!url) { if (msg) msg.textContent = '先填 URL'; return; }
    if (msg) msg.textContent = '下载并校验中……';
    try {
        const d = await (await fetch('/api/plugins/install', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        })).json();
        if (msg) msg.textContent = d.ok ? ('✅ 已安装 ' + (d.installed.name || '') + '（' + (d.installed.files || 0) + ' 个文件），重启 JuneXi 生效') : ('❌ ' + (d.error || '失败'));
        if (d.ok) loadPluginManager();
    } catch (e) {
        if (msg) msg.textContent = '❌ ' + String(e).slice(0, 80);
    }
}
window.installPluginFromUrl = installPluginFromUrl;

async function installPluginLocal() {
    const lp = (document.getElementById('pmInstallLocal')?.value || '').trim();
    const msg = document.getElementById('pmInstallMsg');
    if (!lp) { if (msg) msg.textContent = '先填本机路径'; return; }
    if (msg) msg.textContent = '校验安装中……';
    try {
        const d = await (await fetch('/api/plugins/install', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ local_path: lp })
        })).json();
        if (msg) msg.textContent = d.ok ? ('✅ 已安装 ' + (d.installed.name || '') + '（' + (d.installed.files || 0) + ' 个文件），重启 JuneXi 生效') : ('❌ ' + (d.error || '失败'));
        if (d.ok) loadPluginManager();
    } catch (e) {
        if (msg) msg.textContent = '❌ ' + String(e).slice(0, 80);
    }
}
window.installPluginLocal = installPluginLocal;

async function loadPluginMarket() {
    const el = document.getElementById('pmMarketList');
    if (!el) return;
    el.innerHTML = '<div class="empty-hint">拉取 registry 中……</div>';
    const REG = 'https://raw.githubusercontent.com/Kormont-Chiang/junexi/main/plugins-registry.json';
    let installedMap = {};
    try {
        const pd = await (await fetch('/api/plugins')).json();
        (pd.plugins || []).forEach(p => { installedMap[p.id] = p.version; });
    } catch (e) {}
    try {
        const d = await (await fetch(REG, { cache: 'no-store' })).json();
        if (!Array.isArray(d) || !d.length) {
            el.innerHTML = '<div class="empty-hint">市场暂无条目。向仓库 plugins-registry.json 提 PR 即可上架。</div>';
            return;
        }
        el.innerHTML = d.map(p => {
            const cur = installedMap[p.id];
            const state = cur ? (cur === p.version ? '已安装' : ('升级 ' + cur + '→' + p.version)) : null;
            const can = !!(p.url && /^https:\/\//.test(p.url));
            return '<div class="pm-row">' +
                '<div class="pm-icon">🛒</div>' +
                '<div class="pm-main">' +
                    '<div class="pm-title"><span class="pm-name">' + escapeHtml(p.name || p.id) + '</span>' +
                    '<span class="pm-ver">' + escapeHtml(String(p.version || '')) + '</span>' +
                    '<span class="pm-status">' + escapeHtml(p.author || '') + '</span></div>' +
                    '<div class="pm-desc">' + escapeHtml(p.desc || '') + '</div>' +
                    '<div class="pm-skip">权限: ' + escapeHtml((p.permissions || ['未声明']).join('/')) + (state ? (' · <b>' + escapeHtml(state) + '</b>') : '') + '</div>' +
                '</div>' +
                (can ? ('<button class="btn btn-primary btn-sm" onclick="installMarketPlugin(this)" data-url="' + escapeHtml(p.url) + '" data-sha="' + escapeHtml(p.sha256 || '') + '">' + (cur ? (cur === p.version ? '重装' : '升级') : '安装') + '</button>') : '<span class="pm-ver">未发布</span>') +
            '</div>';
        }).join('');
    } catch (e) {
        el.innerHTML = '<div class="empty-hint">市场清单拉取失败（网络或 registry 不存在）</div>';
    }
}
window.loadPluginMarket = loadPluginMarket;

async function uninstallPlugin(pid) {
    if (!confirm('卸载插件 ' + pid + '？其文件将被删除。')) return;
    try {
        const d = await (await fetch('/api/plugins/' + encodeURIComponent(pid) + '/uninstall', { method: 'POST' })).json();
        showToast(d.ok ? '已卸载，重启后移除' : (d.error || '卸载失败'), d.ok ? 'success' : 'error');
        loadPluginManager();
    } catch (e) {
        showToast(String(e).slice(0, 80), 'error');
    }
}
window.uninstallPlugin = uninstallPlugin;

async function installMarketPlugin(btn) {
    const url = btn.getAttribute('data-url');
    const sha = btn.getAttribute('data-sha') || undefined;
    btn.disabled = true;
    btn.textContent = '安装中…';
    try {
        const d = await (await fetch('/api/plugins/install', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, sha256: sha })
        })).json();
        btn.textContent = d.ok ? '已装 ✓' : '失败';
        if (!d.ok) { btn.disabled = false; showToast(d.error || '安装失败', 'error'); }
        else loadPluginManager();
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '安装';
        showToast(String(e).slice(0, 80), 'error');
    }
}
window.installMarketPlugin = installMarketPlugin;

async function togglePlugin(pid) {
    try {
        const d = await (await fetch('/api/plugins/' + encodeURIComponent(pid) + '/toggle', { method: 'POST' })).json();
        showToast(d.ok ? (d.enabled ? '已启用，重启后加载' : '已停用，重启后卸载') : ('失败：' + (d.error || '')), d.ok ? 'success' : 'error');
        loadPluginManager();
    } catch (e) {
        showToast('操作失败', 'error');
    }
}
window.togglePlugin = togglePlugin;

function switchTab(tabId) {
    // 离开地图页签时停掉进行中的 flyTo 动画：0 尺寸容器上动画每帧抛 Invalid LatLng NaN
    if (tabId !== 'map' && chgisMap && chgisMap._animating) {
        try { chgisMap.stop(); } catch (e) { /* 防御 */ }
    }
    if (tabId === 'reading' && !_rdLoadedOnce) { try { loadReading(); } catch (e) {} }
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
    document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === tabId));
    // 仪表盘单屏: 激活时锁滚动(要锁 html, Windows 上滚动框在 documentElement), 离开解锁
    document.documentElement.classList.toggle('dash-fit', tabId === 'dashboard');
    document.body.classList.toggle('dash-fit', tabId === 'dashboard');
    if (tabId === '_plugins') loadPluginManager();
    if (_pluginTabs && _pluginTabs[tabId]) loadPluginPage(tabId);
    // 页面特定初始化
    if (tabId === 'dashboard') loadDashboard();
    if (tabId === 'map') {
        initMap();
        // display:none → 显示后 Leaflet 内部 size 仍是 0，flyTo/fitBounds 动画会算 NaN；
        // 等一帧让 CSS 生效再校正
        if (chgisMap) setTimeout(() => { try { chgisMap.invalidateSize(); } catch (e) { /* 防御 */ } }, 80);
    }
    if (tabId === 'workspace') loadWorkspace();
    if (tabId === 'library') loadLibrary();
    if (tabId === 'tools') initToolTabs();
    if (tabId === 'cbdb') {
        // 首次进入时渲染默认检索表单(模板里"人名"tab是active但表单要靠这里生成)
        const _area = document.getElementById('cbdbSearchArea');
        if (_area && !_area.innerHTML.trim()) switchCBDBType(window._cbdbType || 'person');
        loadCBDBDynasties();
    }
}

// ── Obsidian 集成 ──────────────────────────────────────
// 所有外部跳转统一走后端 /api/open-url (WebView2 不响应 obsidian:// 自定义协议, window.open/_blank 也不可靠)
window.openExternal = function (url) {
    fetch('/api/open-url?u=' + encodeURIComponent(url)).catch(() => {});
};

function openObsidianURI(path) {
    const u = path
        ? `obsidian://open?vault=${encodeURIComponent(VAULT_NAME)}&file=${encodeURIComponent(path)}`
        : `obsidian://open?vault=${encodeURIComponent(VAULT_NAME)}`;
    window.openExternal(u);
}

async function openObsidianNote(path) {
    try {
        const res = await fetch(`/api/obsidian/note/${encodeURIComponent(path)}`);
        const data = await res.json();
        if (!data.error) return data;
    } catch {}
    // API 失败，直接跳转
    openObsidianURI(path);
}

async function createDailyNote() {
    const content = prompt('今日札记内容（可选）：', '');
    try {
        const res = await fetch('/api/obsidian/daily', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content || '' })
        });
        const data = await res.json();
        if (!data.error) {
            showToast('今日札记已创建！', 'success');
            openObsidianURI('');
        } else {
            showToast('API 调用失败：' + data.error, 'error');
            openObsidianURI('');
        }
    } catch (e) {
        showToast('API 错误：' + e.message, 'error');
        openObsidianURI('');
    }
}

async function createExcerptNote() {
    const content = prompt('史料摘录内容：', '');
    if (!content) return;
    try {
        const res = await fetch(`/api/obsidian/note/${encodeURIComponent('史料/史料摘录 ' + new Date().toISOString().slice(0, 10) + '.md')}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: `# 史料摘录\n\n${content}\n\n---\n*摘录时间：${new Date().toLocaleString()}*` })
        });
        const data = await res.json();
        if (!data.error) {
            showToast('摘录已保存！', 'success');
        } else {
            showToast('保存失败：' + data.error, 'error');
        }
    } catch (e) {
        showToast('API 错误：' + e.message, 'error');
    }
}

async function saveQuickNote() {
    const textarea = document.getElementById('quickNote');
    if (!textarea) return;
    const content = textarea.value.trim();
    if (!content) { showToast('请先输入内容', 'warning'); return; }
    try {
        const res = await fetch('/api/obsidian/daily', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: '\n\n## 快速笔记\n' + content })
        });
        const data = await res.json();
        if (!data.error) {
            showToast('已保存到今日札记！', 'success');
            textarea.value = '';
        } else {
            showToast('保存失败：' + data.error, 'error');
        }
    } catch (e) {
        showToast('API 错误：' + e.message, 'error');
    }
}

// ── 仪表盘数据 ─────────────────────────────────────────
async function loadDashboard() {
    await Promise.all([loadStats(), loadNews(), loadRecentActivity(), loadPapersList()]);
}

async function loadStats() {
    try {
        const res = await fetch('/api/obsidian/stats');
        const data = await res.json();
        const legacy = data.legacy || {};
        const folders = data.folders || {};

        document.getElementById('statPapers').textContent = legacy['论文'] || 0;
        document.getElementById('statNotes').textContent = (legacy['札记'] || 0) + (legacy['日记'] || 0);
        document.getElementById('statPeople').textContent = legacy['人物'] || 0;
        document.getElementById('statSources').textContent = legacy['史料'] || 0;

        // Vault 概览
        const totalFiles = Object.values(folders).reduce((s, f) => s + (f.files || 0), 0);
        const totalFolders = Object.keys(folders).length;
        const rootItems = Object.keys(folders).filter(k => !folders[k].subfolders).length;

        document.getElementById('vaultTotalFiles').textContent = totalFiles;
        document.getElementById('vaultTotalFolders').textContent = totalFolders;
        document.getElementById('vaultRootFiles').textContent = rootItems;
    } catch {}
}

async function loadNews(force) {
    const container = document.getElementById('newsList');
    if (!container) return;
    container.innerHTML = '<div class="empty-hint">正在抓取学术资讯…</div>';
    try {
        const res = await fetch('/api/academic-feed' + (force ? '?refresh=1' : ''));
        const data = await res.json();
        const items = data.items || [];
        if (!items.length) {
            container.innerHTML = `<div class="empty-hint">${escapeHtml(data.error || '暂时没有抓到资讯，点右上角刷新重试')}</div>`;
            return;
        }
        const srcFilter = window._feedSrcFilter || '';
        const shown = srcFilter ? items.filter(it => it.source === srcFilter) : items;
        const srcCount = {};
        items.forEach(i => { srcCount[i.source || '?'] = (srcCount[i.source || '?'] || 0) + 1; });
        const palette = ['#d08a72', '#7ea3d0', '#8fbf9f', '#c9a86a', '#b48ec9', '#7ec9c3'];
        let pi = 0;
        const srcChips = `<div class="kb-chips news-src-chips">
            <span class="kb-chip${!srcFilter ? ' on' : ''}" onclick="feedSetSrc('')">全部·${items.length}</span>` +
            Object.keys(srcCount).map(sk => {
                const col = palette[pi++ % palette.length];
                return `<span class="kb-chip${srcFilter === sk ? ' on' : ''}" onclick="feedSetSrc('${escapeHtml(sk)}')" style="border-color:${col};color:${col}">${escapeHtml(sk)}·${srcCount[sk]}</span>`;
            }).join('') + `</div>`;
        shown.forEach(it => {
            it.title = _cleanFeedText(it.title);
            it.abstract = _cleanFeedText(it.abstract);
            it.authors = _cleanFeedText(it.authors);
        });
        const srcKnown = Object.keys(srcCount);
        container.innerHTML = srcChips + shown.map((it, idx) => {
            const si = Math.max(0, srcKnown.indexOf(it.source));
            const srcCls = 'news-src-c' + (si % 6);
            const abs = (it.abstract || '').trim();
            return `
            <div class="news-item news-feed-item">
                <div class="news-feed-head">
                    <span class="news-src ${srcCls}">${escapeHtml(it.source || '')}</span>
                    <span class="news-date">${escapeHtml(it.date || '')}</span>
                </div>
                <a class="news-feed-title" href="javascript:void(0)" onclick="openExternal('${(it.url || '').replace(/'/g, "%27")}')" title="打开原文">${escapeHtml(it.title || '')}</a>
                <div class="news-feed-meta">${escapeHtml(it.authors || '')}</div>
                ${abs ? `<div class="news-feed-abs" id="newsAbs${idx}" onclick="this.classList.toggle('open')">${escapeHtml(abs)}</div>` : ''}
            </div>`;
        }).join('') + (shown.length ? '' : '<div class="empty-hint">这个源暂时没有条目</div>') + `<div class="news-feed-foot"><button class="kb-nav-btn" onclick="loadNews(true)">↻ 刷新抓取</button><button class="kb-nav-btn" onclick="toggleFeedSources()">⚙ 自定义源</button><span class="news-date">${data.fetched_at ? '更新于 ' + data.fetched_at.slice(11, 16) : ''}${data.stale ? ' · 离线缓存' : ''}</span></div><div id="feedSourcesPanel" style="display:none"></div>`;
        loadFeedSourcesPanel();
    } catch (e) {
        container.innerHTML = '<div class="empty-hint">抓取失败：' + escapeHtml(String(e).slice(0, 80)) + '</div>';
    }
}
window.loadNews = loadNews;

function feedSetSrc(s) {
    window._feedSrcFilter = s || '';
    loadNews();
}
window.feedSetSrc = feedSetSrc;

function toggleFeedSources() {
    const p = document.getElementById('feedSourcesPanel');
    if (p) p.style.display = p.style.display === 'none' ? 'block' : 'none';
}
window.toggleFeedSources = toggleFeedSources;

async function injectPluginTabs() {
    try {
        const d = await (await fetch('/api/plugins')).json();
        const navs = d.nav || [];
        const anchor = document.querySelector('.nav-tab[data-tab="_plugins"]');
        if (!anchor) return;
        navs.forEach(nv => {
            if (document.querySelector('.nav-tab[data-tab="' + nv.tab + '"]')) return;
            const b = document.createElement('button');
            b.className = 'nav-tab';
            b.dataset.tab = nv.tab;
            b.textContent = (nv.icon || '🧩') + ' ' + (nv.label || nv.tab);
            anchor.parentNode.insertBefore(b, anchor);
            b.addEventListener('click', () => switchTab(nv.tab));
        });
    } catch (e) { /* nav 注入失败不影响核心导航 */ }
}
window.injectPluginTabs = injectPluginTabs;

async function downloadAppUpdate(el) {
    if (el) { el.textContent = '下载中…'; el.style.pointerEvents = 'none'; }
    try {
        const d = await (await fetch('/api/update/download', { method: 'POST' })).json();
        if (d.ok) {
            showToast('已下载 ' + Math.round(d.size / 1048576) + 'MB', 'success');
            const info = document.getElementById('appUpdateInfo');
            if (info) info.innerHTML = ' · 已下载到 updates 目录（' + (d.tag || '') + '），解压覆盖安装目录即可';
        } else {
            showToast(d.error || '下载失败', 'error');
            if (el) { el.textContent = '下载更新包'; el.style.pointerEvents = 'auto'; }
        }
    } catch (e) {
        showToast(String(e).slice(0, 80), 'error');
        if (el) { el.textContent = '下载更新包'; el.style.pointerEvents = 'auto'; }
    }
}
window.downloadAppUpdate = downloadAppUpdate;

async function checkAppUpdate(manual) {
    const tag = document.getElementById('appVerTag');
    const info = document.getElementById('appUpdateInfo');
    const link = document.getElementById('appUpdateLink');
    try {
        const d = await (await fetch('/api/update/check', { cache: 'no-store' })).json();
        if (!d.ok) {
            if (manual && info) { info.textContent = ' · 检查失败（需要网络）'; setTimeout(() => { info.textContent = ''; }, 3000); }
            return;
        }
        if (tag) tag.textContent = 'v' + d.current;
        if (d.update_available) {
            if (link) { link.textContent = '发现新版本 v' + d.latest; link.className = 'up-new'; }
            if (info) info.innerHTML = '（' + (d.published_at || '') + ' · <a href="javascript:void(0)" onclick="downloadAppUpdate(this)">下载更新包</a> · <a href="javascript:void(0)" onclick="openExternal(\'' + (d.url || 'https://github.com/Kormont-Chiang/junexi/releases') + '\')">前往页面</a>）';
            if (manual) showToast('发现新版本 v' + d.latest, 'success');
        } else if (manual && info) {
            info.textContent = ' · 已是最新';
            setTimeout(() => { info.textContent = ''; }, 3000);
        }
    } catch (e) {
        if (manual && info) { info.textContent = ' · 检查失败'; setTimeout(() => { info.textContent = ''; }, 3000); }
    }
}
window.checkAppUpdate = checkAppUpdate;

async function loadFeedSourcesPanel() {
    const p = document.getElementById('feedSourcesPanel');
    if (!p) return;
    try {
        const d = await (await fetch('/api/academic-feed/sources')).json();
        const lst = d.sources || [];
        p.innerHTML = '<div class="pm-install" style="margin-top:8px">' +
            '<div class="pm-install-title">📡 自定义 RSS 源 <span class="pm-ver">随内置源一起抓取</span></div>' +
            (lst.length ? lst.map((s, i) =>
                '<div class="pm-row"><div class="pm-main"><div class="pm-title"><span class="pm-name">' + escapeHtml(s.name) + '</span></div>' +
                '<div class="pm-desc">' + escapeHtml(s.url) + '</div></div>' +
                '<button class="btn btn-sm pm-uninstall" onclick="delFeedSource(' + i + ')">🗑</button></div>'
            ).join('') : '<div class="empty-hint">还没有自定义源</div>') +
            '<div class="pm-install-row"><input id="feedSrcName" placeholder="源名称(可空)" style="flex:1;min-width:90px">' +
            '<input id="feedSrcUrl" placeholder="https://…/feed.xml" style="flex:2;min-width:150px">' +
            '<button class="btn btn-primary btn-sm" onclick="addFeedSource()">＋添加</button></div>' +
            '<div class="pm-hint">添加后点"刷新抓取"生效；仅支持 https</div></div>';
    } catch (e) {
        p.innerHTML = '<div class="empty-hint">自定义源面板加载失败</div>';
    }
}

async function addFeedSource() {
    const name = (document.getElementById('feedSrcName') || {}).value || '';
    const url = (document.getElementById('feedSrcUrl') || {}).value || '';
    if (!url.trim()) { showToast('填 RSS 地址', 'error'); return; }
    try {
        const d = await (await fetch('/api/academic-feed/sources', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.trim(), url: url.trim() })
        })).json();
        showToast(d.ok ? '已添加，刷新抓取后生效' : (d.error || '添加失败'), d.ok ? 'success' : 'error');
        if (d.ok) { loadFeedSourcesPanel(); loadNews(true); }
    } catch (e) { showToast(String(e).slice(0, 80), 'error'); }
}
window.addFeedSource = addFeedSource;

async function delFeedSource(i) {
    try {
        const d = await (await fetch('/api/academic-feed/sources/' + i, { method: 'DELETE' })).json();
        showToast(d.ok ? '已删除' : '删除失败', d.ok ? 'success' : 'error');
        if (d.ok) { loadFeedSourcesPanel(); loadNews(true); }
    } catch (e) { showToast(String(e).slice(0, 80), 'error'); }
}
window.delFeedSource = delFeedSource;

// feed/arXiv 文本清洗: LaTeX 内联数学+HTML 实体+空白归一
function _cleanFeedText(s) {
    if (!s) return '';
    return String(s)
        .replace(/\$[^$\n]{1,80}\$/g, ' ')
        .replace(/\$\$[^$]{1,200}\$\$/g, ' ')
        .replace(/&[a-z]+;/gi, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

// ── 联合检索: 一次输入, 多库并行 ──
async function fedSearch() {
    const inp = document.getElementById('fedQuery');
    const box = document.getElementById('fedResults');
    if (!inp || !box) return;
    const q = inp.value.trim();
    if (!q) return;
    box.style.display = '';
    box.innerHTML = '<div class="fed-loading">正在并行检索各库…</div>';
    try {
        const d = await (await fetch('/api/federated/search?q=' + encodeURIComponent(q))).json();
        if (!d.ok) { box.innerHTML = '<div class="fed-loading">检索失败</div>'; return; }
        const r = d.results || {};
        const local = r.local || {};
        const kr = r.kanripo;
        let html = '<div class="fed-grid">';
        // CBDB 本地
        html += '<div class="fed-cell"><div class="fed-cell-title">🏛️ CBDB 本地库</div>' +
            '<div class="fed-cell-body">' +
            '<div class="fed-hit">人物 <b>' + (local.cbdb_person ?? '—') + '</b> · 职官 <b>' + (local.cbdb_office ?? '—') + '</b> · 地名 <b>' + (local.cbdb_place ?? '—') + '</b></div>' +
            '<button class="tool-src-btn" onclick="fedGoCbdb(\'' + q.replace(/'/g, '') + '\')">在 CBDB 中打开</button>' +
            '</div></div>';
        // Kanripo
        html += '<div class="fed-cell"><div class="fed-cell-title">📚 Kanripo 汉籍库</div><div class="fed-cell-body">';
        if (kr && kr.error) {
            html += '<div class="fed-note">' + escapeHtml(kr.error) + '</div>' +
                '<a class="tool-src-btn" href="https://github.com/search?q=' + encodeURIComponent(q + ' org:kanripo') + '&type=code" target="_blank" rel="noopener">GitHub 打开</a>';
        } else if (Array.isArray(kr) && kr.length) {
            html += kr.slice(0, 4).map(it => '<a class="fed-link" href="' + it.link + '" target="_blank" rel="noopener">' + escapeHtml(it.title) + ' <span class="fed-repo">' + escapeHtml(it.repo || '') + '</span></a>').join('');
        } else {
            html += '<div class="fed-note">未命中</div>';
        }
        html += '</div></div>';
        // ctext
        const ct = (r.ctext || [])[0];
        html += '<div class="fed-cell"><div class="fed-cell-title">📖 中国哲学书电子化计划</div><div class="fed-cell-body">';
        if (ct) html += '<a class="tool-src-btn" href="' + ct.link + '" target="_blank" rel="noopener">ctext 检索「' + escapeHtml(q.slice(0, 12)) + '」</a><div class="fed-note">机构库,网页版全文检索</div>';
        html += '</div></div>';
        // 订阅库 deeplinks
        html += '<div class="fed-cell"><div class="fed-cell-title">🔐 订阅库(站内打开)</div><div class="fed-cell-body fed-sub">' +
            '<a class="tool-src-btn" href="https://www.ancientbooks.cn/" target="_blank" rel="noopener">爱如生</a>' +
            '<a class="tool-src-btn" href="https://www.ancientbooks.cn/" target="_blank" rel="noopener" title="机构订阅,需登录">中华经典古籍库</a>' +
            '<a class="tool-src-btn" href="https://www.guji.cn/" target="_blank" rel="noopener">籍合网</a>' +
            '<div class="fed-note">订阅库无公开接口,带词前往检索页</div></div></div>';
        html += '</div>';
        box.innerHTML = html;
    } catch (e) {
        box.innerHTML = '<div class="fed-loading">检索失败：' + escapeHtml(String(e).slice(0, 60)) + '</div>';
    }
}
window.fedSearch = fedSearch;

function fedGoCbdb(q) {
    switchTab('cbdb');
    if (typeof switchCBDBType === 'function') switchCBDBType('person');
    const inp = document.getElementById('cbdbSearchInput');
    if (inp) inp.value = q;
}
window.fedGoCbdb = fedGoCbdb;

// ── 史料库: 检索 + AI 导购 ──
function filterLibrary(kw) {
    kw = (kw || '').trim().toLowerCase();
    const cards = document.querySelectorAll('#library .db-card');
    let shown = 0;
    document.querySelectorAll('#library .db-section').forEach(sec => {
        if (sec.querySelector('.lib-ai-panel') || sec.querySelector('#obsidianSearchInput')) return;
        const secTitle = (sec.querySelector('.db-section-title')?.textContent || '').toLowerCase();
        let secShown = 0;
        sec.querySelectorAll('.db-card').forEach(card => {
            const t = card.textContent.toLowerCase();
            const ok = !kw || t.includes(kw) || secTitle.includes(kw);
            card.style.display = ok ? '' : 'none';
            if (ok) { secShown++; shown++; }
        });
        sec.style.display = secShown ? '' : 'none';
    });
    const cnt = document.getElementById('libCount');
    if (cnt) cnt.textContent = kw ? (shown + ' 个匹配') : (cards.length + ' 站');
    let empty = document.getElementById('libEmpty');
    if (kw && shown === 0) {
        if (!empty) {
            empty = document.createElement('div');
            empty.id = 'libEmpty';
            empty.className = 'empty-hint';
            empty.style.padding = '20px';
            const grid = document.querySelector('#library .db-grid');
            if (grid && grid.parentElement) grid.parentElement.appendChild(empty);
        }
        empty.textContent = '没有匹配的站点——可以直接问下面的 AI 导购';
        empty.style.display = '';
    } else if (empty) {
        empty.style.display = 'none';
    }
}
window.filterLibrary = filterLibrary;

function _libSiteList() {
    const sites = [];
    document.querySelectorAll('#library .db-card').forEach(card => {
        const name = card.querySelector('.db-name')?.textContent.trim();
        const desc = card.querySelector('.db-desc')?.textContent.trim();
        const href = card.getAttribute('href') || '';
        if (name && href && !href.startsWith('javascript')) sites.push({ name, desc, href });
    });
    return sites;
}

window._libAIHistory = [];
function libAISend() {
    const input = document.getElementById('libAIInput');
    const chat = document.getElementById('libAIChat');
    const q = (input?.value || '').trim();
    if (!q) return;
    const btn = document.querySelector('.lib-ai-send');
    if (btn) btn.disabled = true;
    const hint = chat.querySelector('.lib-ai-hint');
    if (hint) hint.remove();
    chat.insertAdjacentHTML('beforeend', '<div class="lib-ai-msg lib-ai-q">' + escapeHtml(q) + '</div><div class="lib-ai-msg lib-ai-a" id="libAIThinking">正在想……</div>');
    chat.scrollTop = chat.scrollHeight;
    input.value = '';
    const sites = _libSiteList();
    const siteLines = sites.map(s => '- ' + s.name + '：' + (s.desc || '')).join('\n');
    const system = '你是「六月息」史料库的文献资源导购员。用户想找某类历史资料但不知道去哪个网站/数据库。' +
        '下面是本库已收录的全部站点（名称：简介）。回答要求：1) 从已收录站点里挑最合适的，说出站点名和它为什么合适；' +
        '2) 如果库里没有合适的，如实说明，并可补充推荐库外知名的公开资源；3) 回答控制在 200 字内，直接给结论，不要寒暄；' +
        '4) 涉及访问限制（需校园网/VPN/翻墙）要提醒。已收录站点：\n' + siteLines;
    const history = window._libAIHistory.slice(-6);
    history.push({ role: 'user', content: q });
    fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'system', content: system }].concat(history) })
    }).then(r => r.json()).then(d => {
        const thinking = document.getElementById('libAIThinking');
        let answer = (d.response || d.message || d.text || '').trim() || '（没有收到回答）';
        answer = escapeHtml(answer);
        answer = answer.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
        // 站名自动变链接(先转义后替换,站名是中文不受影响)
        sites.forEach(s => {
            if (answer.indexOf(s.name) >= 0) {
                answer = answer.split(s.name).join('<a href="' + s.href + '" target="_blank" class="lib-ai-link">' + s.name + '</a>');
            }
        });
        if (thinking) thinking.outerHTML = '<div class="lib-ai-msg lib-ai-a">' + answer.replace(/\n/g, '<br>') + '</div>';
        window._libAIHistory.push({ role: 'user', content: q });
        window._libAIHistory.push({ role: 'assistant', content: (d.response || d.message || d.text || '').trim() });
        chat.scrollTop = chat.scrollHeight;
        if (btn) btn.disabled = false;
    }).catch(err => {
        const thinking = document.getElementById('libAIThinking');
        if (thinking) thinking.outerHTML = '<div class="lib-ai-msg lib-ai-a">请求失败：' + escapeHtml(String(err).slice(0, 80)) + '</div>';
        if (btn) btn.disabled = false;
    });
}
window.libAISend = libAISend;

// ── 读文献页 ─────────────────────────────────────────
let _rdLoadedOnce = false;
async function loadReading() {
    _rdLoadedOnce = true;
    await Promise.all([rdLoadLibrary(''), rdLoadRecentAdd(), rdLoadRecentRead()]);
}

async function rdLoadLibrary(q) {
    const list = document.getElementById('rdList');
    const meta = document.getElementById('rdMeta');
    if (!list) return;
    list.innerHTML = '<div class="empty-hint">连接 Zotero……</div>';
    let res;
    try {
        res = await fetch('/api/zotero/library' + (q ? ('?q=' + encodeURIComponent(q)) : ''));
    } catch (e) {
        list.innerHTML = '<div class="empty-hint">连接失败：Zotero 客户端未启动（或本地 23119 端口不通）。打开 Zotero 后点搜索重试。</div>';
        return;
    }
    if (res.status === 404) {
        list.innerHTML = '<div class="empty-hint">Zotero 联动插件未启用。到「插件」管理页开启 zotero 插件后重试。</div>';
        if (meta) meta.textContent = '';
        return;
    }
    try {
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'fail');
        if (meta) meta.textContent = data.total + ' 篇文献' + (q ? (' · 关键词「' + q + '」') : '');
        if (!data.items.length) {
            list.innerHTML = '<div class="empty-hint">没有找到文献。在 Zotero 里导入后会自动出现在这里；也可以换个关键词搜。</div>';
            return;
        }
        list.innerHTML = data.items.map(it => `
            <div class="doc-item rd-item" onclick="rdOpen('${it.key}')">
                <div class="doc-title">${escapeHtml(it.title)}</div>
                <div class="doc-meta">${escapeHtml(it.creators || '佚名')}${it.year ? ' · ' + it.year : ''} · ${{journalArticle:'期刊',book:'专著',bookSection:'章节',thesis:'学位论文',report:'报告',conferencePaper:'会议',encyclopediaArticle:'百科',document:'文献',manuscript:'手稿',newspaperArticle:'报纸'}[it.itemType] || it.itemType}</div>
            </div>`).join('');
    } catch (e) {
        list.innerHTML = '<div class="empty-hint">文献库加载失败：' + escapeHtml(String(e).slice(0, 80)) + '</div>';
    }
}
window.rdLoadLibrary = rdLoadLibrary;

function rdSearch() {
    const q = (document.getElementById('rdSearch')?.value || '').trim();
    rdLoadLibrary(q);
}
window.rdSearch = rdSearch;

let _rdCurrent = null; // { key, title, attKey, creators, year, itemType }

async function rdOpen(key) {
    try {
        const res = await fetch('/api/zotero/item/' + key + '/attachments');
        const data = await res.json();
        if (!data.ok || !data.attachments || !data.attachments.length) {
            showToast('这条文献没有 PDF 附件', 'error');
            return;
        }
        const pdf = data.attachments.find(x => x.isPdf) || data.attachments[0];
        // 取该条题录信息(作者/年份/标题)
        let meta = { creators: '', year: '', title: '', itemType: '' };
        try {
            const libRes = await fetch('/api/zotero/library');
            const lib = await libRes.json();
            const it = (lib.items || []).find(x => x.key === key);
            if (it) meta = it;
        } catch (e) {}
        _rdCurrent = { key, attKey: pdf.key, title: meta.title || pdf.title || '(PDF)',
                       creators: meta.creators || '', year: meta.year || '', itemType: meta.itemType || '' };
        const viewer = document.getElementById('rdViewer');
        const listWrap = document.getElementById('rdListWrap');
        const header = document.getElementById('rdLibHeader');
        if (viewer && listWrap) {
            listWrap.style.display = 'none';
            if (header) header.style.display = 'none';
            viewer.style.display = '';
            document.getElementById('rdViewerTitle').textContent = _rdCurrent.title;
            document.getElementById('rdPdfFrame').src = '/api/zotero/pdf/' + pdf.key;
            const area = document.getElementById('rdNoteArea');
            if (area) area.value = '';
            const saved = document.getElementById('rdNoteSaved');
            if (saved) saved.textContent = '';
        } else {
            window.open('/api/zotero/pdf/' + pdf.key, '_blank');
        }
        rdLoadRecentRead();
    } catch (e) {
        showToast('打开失败：' + String(e).slice(0, 60), 'error');
    }
}
window.rdOpen = rdOpen;

function rdBackToList() {
    const viewer = document.getElementById('rdViewer');
    const listWrap = document.getElementById('rdListWrap');
    const header = document.getElementById('rdLibHeader');
    if (viewer) viewer.style.display = 'none';
    if (listWrap) listWrap.style.display = '';
    if (header) header.style.display = '';
    _rdCurrent = null;
}
window.rdBackToList = rdBackToList;

function rdOpenExt() {
    if (_rdCurrent && _rdCurrent.attKey) {
        window.open('/api/zotero/pdf/' + _rdCurrent.attKey, '_blank');
    }
}
window.rdOpenExt = rdOpenExt;

async function rdSaveNote() {
    const area = document.getElementById('rdNoteArea');
    const saved = document.getElementById('rdNoteSaved');
    if (!area || !area.value.trim()) { showToast('先写点内容再保存', 'error'); return; }
    if (!_rdCurrent) return;
    try {
        const res = await fetch('/api/obsidian/zotero-note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: _rdCurrent.title,
                content: area.value,
                meta: { creators: _rdCurrent.creators, year: _rdCurrent.year,
                        itemType: _rdCurrent.itemType, zoteroKey: _rdCurrent.key }
            })
        });
        const d = await res.json();
        if (d.ok) {
            if (saved) saved.textContent = '✓ 已保存 ' + new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            showToast('已存到 Obsidian 文献笔记', 'success');
        } else {
            showToast('保存失败：' + (d.error || ''), 'error');
        }
    } catch (e) {
        showToast('保存失败：' + String(e).slice(0, 60), 'error');
    }
}
window.rdSaveNote = rdSaveNote;

async function rdLoadRecentAdd() {
    const box = document.getElementById('rdRecentAdd');
    if (!box) return;
    try {
        const res = await fetch('/api/zotero/recent?limit=6');
        const data = await res.json();
        if (!data.ok || !data.items.length) { box.innerHTML = '<div class="empty-hint">暂无</div>'; return; }
        box.innerHTML = data.items.map(it => `
            <div class="doc-item rd-item rd-mini" onclick="rdOpen('${it.key}')">
                <div class="doc-title">${escapeHtml(it.title)}</div>
                <div class="doc-meta">${it.year || ''}</div>
            </div>`).join('');
    } catch (e) { box.innerHTML = '<div class="empty-hint">连接失败</div>'; }
}

async function rdLoadRecentRead() {
    const box = document.getElementById('rdRecentRead');
    const resumePanel = document.getElementById('rdResumePanel');
    if (!box) return;
    try {
        const res = await fetch('/api/zotero/recently-read?limit=6');
        const data = await res.json();
        const items = data.items || [];
        if (!items.length) {
            box.innerHTML = '<div class="empty-hint">还没有阅读记录</div>';
            if (resumePanel) resumePanel.style.display = 'none';
            return;
        }
        box.innerHTML = items.slice(0, 5).map(it => `
            <div class="doc-item rd-item rd-mini" onclick="rdOpenByAtt('${it.att_key || ''}', '${it.key || ''}')">
                <div class="doc-title">${escapeHtml(it.title || '(PDF)')}</div>
                <div class="doc-meta">${it.read_at || ''}</div>
            </div>`).join('');
        // 继续阅读横幅: 最近一篇
        const last = items[0];
        if (last && resumePanel) {
            resumePanel.style.display = '';
            document.getElementById('rdResume').innerHTML = `
                <div class="doc-item rd-item" onclick="rdOpenByAtt('${last.att_key || ''}', '${last.key || ''}')">
                    <div class="doc-title">⏯️ ${escapeHtml(last.title || '(PDF)')}</div>
                    <div class="doc-meta">上次读到 ${last.read_at || '最近'} · 点击继续</div>
                </div>`;
        }
    } catch (e) { box.innerHTML = '<div class="empty-hint">连接失败</div>'; }
}

async function rdOpenByAtt(attKey, parentKey) {
    if (attKey) {
        window.open('/api/zotero/pdf/' + attKey, '_blank');
        rdLoadRecentRead();
    } else if (parentKey) {
        rdOpen(parentKey);
    }
}
window.rdOpenByAtt = rdOpenByAtt;

// 初始计数
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { try { filterLibrary(''); } catch (e) {} });
} else {
    try { filterLibrary(''); } catch (e) {}
}

async function loadRecentActivity() {
    const container = document.getElementById('activityTimeline');
    if (!container) return;
    const ICONS = { read: '📖', note: '✏️', search: '🔍' };
    try {
        const res = await fetch('/api/activity/recent?limit=6');
        const data = await res.json();
        if (data.ok && data.items && data.items.length) {
            container.innerHTML = data.items.map(a => {
                const d = new Date(a.t * 1000);
                const hh = String(d.getHours()).padStart(2, '0'), mm = String(d.getMinutes()).padStart(2, '0');
                return `<div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">${ICONS[a.act] || '·'} ${escapeHtml(a.label || '')} <span style="color:var(--text-muted);font-size:11px">${hh}:${mm}</span></div>
                </div>`;
            }).join('');
        } else {
            container.innerHTML = '<div class="empty-hint">在 JX 里读论文、存笔记、查 CBDB, 足迹自动记在这里</div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="empty-hint">读取失败</div>';
    }
}


let _kbData = null;
// ── 学术知识库 · 星辰大海 ────────────────────────────
let _kbFilterQ = '';
let _kbFilterTheme = '';
let _kbSelEntry = null;

const KB_GLYPH = { zhixue: '\u2726', shiliao: '\u2739', jiansuo: '\u2756', lunwen: '\u2727', shuping: '\u273b', guifan: '\u00a7', daode: '\u2696' };
function _kbGlyph(key, themes) {
    const t = (themes || []).find(x => x.key === key);
    return (KB_GLYPH[key] || '\u2726') + ' ' + (t ? t.name : key);
}

function _kbRand(seed) {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
}

function renderKbList(container) {
    if (!container) return;
    const data = _kbData;
    if (!data || !Array.isArray(data.entries)) {
        container.innerHTML = '<div class="empty-hint">知识库加载失败</div>';
        return;
    }
    const themes = data.themes || [];
    const entries = data.entries;
    const byTheme = {};
    entries.forEach(e => { (byTheme[e.theme] = byTheme[e.theme] || []).push(e); });

    const chips = themes.map(t => {
        const n = (byTheme[t.key] || []).length;
        const on = !_kbFilterTheme || _kbFilterTheme === t.key;
        return `<span class="kb-chip${(_kbFilterTheme === t.key) ? ' on' : ''}" data-theme="${t.key}" onclick="kbSetTheme('${_kbFilterTheme === t.key ? '' : t.key}')" style="border-color:${t.color};color:${t.color}">${KB_GLYPH[t.key] || '\u2726'} ${t.name}·${n}</span>`;
    }).join('');

    container.innerHTML = `
      <div class="kb-toolbar">
        <input id="kbSearch" class="kb-search" placeholder="在这片星空中检索…" value="${_kbFilterQ.replace(/"/g, '&quot;')}" oninput="kbFilter(this.value)">
        <button class="kb-sea-btn" onclick="kbOpenSea()" title="全屏漫游星海">⤢ 星海</button>
        <span class="kb-count" id="kbCount">${entries.length} 颗星辰 · ${themes.length} 个星座</span>
      </div>
      <div class="kb-chips">${chips}</div>
      <div class="kb-mini-land" id="kbMiniLand"></div>
      <div class="kb-stars-wrap" id="kbMiniStars" style="display:none"><svg id="kbSvg" viewBox="0 0 1000 470" preserveAspectRatio="xMidYMid meet"></svg><div class="kb-tip" id="kbTip" style="display:none"></div></div>
      <div class="kb-detail" id="kbDetail" style="display:none"></div>
      <div class="tip-refresh">${escapeHtml(data.source || '')} · ⤢ 星海 全屏漫游</div>`;

    kbMiniLand();
}

function kbMiniLand() {
    const box = document.getElementById('kbMiniLand');
    if (!box || !_kbData) return;
    const e = _kbPick();
    if (!e) return;
    const themes = _kbData.themes || [];
    const th = themes.find(t => t.key === e.theme) || {};
    box.style.display = 'block';
    document.getElementById('kbMiniStars').style.display = 'none';
    box.innerHTML = `
      <div class="kb-ml-star" style="color:${th.color || '#c9a96e'}">\u2726</div>
      <div class="kb-ml-text" onclick="kbShowEntry(${e.id})" title="展开这一条">${escapeHtml(e.text)}</div>
      <div class="kb-ml-meta">
        <span style="color:${th.color || '#c9a96e'}">${_kbGlyph(e.theme, themes)}</span>
        <span class="kb-detail-src">${escapeHtml(e.src || '')}</span>
        <span class="kb-ml-actions">
          <button onclick="kbMiniLand()" title="换一颗">⚀</button>
          <button onclick="kbMiniMap()" title="看小星图">✦</button>
          <button onclick="kbOpenSea()" title="全屏星海">⤢</button>
        </span>
      </div>`;
}
window.kbMiniLand = kbMiniLand;

function kbMiniMap() {
    const box = document.getElementById('kbMiniLand');
    if (box) box.style.display = 'none';
    document.getElementById('kbMiniStars').style.display = 'block';
    _kbHideDetail();
    if (!document.getElementById('kbSvg').innerHTML) _kbDrawStars();
}
window.kbMiniMap = kbMiniMap;


function _kbEntryMatch(e) {
    if (_kbFilterTheme && e.theme !== _kbFilterTheme) return false;
    if (_kbFilterQ) {
        const q = _kbFilterQ.toLowerCase();
        return (e.text || '').toLowerCase().includes(q) || (e.src || '').toLowerCase().includes(q);
    }
    return true;
}

function _kbDrawStars(svgId) {
    svgId = svgId || 'kbSvg';
    const inSea = (svgId === 'kbSvgSea');
    const svg = document.getElementById(svgId);
    if (!svg || !_kbData) return;
    const themes = _kbData.themes || [];
    const entries = _kbData.entries || [];
    const byTheme = {};
    entries.forEach(e => { (byTheme[e.theme] = byTheme[e.theme] || []).push(e); });

    // 星座区: 上排4个 下排3个(居中)
    const cols = [130, 375, 620, 865];
    const rows = [128, 348];
    const positions = [
        [cols[0], rows[0]], [cols[1], rows[0]], [cols[2], rows[0]], [cols[3], rows[0]],
        [210, rows[1]], [500, rows[1]], [790, rows[1]]
    ];

    let html = '';
    let matchCount = 0;
    const starPos = {};
    { const brnd = _kbRand(20261004);
      for (let bi = 0; bi < 110; bi++) {
          const bx = brnd() * 1000, by = brnd() * 470, brr = 0.4 + brnd() * 0.9;
          html += `<circle cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="${brr.toFixed(2)}" fill="#cfd6e4" opacity="${(0.10 + brnd() * 0.30).toFixed(2)}"/>`;
      } }

    themes.forEach((t, ti) => {
        const list = byTheme[t.key] || [];
        const [cx, cy] = positions[ti] || [500, 300];
        const rnd = _kbRand(t.key.length * 7919 + ti * 104729);

        // 星座名
        html += `<text x="${cx}" y="${cy}" text-anchor="middle" class="kb-constellation" fill="${t.color}" style="filter:drop-shadow(0 0 7px ${t.color})">${_kbGlyph(t.key, themes)}</text>`;

        // 星位: 高斯散布 + 两轮排斥, 出圈拉回
        const spread = list.length <= 6 ? 0.72 : (list.length >= 12 ? 1.0 : 0.85);
        const coords = list.map((e, ei) => {
            const g = () => (rnd() + rnd() + rnd() - 1.5) * 46 * spread;
            return { e, x: cx + g() * 1.5, y: cy + g() };
        });
        for (let round = 0; round < 2; round++) {
            for (let p = 0; p < coords.length; p++) for (let q = p + 1; q < coords.length; q++) {
                const A2 = coords[p], B2 = coords[q];
                const dx = A2.x - B2.x, dy = A2.y - B2.y;
                const d2 = dx * dx + dy * dy;
                if (d2 < 26 * 26 && d2 > 0.01) {
                    const d = Math.sqrt(d2), push = (26 - d) / 2;
                    const ux = dx / d, uy = dy / d;
                    A2.x += ux * push; A2.y += uy * push;
                    B2.x -= ux * push; B2.y -= uy * push;
                }
            }
        }
        coords.forEach(c => {
            c.x = Math.max(30, Math.min(970, c.x));
            c.y = Math.max(30, Math.min(440, c.y));
        });

        // 连线: 每星仅连最近邻居(意象星座线)
        for (let k = 0; k < coords.length; k++) {
            let best = -1, bd = 115;
            for (let m = 0; m < coords.length; m++) {
                if (m === k) continue;
                const dx = coords[k].x - coords[m].x, dy = coords[k].y - coords[m].y;
                const d = Math.sqrt(dx * dx + dy * dy);
                if (d < bd) { bd = d; best = m; }
            }
            if (best >= 0 && best > k) {
                const A2 = coords[k], B2 = coords[best];
                const dimA = _kbEntryMatch(A2.e), dimB = _kbEntryMatch(B2.e);
                const op = (dimA && dimB) ? 0.26 : 0.04;
                html += `<line x1="${A2.x}" y1="${A2.y}" x2="${B2.x}" y2="${B2.y}" stroke="${t.color}" stroke-width="0.5" opacity="${op}"/>`;
            }
        }

        // 星辰
        coords.forEach(({ e, x, y }) => {
            const on = _kbEntryMatch(e);
            if (on) matchCount++;
            const r = e.text.length > 90 ? 6.2 : (e.text.length > 55 ? 4.8 : 3.4);
            const op = on ? 0.95 : 0.07;
            const phase = (e.id % 7) * 0.5;
            starPos[e.id] = { x, y };
            html += `<circle cx="${x}" cy="${y}" r="${r * 2.4}" fill="${t.color}" opacity="${on ? 0.26 : 0.03}" class="kb-star-glow" style="animation-delay:-${phase}s"/>`;
            html += `<circle cx="${x}" cy="${y}" r="${r}" fill="${t.color}" opacity="${op}" class="kb-star" data-id="${e.id}" style="cursor:pointer"/>`;
            if (on && r >= 4.8) html += `<circle cx="${x}" cy="${y}" r="${r * 0.36}" fill="#fff8ec" opacity="0.75" class="kb-star-core"/>`;
        });
    });

    svg.innerHTML = html;

    // 交互
    const tip = document.getElementById(inSea ? 'kbTipSea' : 'kbTip');
    svg.querySelectorAll('.kb-star').forEach(el => {
        const id = parseInt(el.dataset.id, 10);
        const e = entries.find(x => x.id === id);
        if (!e) return;
        const th = themes.find(t => t.key === e.theme) || {};
        el.addEventListener('mousemove', (ev) => {
            const wrap = svg.parentElement.getBoundingClientRect();
            tip.style.display = 'block';
            tip.style.left = Math.min(ev.clientX - wrap.left + 14, wrap.width - 250) + 'px';
            tip.style.top = (ev.clientY - wrap.top + 10) + 'px';
            tip.innerHTML = `<div class="kb-tip-theme" style="color:${th.color || '#c9a96e'}">${th.icon || ''} ${th.name || ''} <span class="kb-tip-src">${escapeHtml(e.src || '')}</span></div><div class="kb-tip-text">${escapeHtml(e.text.slice(0, 72))}${e.text.length > 72 ? '…' : ''}</div>`;
        });
        el.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
        el.addEventListener('click', (ev) => {
            ev.stopPropagation();
            tip.style.display = 'none';
            kbShowEntry(id, inSea);
        });
    });

    const cnt = document.getElementById(inSea ? 'kbCountSea' : 'kbCount');
    if (cnt) cnt.textContent = (_kbFilterQ || _kbFilterTheme) ? `匹配 ${matchCount} 颗星辰` : `${entries.length} 颗星辰 · ${themes.length} 个星座`;
}

let _kbFilterTimer = null;
function kbFilter(v) {
    _kbFilterQ = (v || '').trim();
    clearTimeout(_kbFilterTimer);
    _kbFilterTimer = setTimeout(() => { _kbSelEntry = null; _kbHideDetail(); _kbHideDetail(true); _kbDrawStars(); const seaSvg = document.getElementById('kbSvgSea'); if (seaSvg && seaSvg.innerHTML) _kbDrawStars('kbSvgSea'); if (document.getElementById('kbSeaOverlay') && document.getElementById('kbLand') && document.getElementById('kbLand').style.display !== 'none') kbLand(); }, 220);
}

function kbSetTheme(key) {
    _kbFilterTheme = key || '';
    _kbSelEntry = null;
    _kbHideDetail();
    const container = document.getElementById('papersList');
    if (container) renderKbList(container);
}

function kbShowEntry(id, inSea) {
    const entries = (_kbData && _kbData.entries) || [];
    const themes = (_kbData && _kbData.themes) || [];
    const e = entries.find(x => x.id === id);
    if (!e) return;
    _kbSelEntry = id;
    try { window._logActivity('kb-read', '学术知识库：' + (e.text || '').slice(0, 24)); } catch (err) {}
    const th = themes.find(t => t.key === e.theme) || {};
    const detail = document.getElementById(inSea ? 'kbDetailSea' : 'kbDetail');
    if (!detail) return;
    if (inSea) {
        const land = document.getElementById('kbLand');
        if (land) land.style.display = 'none';
        const pane = document.getElementById('kbStarsPane');
        if (pane) pane.style.display = 'block';
        if (!document.getElementById('kbSvgSea').innerHTML) _kbDrawStars('kbSvgSea');
    } else {
        const box = document.getElementById('kbMiniLand');
        if (box) box.style.display = 'none';
        document.getElementById('kbMiniStars').style.display = 'block';
        if (!document.getElementById('kbSvg').innerHTML) _kbDrawStars();
    }
    // 同星座导航
    const sibs = entries.filter(x => x.theme === e.theme);
    const idx = sibs.findIndex(x => x.id === id);
    const prev = sibs[(idx - 1 + sibs.length) % sibs.length];
    const next = sibs[(idx + 1) % sibs.length];
    detail.style.display = 'block';
    detail.innerHTML = `
      <div class="kb-detail-head">
        <span class="kb-detail-theme" style="color:${th.color || '#c9a96e'};border-color:${th.color || '#c9a96e'}">${th.icon || ''} ${th.name || ''}</span>
        <span class="kb-detail-src">${escapeHtml(e.src || '')}</span>
        <span class="kb-detail-close" onclick="kbHideDetail()" title="关闭">×</span>
      </div>
      <div class="kb-detail-text">${escapeHtml(e.text)}</div>
      <div class="kb-detail-nav">
        <button onclick="kbShowEntry(${prev.id}, ${inSea ? 'true' : 'false'})" class="kb-nav-btn">← ${escapeHtml((prev.text || '').slice(0, 14))}…</button>
        <button onclick="kbAskAI(${e.id})" class="kb-nav-btn" title="带着这一条去问 AI 助手">✦ 问 AI</button>
        <button onclick="${inSea ? 'kbHideDetail(true);kbShowMap()' : 'kbHideDetail();kbMiniLand()'}" class="kb-nav-btn">收起</button>
        <button onclick="kbShowEntry(${next.id}, ${inSea ? 'true' : 'false'})" class="kb-nav-btn">${escapeHtml((next.text || '').slice(0, 14))}… →</button>
      </div>`;
    detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
window.kbShowEntry = kbShowEntry;

function kbOpenSea() {
    if (document.getElementById('kbSeaOverlay')) return;
    const ov = document.createElement('div');
    ov.id = 'kbSeaOverlay';
    ov.className = 'kb-sea-overlay';
    ov.innerHTML = `
      <div class="kb-sea-head">
        <span class="kb-sea-title">学术写作知识库 · 星辰大海</span>
        <input id="kbSearchSea" class="kb-search" placeholder="在这片星空中检索…" value="${_kbFilterQ.replace(/"/g, '&quot;')}" oninput="kbFilter(this.value)">
        <span class="kb-count" id="kbCountSea"></span>
        <button class="kb-sea-close" onclick="kbCloseSea()" title="关闭 (ESC)">×</button>
      </div>
      <div class="kb-chips kb-chips-sea">${(_kbData.themes || []).map(t => {
          const n = (_kbData.entries || []).filter(e => e.theme === t.key).length;
          return `<span class="kb-chip${(_kbFilterTheme === t.key) ? ' on' : ''}" onclick="kbSetTheme('${_kbFilterTheme === t.key ? '' : t.key}')" style="border-color:${t.color};color:${t.color}">${KB_GLYPH[t.key] || '\u2726'} ${t.name}·${n}</span>`;
      }).join('')}</div>
      <div class="kb-sea-body">
        <div class="kb-land" id="kbLand"></div>
        <div class="kb-stars-wrap kb-stars-sea" id="kbStarsPane" style="display:none"><svg id="kbSvgSea" viewBox="0 0 1000 470" preserveAspectRatio="xMidYMid meet"></svg><div class="kb-tip" id="kbTipSea" style="display:none"></div></div>
      </div>
      <div class="kb-detail kb-detail-sea" id="kbDetailSea" style="display:none"></div>
      <div class="kb-sea-foot">${escapeHtml((_kbData && _kbData.source) || '')} · ESC 退出</div>`;
    document.body.appendChild(ov);
    document.body.style.overflow = 'hidden';
    kbLand();
    ov.setAttribute('tabindex', '-1');
    ov.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { kbCloseSea(); return; }
        const landVisible = document.getElementById('kbLand') && document.getElementById('kbLand').style.display !== 'none';
        if (landVisible && (e.key === ' ' || e.key === 'ArrowRight')) { e.preventDefault(); kbReroll(); }
        if (landVisible && (e.key === 'm' || e.key === 'M' || e.key === 'ArrowUp')) kbShowMap();
    });
    ov.focus();
}
window.kbOpenSea = kbOpenSea;

function _kbPick() {
    const entries = (_kbData && _kbData.entries) || [];
    const pool = entries.filter(_kbEntryMatch);
    const src = pool.length ? pool : entries;
    return src[Math.floor(Math.random() * src.length)];
}

function kbLand() {
    const land = document.getElementById('kbLand');
    if (!land) return;
    const e = _kbPick();
    if (!e) return;
    const themes = (_kbData && _kbData.themes) || [];
    const th = themes.find(t => t.key === e.theme) || {};
    document.getElementById('kbStarsPane').style.display = 'none';
    land.style.display = 'flex';
    land.innerHTML = `
      <div class="kb-land-star" style="color:${th.color || '#c9a96e'}">\u2726</div>
      <div class="kb-land-text" onclick="kbShowEntry(${e.id}, true)">${escapeHtml(e.text)}</div>
      <div class="kb-land-meta">
        <span class="kb-detail-theme kb-theme-click" style="color:${th.color || '#c9a96e'};border-color:${th.color || '#c9a96e'}" onclick="kbSetTheme('${e.theme}')" title="只看这个星座">${_kbGlyph(e.theme, themes)}</span>
        <span class="kb-detail-src">${escapeHtml(e.src || '')}</span>
        <span class="kb-detail-src">第 ${e.id} / ${(_kbData.entries || []).length} 颗</span>
      </div>
      <div class="kb-land-actions">
        <button class="kb-nav-btn" onclick="kbShowEntry(${e.id}, true)">展开这一条 →</button>
        <button class="kb-nav-btn" onclick="kbReroll()">再来一颗 ⚀</button>
        <button class="kb-nav-btn" onclick="kbShowMap()">看全图 ✦</button>
      </div>`;
}
window.kbLand = kbLand;

function kbReroll() {
    const land = document.getElementById('kbLand');
    if (!land) return;
    land.style.opacity = '0';
    setTimeout(() => { kbLand(); land.style.opacity = '1'; }, 160);
}
window.kbReroll = kbReroll;

function kbShowMap() {
    const land = document.getElementById('kbLand');
    if (land) land.style.display = 'none';
    document.getElementById('kbStarsPane').style.display = 'block';
    _kbHideDetail(true);
    if (!document.getElementById('kbSvgSea').innerHTML) _kbDrawStars('kbSvgSea');
    const cnt = document.getElementById('kbCountSea');
    if (cnt) cnt.textContent = (_kbData.entries || []).length + ' 颗星辰';
}
window.kbShowMap = kbShowMap;

function kbAskAI(id) {
    const entries = (_kbData && _kbData.entries) || [];
    const e = entries.find(x => x.id === id);
    if (!e) return;
    try { kbCloseSea(); } catch (err) {}
    switchTab('ai');
    const input = document.getElementById('aiChatInput');
    if (input) {
        input.value = '请结合具体例子展开讲讲这条学术规范/方法：「' + e.text + '」（出处：荣新江《学术训练与学术规范》' + (e.src || '') + '）';
        setTimeout(() => { input.focus(); }, 150);
    }
}
window.kbAskAI = kbAskAI;

function kbCloseSea() {
    const ov = document.getElementById('kbSeaOverlay');
    if (ov) ov.remove();
    document.body.style.overflow = '';
    _kbHideDetail(true);
}
window.kbCloseSea = kbCloseSea;

function kbHideDetail(sea) {
    _kbSelEntry = null;
    _kbHideDetail(sea);
}
window.kbHideDetail = kbHideDetail;
function _kbHideDetail(sea) {
    const detail = document.getElementById(sea ? 'kbDetailSea' : 'kbDetail');
    if (detail) { detail.style.display = 'none'; detail.innerHTML = ''; }
}


async function loadPapersList() {
    const container = document.getElementById('papersList');
    if (!container) return;
    try {
        if (!_kbData) {
            const res = await fetch('/api/writing-kb');
            const data = await res.json();
            if (!data.ok) throw new Error('kb fail');
            _kbData = data;
        }
        renderKbList(container);
    } catch (e) {
        container.innerHTML = '<div class="empty-hint">知识库加载失败</div>';
    }
}

window.refreshTips = async function () {
    const container = document.getElementById('papersList');
    if (!container) return;
    try {
        const res = await fetch('/api/writing-tips?n=3&refresh=1');
        renderTips(container, await res.json());
    } catch (e) { /* 忽略 */ }
};

window.openReadingItem = function (key, attKey) {
    if (key) sessionStorage.setItem('jx.rd.pending', key);
    else if (attKey) sessionStorage.setItem('jx.rd.openpdf', attKey);
    switchTab('reading');
};

// ── 论文工作台 ─────────────────────────────────────────

// 当前查看/编辑的论文状态
let currentPaperPath = null;
let currentPaperContent = '';
let currentPaperTitle = '';
let currentEditingPath = null;

function showPaperEditor(existingPath = null, title = '', content = '') {
    currentEditingPath = existingPath;
    const preview = document.getElementById('paperPreview');
    const isNew = !existingPath;

    preview.innerHTML = `
        <div class="panel-header">
            <span class="panel-icon">✏️</span>
            ${isNew ? '新建论文' : '编辑：' + title}
        </div>
        <div class="paper-editor">
            <input type="text" id="paperTitleInput" class="paper-editor-title"
                placeholder="输入论文标题..." value="${title}"
                ${isNew ? '' : 'disabled'}>
            <textarea id="paperBodyInput" class="paper-editor-body"
                placeholder="开始写作...&#10;&#10;支持 Markdown 格式。&#10;&#10;## 摘要&#10;&#10;## 引言&#10;&#10;## 正文&#10;&#10;## 参考文献">${content}</textarea>
            <div class="paper-editor-actions">
                <button class="btn-primary" onclick="savePaper()">💾 保存到 Obsidian</button>
                ${isNew ? '' : `<button class="btn-secondary" onclick="viewPaper('${existingPath}')">取消</button>`}
                <span class="paper-editor-status" id="editorStatus"></span>
            </div>
        </div>
    `;

    if (isNew) {
        document.getElementById('paperTitleInput').focus();
    } else {
        document.getElementById('paperBodyInput').focus();
    }
}

async function savePaper() {
    const titleInput = document.getElementById('paperTitleInput');
    const bodyInput = document.getElementById('paperBodyInput');
    const status = document.getElementById('editorStatus');

    const title = titleInput.value.trim();
    const body = bodyInput.value.trim();

    if (!title) { showToast('请输入论文标题', 'warning'); titleInput.focus(); return; }
    if (!body) { showToast('正文不能为空', 'warning'); bodyInput.focus(); return; }

    status.innerHTML = '<div class="loading" style="width:14px;height:14px"></div> 保存中...';

    const filename = title.endsWith('.md') ? title : title + '.md';
    const path = `论文/${filename}`;
    const content = `# ${title.replace('.md', '')}\n\n${body}\n`;

    try {
        const res = await fetch(`/api/obsidian/note/${encodeURIComponent(path)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        try { window._logActivity('quick-note', '快速笔记 ' + (content || '').slice(0, 30)); } catch (e) {}
        const data = await res.json();

        if (!data.error) {
            showToast('已保存到 Obsidian！', 'success');
            currentEditingPath = path;
            loadWorkspace();
            viewPaper(path);
        } else {
            status.textContent = '';
            showToast('保存失败：' + data.error, 'error');
        }
    } catch (e) {
        status.textContent = '';
        showToast('保存失败：' + e.message, 'error');
    }
}

async function loadWorkspace() {
    const container = document.getElementById('workspacePapers');
    try {
        const res = await fetch('/api/obsidian/notes?folder=论文');
        const data = await res.json();

        document.getElementById('wsPaperCount').textContent = Array.isArray(data) ? data.length : 0;

        if (Array.isArray(data) && data.length > 0) {
            container.innerHTML = data.map(f => `
                <div class="doc-item" onclick="viewPaper('${f.path || ('论文/' + (f.basename || f))}')" style="cursor:pointer">
                    <div class="doc-icon">📄</div>
                    <div class="doc-info">
                        <div class="doc-title">${(f.basename || f).replace('.md', '')}</div>
                    </div>
                </div>
            `).join('');

            // 自动加载第一篇论文
            viewPaper(data[0].path || `论文/${data[0].basename || data[0]}`);
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <div class="empty-state-text">暂无论在研论文</div>
                    <div class="empty-state-hint">点击下方「新建」创建论文</div>
                </div>
            `;
            document.getElementById('wsPaperCount').textContent = '0';
        }

        loadWorkspaceStats();
    } catch {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">无法加载</div>
                <div class="empty-state-hint">请确认 Obsidian 已连接</div>
            </div>
        `;
    }
}

async function viewPaper(path) {
    currentPaperPath = path;
    const preview = document.getElementById('paperPreview');
    const title = path.split('/').pop().replace('.md', '');
    currentPaperTitle = title;

    preview.innerHTML = `
        <div class="panel-header"><span class="panel-icon">📄</span> ${title}</div>
        <div class="loading" style="margin:20px auto;display:block"></div>
    `;

    try {
        const res = await fetch(`/api/obsidian/note/${encodeURIComponent(path)}`);
        const data = await res.json();
        if (data.error) {
            preview.innerHTML = `
                <div class="panel-header"><span class="panel-icon">📄</span> ${title}</div>
                <div class="empty-state">
                    <div class="empty-state-icon">⚠️</div>
                    <div class="empty-state-text">无法读取文件</div>
                </div>
            `;
            return;
        }

        const content = data.content || '';
        currentPaperContent = content;
        const lines = content.split('\n');
        const previewText = lines.slice(0, 50).join('\n');
        const totalChars = content.replace(/\s/g, '').length;

        preview.innerHTML = `
            <div class="panel-header"><span class="panel-icon">📄</span> ${title}</div>
            <div class="paper-meta-bar">
                <span class="paper-meta-item">📝 ${totalChars} 字</span>
                <span class="paper-meta-item">📋 ${lines.length} 行</span>
            </div>
            <div class="file-preview">${previewText}${lines.length > 50 ? '\n\n... (更多内容请在 Obsidian 中查看)' : ''}</div>
            <div class="paper-actions">
                <button class="btn-primary" onclick="editCurrentPaper()">✏️ 编辑</button>
                <button class="btn-secondary" onclick="openObsidianURI('${path}')">在 Obsidian 中打开</button>
                <button class="btn-secondary" onclick="switchTab('ai')">AI 分析</button>
            </div>
        `;
    } catch (e) {
        preview.innerHTML = `
            <div class="panel-header"><span class="panel-icon">📄</span> ${title}</div>
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">加载失败</div>
            </div>
        `;
    }
}

function editCurrentPaper() {
    if (!currentPaperPath) return;
    showPaperEditor(currentPaperPath, currentPaperTitle, currentPaperContent);
}

async function loadWorkspaceStats() {
    try {
        const res = await fetch('/api/obsidian/stats');
        const stats = await res.json();
        const legacy = stats.legacy || {};

        const notes = legacy['札记'] || 0;
        const diary = legacy['日记'] || 0;
        document.getElementById('wsTodayNotes').textContent = notes + diary;
        const chars = stats.total_chars || 0;
        document.getElementById('wsTotalWords').textContent = chars > 10000 ? (chars / 10000).toFixed(1) + '万' : chars;
        document.getElementById('wsLastEdit').textContent = '今天';
    } catch {}
}

async function createPaper() {
    showPaperEditor();
}

// ── 史料库 ────────────────────────────────────────────

async function loadLibrary() {
    // 史料库页面以数据库导航为主，Vault 搜索由用户手动触发
}

async function viewLibraryFile(path) {
    const detail = document.getElementById('obsidianSearchResults');
    if (!detail) return;
    detail.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';

    try {
        const res = await fetch(`/api/obsidian/note/${encodeURIComponent(path)}`);
        const data = await res.json();
        const preview = data.content ? data.content.split('\n').slice(0, 30).join('\n') : '(空文件)';

        detail.innerHTML = `
            <div class="panel-header"><span class="panel-icon">📚</span> ${path.split('/').pop().replace('.md', '')}</div>
            <div class="file-preview">${preview}${data.content && data.content.split('\n').length > 30 ? '\n\n... (更多内容请在 Obsidian 中查看)' : ''}</div>
            <div style="margin-top:16px;display:flex;gap:10px">
                <button class="btn-primary" onclick="openObsidianURI('${path}')">在 Obsidian 中打开</button>
            </div>
        `;
    } catch (e) {
        detail.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">加载失败</div>
                <div class="empty-state-hint">${e.message}</div>
            </div>
        `;
    }
}

async function initVaultFolders() {
    showToast('正在创建标准文件夹...', 'info');
    try {
        const res = await fetch('/api/obsidian/init-folders', { method: 'POST' });
        const data = await res.json();
        if (data.created && data.created.length > 0) {
            showToast(`已创建：${data.created.join(', ')}`, 'success');
            loadLibrary();
        } else {
            showToast('文件夹已存在或创建失败', 'warning');
        }
    } catch (e) {
        showToast('初始化失败：' + e.message, 'error');
    }
}

// ── Vault 搜索 ─────────────────────────────────────────
async function searchVault() {
    const input = document.getElementById('obsidianSearchInput');
    const query = input ? input.value.trim() : '';
    if (!query) { showToast('请输入搜索关键词', 'warning'); return; }

    switchTab('cbdb'); // 临时用 CBDB 页显示搜索结果
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading"></div> 搜索中...';

    try {
        const res = await fetch(`/api/obsidian/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
            resultsDiv.innerHTML = data.slice(0, 10).map(f => `
                <div class="doc-item" onclick="openObsidianURI('${f.path || f}')">
                    <div class="doc-icon">📄</div>
                    <div class="doc-info">
                        <div class="doc-title">${(f.basename || f).replace('.md', '')}</div>
                        <div class="doc-meta">${f.path || ''}</div>
                    </div>
                </div>
            `).join('');
        } else {
            resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-text">未找到结果</div></div>';
        }
    } catch (e) {
        resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">搜索失败</div><div class="empty-state-hint">请检查 Obsidian Local REST API 是否已启用</div></div>';
    }
}

// ── CBDB 查询 ──────────────────────────────────────────
// CBDB 检索（复刻原生十大检索模块：人/官/地/社会关系/入仕/社会区分/著作/年份/综合）
window._cbdbType = 'person';
window._cbdbViewStack = [];
window._cbdbListView = null;
window._cbdbPlaceCache = {};
window._cbdbExport = null;
window._cbdbAdvState = { place: null, entry: null, office: null, status: null, text: null, assoc: null };
window._cbdbAssocState = { type: null };

const CBDB_TYPE_CONFIG = {
    person: { placeholder: '姓名/字/号/谥号/拼音/人物ID（如 王安石、介甫、1762）' },
    office: { placeholder: '输入官名（如 尚書、刺史），可叠加门类筛选' },
    place:  { placeholder: '输入地名（如 洛陽、開封），可叠加层级/年代' },
    assoc:  { placeholder: '' },
    pair:   { placeholder: '' },
    placeassoc: { placeholder: '' },
    entry:  { placeholder: '输入入仕方式（如 進士、蔭補）' },
    status: { placeholder: '输入身份类型（如 進士、封爵、孝廉）' },
    text:   { placeholder: '输入书名（如 資治通鑑、文選）' },
    year:   { placeholder: '' },
    adv:    { placeholder: '' },
};

// 社会关系大类（与后端 _ASSOC_CATEGORY_RULES 输出对应）
const CBDB_ASSOC_CATEGORIES = ['学术教育', '政治行政', '文学创作', '丧葬纪念', '交游应酬',
    '宗教方外', '刑戮迫害', '军事戎务', '艺术赏鉴', '婚姻亲属', '法律诉讼', '医疗照护', '财物往来', '其他'];

// 行政层级选项（ADDR_CODES c_admin_type 主要取值）
const CBDB_ADMIN_TYPES = [
    ['', '全部层级'], ['Xian', '县'], ['Zhou', '州'], ['Fu', '府'], ['Shi', '市/都市'],
    ['Jun', '郡'], ['Dao', '道'], ['Lu', '路'], ['Jiedu', '节度'], ['Dudufu', '都督府'],
    ['Fengjun', '封君'], ['Du', '都'], ['Wei', '卫'], ['Qi', '旗'],
];
// 数据里出现但主表未收的类型补充
const CBDB_ADMIN_TYPE_EXTRA = {
    County: '县', Shixiaqu: '市辖区', Mountain: '山', River: '河流', Lake: '湖泊',
    Island: '岛', Town: '镇', Jing: '京', Guan: '关', Xiang: '乡', Ting: '亭',
    Yi: '邑', Bao: '堡', Zhai: '寨', Zhou2: '洲', Gang: '岗', Qu: '区'
};
// c_admin_type 英译代码 → 中文标签（未知值原样显示，比裸代码友好）
function cbdbAdminTypeLabel(code) {
    if (!code) return '—';
    const hit = CBDB_ADMIN_TYPES.find(t => t[0] === code);
    if (hit) return hit[1];
    return CBDB_ADMIN_TYPE_EXTRA[code] || code;
}

// 渲染各类型对应的检索输入区
function renderCBDBSearchArea(type) {
    const area = document.getElementById('cbdbSearchArea');
    if (!area) return;
    if (type === 'adv') {
        // 原生 CBDB 综合查询全维度：各模块条件任意 AND 组合
        area.innerHTML = `
            <div class="cbdb-adv-form">
                <div class="cbdb-adv-section">人物</div>
                <div class="cbdb-adv-row">
                    <label>姓名</label>
                    <input type="text" id="cbdbAdvName" placeholder="姓名/字/号，支持模糊" ${''}>
                </div>
                <div class="cbdb-adv-row">
                    <label>朝代</label>
                    <select id="cbdbDynasty"><option value="">全部朝代</option></select>
                </div>
                <div class="cbdb-adv-row">
                    <label>性别</label>
                    <select id="cbdbAdvGender"><option value="">不限</option><option value="0">男</option><option value="1">女</option></select>
                </div>
                <div class="cbdb-adv-section">年份</div>
                <div class="cbdb-adv-row">
                    <label>指数年</label>
                    <input type="number" id="cbdbAdvFrom" placeholder="自" style="width:48%">
                    <span style="color:var(--text-muted)">至</span>
                    <input type="number" id="cbdbAdvTo" placeholder="至" style="width:48%">
                </div>
                <div class="cbdb-adv-row">
                    <label>生年</label>
                    <input type="number" id="cbdbAdvBirthFrom" placeholder="自" style="width:48%">
                    <span style="color:var(--text-muted)">至</span>
                    <input type="number" id="cbdbAdvBirthTo" placeholder="至" style="width:48%">
                </div>
                <div class="cbdb-adv-row">
                    <label>卒年</label>
                    <input type="number" id="cbdbAdvDeathFrom" placeholder="自" style="width:48%">
                    <span style="color:var(--text-muted)">至</span>
                    <input type="number" id="cbdbAdvDeathTo" placeholder="至" style="width:48%">
                </div>
                <div class="cbdb-adv-section">地址</div>
                <div class="cbdb-adv-row">
                    <label>地名</label>
                    <input type="text" id="cbdbAdvPlace" placeholder="输入地名，点击选择（可留空）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAdvPlaceList"></div>
                </div>
                <div class="cbdb-adv-row">
                    <label>类型</label>
                    <select id="cbdbAdvAddrType">
                        <option value="1">籍贯（含指数地址）</option>
                        <option value="5">祖籍（郡望）</option>
                        <option value="6">实际居址</option>
                        <option value="7">户籍地</option>
                        <option value="8">出生地</option>
                        <option value="9">葬地</option>
                        <option value="10">卒地</option>
                    </select>
                </div>
                <div class="cbdb-adv-section">入仕</div>
                <div class="cbdb-adv-row">
                    <label>方式</label>
                    <input type="text" id="cbdbAdvEntry" placeholder="入仕方式，点击选择（可留空）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAdvEntryList"></div>
                </div>
                <div class="cbdb-adv-row">
                    <label>入仕年</label>
                    <input type="number" id="cbdbAdvEntryFrom" placeholder="自" style="width:48%">
                    <span style="color:var(--text-muted)">至</span>
                    <input type="number" id="cbdbAdvEntryTo" placeholder="至" style="width:48%">
                </div>
                <div class="cbdb-adv-section">职官</div>
                <div class="cbdb-adv-row">
                    <label>官名</label>
                    <input type="text" id="cbdbAdvOffice" placeholder="官名，点击选择（可留空）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAdvOfficeList"></div>
                </div>
                <div class="cbdb-adv-row">
                    <label>任职年</label>
                    <input type="number" id="cbdbAdvOfficeFrom" placeholder="自" style="width:48%">
                    <span style="color:var(--text-muted)">至</span>
                    <input type="number" id="cbdbAdvOfficeTo" placeholder="至" style="width:48%">
                </div>
                <div class="cbdb-adv-section">身份 · 著作 · 关系</div>
                <div class="cbdb-adv-row">
                    <label>身份</label>
                    <input type="text" id="cbdbAdvStatus" placeholder="社会区分，点击选择（可留空）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAdvStatusList"></div>
                </div>
                <div class="cbdb-adv-row">
                    <label>著作</label>
                    <input type="text" id="cbdbAdvText" placeholder="著作名，点击选择（可留空）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAdvTextList"></div>
                </div>
                <div class="cbdb-adv-row">
                    <label>关系</label>
                    <input type="text" id="cbdbAdvAssoc" placeholder="社会关系类型（并入配对方向）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAdvAssocList"></div>
                </div>
                <button class="btn-primary" style="width:100%;margin-top:4px" onclick="runAdvancedQuery()">组合查询</button>
                <div class="cbdb-hint">全部条件按"且"组合；留空的条件不参与筛选</div>
            </div>`;
        const placeFetcher = async q => {
            const res = await fetch(`/api/cbdb/places/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            return (Array.isArray(data) ? data : []).map(p => ({ id: p.addr_id, label: p.name_chn, sub: p.firstyear ? `${p.firstyear}${p.lastyear ? '-' + p.lastyear : ''}` : (p.admin_type || '') }));
        };
        const pick = (key, inputId) => item => {
            window._cbdbAdvState[key] = item;
            const inp = document.getElementById(inputId);
            if (inp) inp.value = item.label + (item.sub ? `（${item.sub}）` : '');
        };
        bindCBDBAutocomplete('cbdbAdvPlace', 'cbdbAdvPlaceList', placeFetcher, pick('place', 'cbdbAdvPlace'));
        bindCBDBAutocomplete('cbdbAdvEntry', 'cbdbAdvEntryList',
            async q => {
                const res = await fetch(`/api/cbdb/entries/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(e => ({ id: e.code, label: e.name_chn, sub: e.name_eng }));
            },
            pick('entry', 'cbdbAdvEntry'));
        bindCBDBAutocomplete('cbdbAdvOffice', 'cbdbAdvOfficeList',
            async q => {
                const res = await fetch(`/api/cbdb/offices/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(o => ({ id: o.office_id, label: o.office_chn, sub: [o.dynasty, o.category].filter(Boolean).join(' · ') }));
            },
            pick('office', 'cbdbAdvOffice'));
        bindCBDBAutocomplete('cbdbAdvStatus', 'cbdbAdvStatusList',
            async q => {
                const res = await fetch(`/api/cbdb/status/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(s => ({ id: s.code, label: s.name_chn, sub: s.name_eng }));
            },
            pick('status', 'cbdbAdvStatus'));
        bindCBDBAutocomplete('cbdbAdvText', 'cbdbAdvTextList',
            async q => {
                const res = await fetch(`/api/cbdb/texts/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(tx => ({ id: tx.text_id, label: tx.title_chn, sub: tx.dynasty || '' }));
            },
            pick('text', 'cbdbAdvText'));
        bindCBDBAutocomplete('cbdbAdvAssoc', 'cbdbAdvAssocList',
            async q => {
                const res = await fetch(`/api/cbdb/assoc/types?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(x => ({ id: x.code, label: x.name_chn, sub: x.category }));
            },
            pick('assoc', 'cbdbAdvAssoc'));
        loadCBDBDynasties();
    } else if (type === 'assoc') {
        // 社会关系检索（原生十大模块之五）：大类 + 类型搜索 + pair/年份/朝代过滤
        const catOpts = ['<option value="">全部大类</option>']
            .concat(CBDB_ASSOC_CATEGORIES.map(c => `<option value="${c}">${c}</option>`)).join('');
        area.innerHTML = `
            <div class="cbdb-adv-form">
                <div class="cbdb-adv-row">
                    <label>大类</label>
                    <select id="cbdbAssocCat">${catOpts}</select>
                </div>
                <div class="cbdb-adv-row">
                    <label>关系</label>
                    <input type="text" id="cbdbAssocInput" placeholder="搜索关系类型（如 師、門生、墓誌、同年）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbAssocList"></div>
                </div>
                <div id="cbdbAssocChips"></div>
                <div class="cbdb-adv-row">
                    <label>年份</label>
                    <input type="number" id="cbdbAssocFrom" placeholder="起" style="width:48%">
                    <span style="color:var(--text-muted)">—</span>
                    <input type="number" id="cbdbAssocTo" placeholder="止" style="width:48%">
                </div>
                <div class="cbdb-adv-row">
                    <label>朝代</label>
                    <select id="cbdbDynasty"><option value="">全部朝代</option></select>
                </div>
                <div class="cbdb-adv-row" style="flex-direction:row;align-items:center;gap:6px">
                    <input type="checkbox" id="cbdbAssocPair" checked style="width:auto">
                    <label for="cbdbAssocPair" style="flex:1">含配对关系（如 師長↔門生 双向）</label>
                </div>
                <button class="btn-primary" style="width:100%;margin-top:4px" onclick="runAssocQuery()">查询关系</button>
                <div class="cbdb-hint">社会关系多未标年份，设年份区间会大幅收窄结果</div>
            </div>`;
        bindCBDBAutocomplete('cbdbAssocInput', 'cbdbAssocList',
            async q => {
                const cat = (document.getElementById('cbdbAssocCat') || {}).value || '';
                const res = await fetch(`/api/cbdb/assoc/types?q=${encodeURIComponent(q)}${cat ? '&category=' + encodeURIComponent(cat) : ''}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(x => ({
                    id: x.code, label: x.name_chn,
                    sub: `${x.category}${x.pair && x.pair !== x.code ? ' · 配对 ' + x.pair : ''}`
                }));
            },
            item => {
                window._cbdbAssocState.type = { code: item.id, name_chn: item.label };
                renderAssocChips();
                document.getElementById('cbdbAssocInput').value = '';
            });
        const catSel = document.getElementById('cbdbAssocCat');
        if (catSel) catSel.onchange = () => {
            const inp = document.getElementById('cbdbAssocInput');
            if (inp) inp.value = '';
        };
        loadCBDBDynasties();
        renderAssocChips();
    } else if (type === 'year') {
        area.innerHTML = `
            <div class="cbdb-adv-form">
                <div class="cbdb-adv-row"><label>年份</label><input type="number" id="cbdbYearInput" placeholder="公历年份（如 1086）" onkeydown="if(event.key==='Enter')searchCBDB()"></div>
                <div class="cbdb-adv-row"><label>朝代</label><select id="cbdbDynasty"><option value="">全部朝代</option></select></div>
                <div class="cbdb-adv-row"><label>入仕</label><input type="text" id="cbdbYearEntry" placeholder="可选：入仕方式（如 进士）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbYearEntryList"></div></div>
                <button class="btn-primary" style="width:100%;margin-top:2px" onclick="searchCBDB()">查询</button>
                <div class="cbdb-hint">检索该年份在世的人物（按生卒年/活跃期判定）</div>
            </div>`;
        loadCBDBDynasties();
        window._cbdbYearEntry = null;
        bindCBDBAutocomplete('cbdbYearEntry', 'cbdbYearEntryList',
            async q => {
                const res = await fetch(`/api/cbdb/entries/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(e => ({ id: e.code, label: e.name_chn, sub: e.name_eng }));
            },
            it => { window._cbdbYearEntry = it; document.getElementById('cbdbYearEntry').value = it.label; });
    } else if (type === 'pair') {
        // 两人关系（原生 Query Pair-wise Associations）：双向社会关系 + 直系亲属直查
        area.innerHTML = `
            <div class="cbdb-adv-form">
                <div class="cbdb-adv-row"><label>人物 A</label><input type="text" id="cbdbPairA" placeholder="输入姓名，下拉选择人物 A" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbPairAList"></div></div>
                <div class="cbdb-adv-row"><label>人物 B</label><input type="text" id="cbdbPairB" placeholder="输入姓名，下拉选择人物 B" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbPairBList"></div></div>
                <button class="btn-primary" style="width:100%;margin-top:4px" onclick="runPairQuery()">查询两人关系</button>
                <div class="cbdb-hint">两人之间的全部社会关系（双向）+ 直系亲属直查（附五服）</div>
            </div>`;
        window._cbdbPairState = { a: null, b: null };
        const pairFetcher = async q => {
            const res = await fetch(`/api/cbdb/search?name=${encodeURIComponent(q)}`);
            const data = await res.json();
            return (Array.isArray(data) ? data : []).map(p => ({
                id: p.id, label: p.name_chn || p.name,
                sub: [p.dynasty, (p.birthyear > 0 ? `${p.birthyear}—${p.deathyear || '?'}` : '')].filter(Boolean).join(' · ')
            }));
        };
        bindCBDBAutocomplete('cbdbPairA', 'cbdbPairAList', pairFetcher, item => {
            window._cbdbPairState.a = item;
            document.getElementById('cbdbPairA').value = item.label;
        });
        bindCBDBAutocomplete('cbdbPairB', 'cbdbPairBList', pairFetcher, item => {
            window._cbdbPairState.b = item;
            document.getElementById('cbdbPairB').value = item.label;
        });
    } else if (type === 'placeassoc') {
        // 地区关系（原生 Query Place Associations）：某地人物之间的社会关系
        area.innerHTML = `
            <div class="cbdb-adv-form">
                <div class="cbdb-adv-row"><label>地名</label><input type="text" id="cbdbPlaceAssocInput" placeholder="输入地名（如 洛陽、開封），下拉选择" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbPlaceAssocList"></div></div>
                <div class="cbdb-adv-row"><label>关系</label><input type="text" id="cbdbPlaceAssocType" placeholder="全部关系（可空，搜索并选择类型）" autocomplete="off">
                    <div class="cbdb-ac" id="cbdbPlaceAssocTypeList"></div></div>
                <div class="cbdb-adv-row"><label>年份</label><input type="number" id="cbdbPlaceAssocFrom" placeholder="自" style="width:48%"><span style="color:var(--text-muted)">至</span><input type="number" id="cbdbPlaceAssocTo" placeholder="至" style="width:48%"></div>
                <div class="cbdb-adv-row" style="flex-direction:row;align-items:center;gap:6px">
                    <input type="checkbox" id="cbdbPlaceAssocSame" style="width:auto">
                    <label for="cbdbPlaceAssocSame" style="flex:1">并入同坐标地址</label>
                </div>
                <div class="cbdb-adv-row" style="flex-direction:row;align-items:center;gap:6px">
                    <input type="checkbox" id="cbdbPlaceAssocBoth" style="width:auto">
                    <label for="cbdbPlaceAssocBoth" style="flex:1">仅双方均在该地区</label>
                </div>
                <button class="btn-primary" style="width:100%;margin-top:4px" onclick="runPlaceAssocQuery()">查询地区关系</button>
                <div class="cbdb-hint">该地区人物（籍贯/居址/任职地/索引地址）之间的社会关系</div>
            </div>`;
        window._cbdbPlaceAssocState = { place: null, type: null };
        bindCBDBAutocomplete('cbdbPlaceAssocInput', 'cbdbPlaceAssocList',
            async q => {
                const res = await fetch(`/api/cbdb/places/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(p => ({ id: p.addr_id, label: p.name_chn, sub: p.firstyear ? `${p.firstyear}—${p.lastyear || ''}` : (p.admin_type || '') }));
            },
            item => {
                window._cbdbPlaceAssocState.place = item;
                document.getElementById('cbdbPlaceAssocInput').value = item.label;
            });
        bindCBDBAutocomplete('cbdbPlaceAssocType', 'cbdbPlaceAssocTypeList',
            async q => {
                const res = await fetch(`/api/cbdb/assoc/types?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                return (Array.isArray(data) ? data : []).map(x => ({ id: x.code, label: x.name_chn, sub: x.category }));
            },
            item => {
                window._cbdbPlaceAssocState.type = { code: item.id, name_chn: item.label };
                document.getElementById('cbdbPlaceAssocType').value = item.label;
            });
    } else {
        // 竖排舒展表单：一行一个条件，原生查询维度全部铺开
        const cfg = CBDB_TYPE_CONFIG[type] || CBDB_TYPE_CONFIG.person;
        const enterGo = `onkeydown="if(event.key==='Enter')searchCBDB()"`;
        let rows = '';
        if (type === 'person') {
            rows = `
                <div class="cbdb-adv-row cbdb-adv-row-top"><label>姓名</label><textarea id="cbdbSearchInput" class="cbdb-textarea" rows="2" placeholder="${cfg.placeholder}"></textarea></div>
                <div class="cbdb-adv-row"><label>朝代</label><select id="cbdbDynasty"><option value="">全部朝代</option></select></div>
                <div class="cbdb-adv-row"><label>性别</label><select id="cbdbGender"><option value="">不限</option><option value="0">男</option><option value="1">女</option></select></div>
                <div class="cbdb-adv-row"><label>生年</label><input type="number" id="cbdbBirthFrom" placeholder="自" style="width:48%"><span style="color:var(--text-muted)">至</span><input type="number" id="cbdbBirthTo" placeholder="至" style="width:48%"></div>
                <div class="cbdb-adv-row"><label>卒年</label><input type="number" id="cbdbDeathFrom" placeholder="自" style="width:48%"><span style="color:var(--text-muted)">至</span><input type="number" id="cbdbDeathTo" placeholder="至" style="width:48%"></div>
                <div class="cbdb-adv-row"><label>指数年</label><input type="number" id="cbdbIndexFrom" placeholder="自" style="width:48%"><span style="color:var(--text-muted)">至</span><input type="number" id="cbdbIndexTo" placeholder="至" style="width:48%"></div>
                <div class="cbdb-adv-row"><label>籍贯</label><input type="text" id="cbdbPersonPlace" placeholder="输入地名，点击选择（可留空）" autocomplete="off" ${enterGo}>
                    <div class="cbdb-ac" id="cbdbPersonPlaceList"></div></div>
                <div class="cbdb-hint">检索框可纵向拉开：多行/顿号/逗号分隔 = 批量查人（或）。拼音：小写模糊（hao）；首字母大写按词首（Hao 命中 Zhang Hao 与 Hao Jing）；! 开头最左前缀（!Hao 仅 Hao Jing）</div>`;
        } else if (type === 'office') {
            rows = `
                <div class="cbdb-adv-row"><label>官名</label><input type="text" id="cbdbSearchInput" placeholder="${cfg.placeholder}" ${enterGo}></div>
                <div class="cbdb-adv-row"><label>门类</label><input type="text" id="cbdbOfficeCat" placeholder="如 統稱、機構（可空，简体自动转繁）" ${enterGo}></div>`;
        } else if (type === 'place') {
            const opts = CBDB_ADMIN_TYPES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
            rows = `
                <div class="cbdb-adv-row"><label>地名</label><input type="text" id="cbdbSearchInput" placeholder="${cfg.placeholder}" ${enterGo}></div>
                <div class="cbdb-adv-row"><label>层级</label><select id="cbdbAdminType">${opts}</select></div>
                <div class="cbdb-adv-row"><label>存续年</label><input type="number" id="cbdbPlaceFrom" placeholder="起始年"><span style="color:var(--text-muted)">—</span><input type="number" id="cbdbPlaceTo" placeholder="结束年"></div>`;
        } else {
            rows = `<div class="cbdb-adv-row"><label>${{entry:'入仕', status:'身份', text:'书名'}[type] || '检索'}</label><input type="text" id="cbdbSearchInput" placeholder="${cfg.placeholder}" ${enterGo}></div>`;
        }
        area.innerHTML = `<div class="cbdb-adv-form">${rows}
            <button class="btn-primary" style="width:100%;margin-top:2px" onclick="searchCBDB()">搜索</button></div>`;
        if (type === 'person') {
            loadCBDBDynasties();
            window._cbdbPersonState = window._cbdbPersonState || { place: null };
            bindCBDBAutocomplete('cbdbPersonPlace', 'cbdbPersonPlaceList',
                async q => {
                    const res = await fetch(`/api/cbdb/places/search?q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    return (Array.isArray(data) ? data : []).map(p => ({ id: p.addr_id, label: p.name_chn, sub: p.firstyear ? `${p.firstyear}—${p.lastyear || ''}` : (p.admin_type || '') }));
                },
                item => {
                    window._cbdbPersonState.place = item;
                    const inp = document.getElementById('cbdbPersonPlace');
                    if (inp) inp.value = item.label;
                });
        }
    }
}

// 简易自动补全：输入防抖 → 下拉列表 → 点击选中
function bindCBDBAutocomplete(inputId, listId, fetcher, onPick) {
    const input = document.getElementById(inputId);
    const box = document.getElementById(listId);
    if (!input || !box) return;
    let timer = null;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        const q = input.value.trim();
        if (!q) { box.innerHTML = ''; box.style.display = 'none'; return; }
        timer = setTimeout(async () => {
            try {
                const items = await fetcher(q);
                if (!items || !items.length) { box.innerHTML = ''; box.style.display = 'none'; return; }
                box.innerHTML = items.slice(0, 8).map((it, i) =>
                    `<div class="cbdb-ac-item" data-i="${i}">${escapeHtml(it.label)}${it.sub ? ` <span class="cbdb-ac-sub">${escapeHtml(it.sub)}</span>` : ''}</div>`
                ).join('');
                box.style.display = 'block';
                box.querySelectorAll('.cbdb-ac-item').forEach(el => {
                    el.onclick = () => { onPick(items[+el.dataset.i]); box.innerHTML = ''; box.style.display = 'none'; };
                });
            } catch (e) { box.style.display = 'none'; }
        }, 250);
    });
    document.addEventListener('click', e => {
        if (!box.contains(e.target) && e.target !== input) { box.style.display = 'none'; }
    });
}

function switchCBDBType(type) {
    window._cbdbType = type;
    window._cbdbAdvState = { place: null, entry: null };
    document.querySelectorAll('.cbdb-type-tab').forEach(b =>
        b.classList.toggle('active', b.dataset.type === type));
    renderCBDBSearchArea(type);
    const results = document.getElementById('cbdbResults');
    if (results) results.innerHTML = '';
    window._cbdbViewStack = [];
    window._cbdbListView = null;
    window._cbdbExport = null;
}

async function loadCBDBDynasties() {
    const sel = document.getElementById('cbdbDynasty');
    if (!sel || sel.dataset.loaded) return;
    try {
        const res = await fetch('/api/cbdb/dynasties');
        const data = await res.json();
        if (!Array.isArray(data)) return;
        sel.innerHTML = '<option value="">全部朝代</option>' +
            data.map(d => `<option value="${d.code}">${escapeHtml(d.name)}</option>`).join('');
        sel.dataset.loaded = '1';
    } catch (e) { /* 保留默认项即可 */ }
}

function renderCBDBBackBar(title) {
    if (!window._cbdbViewStack.length) return '';
    return `<div class="cbdb-back-bar">
        <button class="btn-secondary" onclick="cbdbGoBack()">← 返回</button>
        <span class="cbdb-view-title">${escapeHtml(title || '')}</span>
    </div>`;
}

// 导出工具条：结果数 + 范围/GeoJSON/CSV/群体按钮（人物列表附带三期范围传递 + 六期群体网络/人群属性入口）
function renderCBDBToolbar(count, persons) {
    const scopeBtns = (persons && persons.length)
        ? `<button class="btn-secondary cbdb-export-btn" onclick="cbdbSetScopeFromTable()" title="将勾选行（未勾选时为全部）设为查询范围，综合查询/年份检索自动取交集">🔎 设为查询范围</button>
           <button class="btn-secondary cbdb-export-btn" onclick="cbdbExportGeoJSON()" title="导出这些人物的地址坐标点（GeoJSON），可直接拖入 QGIS">🗺️ GeoJSON</button>
           <button class="btn-secondary cbdb-export-btn" onclick="cbdbShowOnMap()" title="把这些人物带坐标的地址直接标注到史料地图上联动查看，重复点击以新结果替换旧标注">🧭 在地图查看</button>
           <button class="btn-secondary cbdb-export-btn" onclick="cbdbGroupNetwork()" title="将勾选行（未勾选时为全部）作为群体，查看他们彼此之间的社会关系网络（原生社会关系网络窗体）">🕸️ 群体网络</button>
           <button class="btn-secondary cbdb-export-btn" onclick="cbdbGroupData()" title="将勾选行（未勾选时为全部）生成属性总表（原生按人群查询：入仕/官职/社会区分/著作/亲属/社会关系数）">📊 人群属性</button>` : '';
    const csvBtn = window._cbdbExport
        ? `<button class="btn-secondary cbdb-export-btn" onclick="exportCBDBCSV()">⬇ 导出 CSV</button>` : '';
    return `<div class="cbdb-toolbar">
        <span class="cbdb-result-meta" style="margin:0">共 ${count} 条</span>
        ${scopeBtns}${csvBtn}
    </div>`;
}

// ── 三期：人物表格统一渲染（勾选 + 范围 + 导出）────────────────
// opts: {backTitle, columns:[{label,render}], export:{filename,headers,rows}, extraMeta, extraHTML}
function cbdbRenderPersons(container, persons, opts = {}) {
    window._cbdbLastPersons = persons;
    if (opts.export) setCBDBExport(opts.export.filename, opts.export.headers, opts.export.rows);
    else window._cbdbExport = null;

    const cols = opts.columns || [];
    const thead = `<th class="cbdb-chk"><input type="checkbox" id="cbdbChkAll" title="全选"></th>` +
        cols.map(c => `<th>${c.label}</th>`).join('');
    const tbody = persons.map(p => `
        <tr data-pid="${p.id}">
            <td class="cbdb-chk" onclick="event.stopPropagation()"><input type="checkbox" class="cbdb-row-chk" data-pid="${p.id}"></td>
            ${cols.map(c => `<td>${c.render(p)}</td>`).join('')}
        </tr>`).join('');

    container.innerHTML = `
        ${opts.backTitle != null ? renderCBDBBackBar(opts.backTitle) : ''}
        ${renderCBDBToolbar(persons.length, persons)}
        ${opts.extraMeta || ''}
        <table class="cbdb-table">
            <thead><tr>${thead}</tr></thead>
            <tbody>${tbody}</tbody>
        </table>
        ${opts.extraHTML || ''}`;

    const chkAll = document.getElementById('cbdbChkAll');
    if (chkAll) chkAll.onchange = () => {
        document.querySelectorAll('.cbdb-row-chk').forEach(c => { c.checked = chkAll.checked; });
    };
    const rows = container.querySelectorAll('tbody tr');
    rows.forEach((tr, i) => {
        tr.onclick = () => { if (persons[i]) loadCBDBPersonDetail(persons[i].id); };
    });
}

// ── 三期：跨查询人物列表传递 ─────────────────────────────
function cbdbSetScopeFromTable() {
    const persons = window._cbdbLastPersons || [];
    const checked = [...document.querySelectorAll('.cbdb-row-chk:checked')].map(c => +c.dataset.pid);
    const ids = checked.length ? checked : persons.map(p => p.id);
    if (!ids.length) { showToast('当前列表没有人物', 'warning'); return; }
    window._cbdbScope = { ids, label: (checked.length ? '勾选' : '全部') + ' ' + ids.length + ' 人' };
    renderScopeBar();
    showToast(`查询范围已设：${ids.length} 人，综合查询/年份检索将自动取交集`, 'success', 4000);
}

function cbdbClearScope() {
    window._cbdbScope = null;
    renderScopeBar();
}

function renderScopeBar() {
    const results = document.getElementById('cbdbResults');
    if (!results) return;
    let bar = document.getElementById('cbdbScopeBar');
    if (!window._cbdbScope) { if (bar) bar.remove(); return; }
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'cbdbScopeBar';
        results.parentNode.insertBefore(bar, results);
    }
    bar.className = 'cbdb-scope-bar';
    bar.innerHTML = `<span class="cbdb-scope-label">🔎 查询范围 <b>${window._cbdbScope.ids.length}</b> 人（${escapeHtml(window._cbdbScope.label)}）</span>
        <span class="cbdb-scope-hint">已自动应用于 综合查询 / 年份检索</span>
        <button class="btn-secondary cbdb-scope-clear" onclick="cbdbClearScope()">✕ 清除</button>`;
}

// ── 六期：群体网络 / 人群属性（任意人物列表 → 原生 Query Social Networks / Look Up Group）──
function cbdbCollectCheckedIds() {
    const persons = window._cbdbLastPersons || [];
    const checked = [...document.querySelectorAll('.cbdb-row-chk:checked')].map(c => +c.dataset.pid);
    return { ids: checked.length ? checked : persons.map(p => p.id), checked: !!checked.length };
}

async function cbdbGroupNetwork() {
    const { ids, checked } = cbdbCollectCheckedIds();
    if (!ids.length) { showToast('当前列表没有人物', 'warning'); return; }
    window._cbdbGroupNet = { ids, label: (checked ? '勾选' : '全部') + ' ' + ids.length + ' 人' };
    _cbdbNetState.includeKin = false;
    _cbdbNetState.dy = '';
    showCBDBNetworkView();
    await loadCBDBGroupNetwork();
}

async function loadCBDBGroupNetwork() {
    const panel = document.getElementById('cbdbNetwork');
    const g = window._cbdbGroupNet;
    if (!panel || !g) return;
    panel.innerHTML = '<div class="loading" style="margin:30px auto;display:block"></div>';
    try {
        const res = await fetch('/api/cbdb/network/group', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ids: g.ids.slice(0, 500),
                include_kin: !!_cbdbNetState.includeKin,
                up: 2, down: 2, col: 1, mar: 1,
                dy: _cbdbNetState.dy || undefined
            })
        });
        const data = await res.json();
        if (data.error) { panel.innerHTML = `<p style="color:var(--danger);padding:20px">${escapeHtml(data.error)}</p>`; return; }
        renderNetworkPanel(panel, data, 0, g);
    } catch (e) {
        panel.innerHTML = `<p style="color:var(--danger);padding:20px">网络加载失败：${escapeHtml(e.message)}</p>`;
    }
}

async function cbdbGroupData() {
    const { ids, checked } = cbdbCollectCheckedIds();
    if (!ids.length) { showToast('当前列表没有人物', 'warning'); return; }
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading"></div> 正在生成属性总表...';
    window._cbdbExport = null;
    try {
        const res = await fetch('/api/cbdb/group/data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids.slice(0, 500) })
        });
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger)">${escapeHtml(data.error)}</p>`; return; }
        const rows = data.rows || [];
        if (!rows.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">没有可用数据</p>'; return; }
        const cols = [
            ['姓名', r => `<span class="cbdb-name" onclick="loadCBDBPersonDetail(${r.id});event.stopPropagation()">${escapeHtml(r.name_chn)}</span>`],
            ['朝代', r => escapeHtml(r.dynasty)],
            ['生卒', r => (r.birthyear > 0 || r.deathyear > 0) ? `${r.birthyear > 0 ? r.birthyear : '?'}—${r.deathyear > 0 ? r.deathyear : '?'}` : '—'],
            ['索引年', r => r.index_year || '—'],
            ['性别', r => r.female ? '女' : '男'],
            ['籍贯', r => escapeHtml(r.native_place) || '—'],
            ['入仕', r => escapeHtml(r.entry) || '—'],
            ['官职', r => escapeHtml(r.offices) || '—'],
            ['社会区分', r => escapeHtml(r.statuses) || '—'],
            ['著作', r => r.texts_count || '—'],
            ['亲属', r => r.kin_count || '—'],
            ['社会关系', r => r.assoc_count || '—']
        ];
        setCBDBExport(`cbdb_人群属性_${rows.length}人.csv`,
            ['姓名', '朝代', '生年', '卒年', '索引年', '性别', '籍贯', '入仕', '官职', '社会区分', '著作数', '亲属数', '社会关系数', '人物ID'],
            rows.map(r => [r.name_chn, r.dynasty, r.birthyear || '', r.deathyear || '', r.index_year || '',
                r.female ? '女' : '男', r.native_place, r.entry, r.offices, r.statuses,
                r.texts_count, r.kin_count, r.assoc_count, r.id]));
        resultsDiv.innerHTML = `
            <div class="cbdb-toolbar">
                <span class="cbdb-result-meta" style="margin:0">共 ${rows.length} 人${checked ? '（勾选行）' : ''}</span>
                <button class="btn-secondary cbdb-export-btn" onclick="exportCBDBCSV()">⬇ 导出 CSV</button>
            </div>
            <div class="cbdb-hint" style="margin:4px 0">按人群查询（原生 Look Up Data on a Group of People）：任意人物列表一键转属性总表</div>
            <table class="cbdb-table"><thead><tr>${cols.map(c => `<th>${c[0]}</th>`).join('')}</tr></thead>
            <tbody>${rows.map(r => `<tr>${cols.map(c => `<td>${c[1](r)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
        resultsDiv.scrollTop = 0;
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger)">生成失败：${escapeHtml(e.message)}</p>`;
    }
}

// ── 三期：GeoJSON 导出（QGIS 直读）────────────────────────
// 十期R4：导出跟随当前地址来源（生活地址/任职地/全部），文件名标注来源
async function cbdbExportGeoJSON() {
    const persons = window._cbdbLastPersons || [];
    if (!persons.length) { showToast('当前列表没有人物', 'warning'); return; }
    const src = window._cbdbMapAddrSource || 'bio';
    const srcLabel = { bio: '生活地址', posted: '任职地', all: '生活+任职' }[src] || '生活地址';
    showToast('正在生成 GeoJSON…', 'info', 1500);
    try {
        const res = await fetch('/api/cbdb/persons/geojson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: persons.map(p => p.id), addr_source: src })
        });
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        const n = (data.features || []).length;
        if (!n) { showToast('这些人物在该来源下没有带坐标的地址记录', 'warning', 3500); return; }
        const blob = new Blob([JSON.stringify(data)], { type: 'application/geo+json;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `cbdb_${srcLabel}_${new Date().toISOString().slice(0, 10)}.geojson`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        showToast(`GeoJSON 已导出：${n} 个${srcLabel}点，可直接拖入 QGIS`, 'success', 4000);
    } catch (e) { showToast('导出失败：' + e.message, 'error'); }
}

// 地图联动：把当前人物列表的地址坐标直接标注到史料地图（复用 persons/geojson，不入文件）
// 地图聚点筛选：'all' | 'jiguan' | 'zuji' | 'juzhi' | 'zang'
window._cbdbMapAddrFilter = window._cbdbMapAddrFilter || 'all';
// 十期：地址来源 'bio' 生活地址 | 'posted' 任职地 | 'all' 两者合并（群体模式）
window._cbdbMapAddrSource = window._cbdbMapAddrSource || 'bio';
const CBDB_MAP_SOURCES = [
    { key: 'bio', label: '生活地址' },
    { key: 'posted', label: '任职地' },
    { key: 'all', label: '生活+任职' },
];
const CBDB_MAP_FILTERS = [
    { key: 'all',   label: '全部',   types: [] },
    { key: 'jiguan', label: '籍贯',  types: [1] },
    { key: 'zuji',  label: '祖籍',   types: [5] },
    { key: 'juzhi', label: '居址',   types: [6, 7] },
    { key: 'zang',  label: '葬·卒地', types: [9, 10] },
];

async function cbdbShowOnMap() {
    const persons = window._cbdbLastPersons || [];
    if (!persons.length) { showToast('当前列表没有人物', 'warning'); return; }
    window._cbdbMapLastIds = persons.map(p => p.id);
    window._cbdbMapLastTitle = persons.length + ' 人';
    // 朝代图层联动（任务3）：列表平均指数年/生年 + 众数朝代名作为图层上下文
    let sum = 0, n = 0;
    const nameCount = {};
    persons.forEach(p => {
        const y = p.index_year || (p.birthyear > 0 ? p.birthyear : 0);
        if (y > 0) { sum += y; n++; }
        const dn = p.dynasty || '';
        if (dn) nameCount[dn] = (nameCount[dn] || 0) + 1;
    });
    const topName = Object.keys(nameCount).sort((a, b) => nameCount[b] - nameCount[a])[0] || null;
    // 众数朝代占多数时名称优先（混合群体平均年可能落入无人属于的朝代），否则按年份优先、名称兜底
    const majority = topName ? nameCount[topName] > persons.length / 2 : false;
    window._cbdbMapCtx = { year: n ? Math.round(sum / n) : 0, dynastyName: topName, preferName: majority };
    if (persons.length === 1) {
        // 单人 → 人生轨迹模式（生活地址+任职地+年份交叠官职）
        await cbdbPlotTrajectory();
        return;
    }
    await cbdbPlotGroupOnMap();
}

// ── 十期：人生轨迹（单人物）────────────────────────────
// 地址类型 → 类别（颜色/标签）。任职地 addr_type_code=100 为posted模式专用。
const CBDB_TRAJ_CATS = [
    { key: 'birth',  label: '出生地', color: '#2e7d4f', codes: [8] },
    { key: 'jiguan', label: '籍贯',   color: '#3a6ea5', codes: [1, 14] },
    { key: 'death',  label: '死所',   color: '#1a1a1a', codes: [10] },
    { key: 'burial', label: '葬地',   color: '#7d5a3c', codes: [9] },
    { key: 'posted', label: '任职地', color: '#b03a2e', codes: [100] },
    { key: 'reside', label: '居住',   color: '#c9962e', codes: [2, 3, 6, 7, 15, 16, 17, 18, 19] },
    { key: 'travel', label: '游历',   color: '#8a8a8a', codes: [12, 11, 21] },
];
function cbdbTrajCat(code) {
    return CBDB_TRAJ_CATS.find(c => c.codes.includes(code)) ||
        { key: 'other', label: '其他', color: '#999', codes: [] };
}
// 聚合节点的代表类别：按叙事意义取最高优先级（任职>出生>死所>葬地>籍贯>居住>游历）。
// 黄州聚簇里有"前住地+团练副使"，应显示任职朱砂红而不是居住金
function cbdbTrajTopCat(items) {
    const order = ['posted', 'birth', 'death', 'burial', 'jiguan', 'reside', 'travel'];
    const keys = new Set(items.map(p => cbdbTrajCat(p.addr_type_code).key));
    for (const k of order) {
        if (keys.has(k)) return CBDB_TRAJ_CATS.find(c => c.key === k);
    }
    return cbdbTrajCat(items[0] && items[0].addr_type_code);
}

async function cbdbPlotTrajectory() {
    const ids = window._cbdbMapLastIds || [];
    if (ids.length !== 1) return;
    showToast('正在生成人生轨迹…（生活地址 + 任职履历）', 'info', 2000);
    try {
        const res = await fetch('/api/cbdb/persons/geojson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids, addr_source: 'all', with_offices: true })
        });
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        const feats = data.features || [];
        const meta = data.meta || {};
        if (!feats.length) {
            const noCoord = (meta.addr_total || 0) + (meta.posting_total || 0);
            showToast(noCoord
                ? `此人有 ${noCoord} 条地址/任职记录，但均无坐标无法定位（古今地名未考定）`
                : '此人没有地址与任职记录', 'warning', 6000);
            return;
        }
        const person = feats.find(f => f.properties.name)?.properties || {};
        const pname = person.name || ('人物 ' + ids[0]);

        switchTab('map');
        const mctx = window._cbdbMapCtx;
        if (mctx) autoSwitchDynastyByYear(mctx.year || 0, mctx.dynastyName, mctx.preferName);
        setTimeout(() => {
            try {
                initMap();
                if (!chgisMap) { showToast('地图初始化失败', 'error'); return; }
                if (window.cbdbPersonLayer) { chgisMap.removeLayer(window.cbdbPersonLayer); window.cbdbPersonLayer = null; }
                if (window.cbdbPersonClearCtl) { chgisMap.removeControl(window.cbdbPersonClearCtl); window.cbdbPersonClearCtl = null; }
                if (window._cbdbTrajFitAllCtl) { chgisMap.removeControl(window._cbdbTrajFitAllCtl); window._cbdbTrajFitAllCtl = null; }

                // 按坐标聚合（同地多记录合一），保留类型/年份/官职
                const groups = new Map();
                feats.forEach(f => {
                    const p = f.properties;
                    const x = f.geometry.coordinates[0], y = f.geometry.coordinates[1];
                    const k = x.toFixed(3) + ',' + y.toFixed(3);
                    if (!groups.has(k)) groups.set(k, { x, y, items: [] });
                    groups.get(k).items.push(p);
                });
                const gs = [...groups.values()];

                // 轨迹序列：有年份的非游历节点按最早年份排序（同坐标取一次）；其余组渲染为小点
                const seq = [];
                const minors = [];
                gs.forEach(g => {
                    const timed = g.items.filter(p =>
                        (p.firstyear || p.lastyear) &&
                        (cbdbTrajCat(p.addr_type_code).key !== 'travel'));
                    if (timed.length) {
                        const y0 = Math.min(...timed.map(p => p.firstyear || p.lastyear));
                        seq.push({ g, y0, items: g.items });
                    } else {
                        minors.push({ g, items: g.items });
                    }
                });
                seq.sort((a, b) => a.y0 - b.y0);

                const markers = [];
                const linePts = [];
                const addNode = (s, minor, idx) => {
                    const cat = cbdbTrajTopCat(s.items);
                    const isStart = s.items.some(p => p.addr_type_code === 8);
                    const isEnd = s.items.some(p => p.addr_type_code === 10);
                    const ll = [s.g.y, s.g.x];
                    const icon = L.divIcon({
                        className: 'cbdb-traj-wrap',
                        html: `<div class="cbdb-traj-node${isStart ? ' start' : ''}${isEnd ? ' end' : ''}${minor ? ' minor' : ''}${!minor && idx % 2 ? ' alt' : ''}" style="--c:${cat.color}">
                            <div class="cbdb-traj-dot"></div>
                            ${minor ? '' : `<div class="cbdb-traj-yr">${s.y0 < 0 ? '?' : s.y0}</div>`}
                            ${isStart ? '<div class="cbdb-traj-tag">始</div>' : ''}
                            ${isEnd ? '<div class="cbdb-traj-tag">终</div>' : ''}
                        </div>`,
                        iconSize: [14, 14], iconAnchor: [7, 7]
                    });
                    const mk = L.marker(ll, { icon, zIndexOffset: minor ? 0 : 500 })
                        .bindPopup(cbdbTrajPopup(pname, person, s.items), { maxWidth: 320, minWidth: 220 });
                    markers.push(mk);
                    return mk;
                };
                seq.forEach((s, i) => {
                    addNode(s, false, i);
                    linePts.push([s.g.y, s.g.x]);
                });
                minors.forEach(m => addNode(m, true, 0));

                // 年份标签：zoom<5 隐藏（留始终点），奇偶节点交替上下防重叠
                // R5：屏幕空间碰撞检测——标签矩形相交则隐藏（放大后自动释放），根治开封密集区互相压盖
                const syncYrVis = () => {
                    const z = chgisMap.getZoom();
                    const show = z >= 5;
                    const placed = [];
                    window.cbdbPersonLayer?.eachLayer(l => {
                        const el = l.getElement?.();
                        if (!el || !el.classList.contains('cbdb-traj-wrap')) return;
                        el.classList.toggle('show-yr', show);
                        const yr = el.querySelector('.cbdb-traj-yr');
                        if (!yr) return;
                        if (!show) { yr.style.visibility = ''; return; }
                        const pt = chgisMap.latLngToLayerPoint(l.getLatLng());
                        const below = !!el.querySelector('.cbdb-traj-node.alt');
                        const cx = pt.x, cy = below ? pt.y + 21 : pt.y - 17;
                        const rect = { x: cx - 18, y: cy - 7, w: 36, h: 14 };
                        const hit = placed.some(r => rect.x < r.x + r.w && rect.x + rect.w > r.x && rect.y < r.y + r.h && rect.y + rect.h > r.y);
                        yr.style.visibility = hit ? 'hidden' : 'visible';
                        if (!hit) placed.push(rect);
                    });
                };
                chgisMap.off('zoomend', window._cbdbTrajZoomH);
                window._cbdbTrajZoomH = syncYrVis;
                chgisMap.on('zoomend', syncYrVis);

                // 轨迹线 + 方向小箭头（段中点，按线段方位旋转）
                const layers = [...markers];
                if (linePts.length >= 2) {
                    const line = L.polyline(linePts, {
                        color: '#c9962e', weight: 2.5, opacity: 0.8, dashArray: '7 5'
                    });
                    layers.push(line);
                    for (let i = 0; i < linePts.length - 1; i++) {
                        const a = chgisMap.latLngToLayerPoint(linePts[i]);
                        const b = chgisMap.latLngToLayerPoint(linePts[i + 1]);
                        const mid = chgisMap.layerPointToLatLng(a.add(b).divideBy(2));
                        const deg = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
                        layers.push(L.marker(mid, {
                            icon: L.divIcon({
                                className: 'cbdb-traj-arrow',
                                html: `<div style="transform:rotate(${deg}deg);color:#c9962e">▶</div>`,
                                iconSize: [12, 12], iconAnchor: [6, 6]
                            }), interactive: false, keyboard: false
                        }));
                    }
                }
                window.cbdbPersonLayer = L.layerGroup(layers).addTo(chgisMap);
                cbdbAddTrajLegend(pname, seq, minors, feats.length, meta);

                // R5：初始视野聚焦主要活动区（地理中位数 70% 密集区），离群节点（如海南）给"全览"按钮
                // 注：始终点不强制入视野—— Anchor 会把 bbox 拉回全国尺度，密集区可读性优先；"全览"兜底看全部
                // 距离归一化：经度差乘 cos(中位纬度)，否则高纬地区经向距离被高估、离群判定失真
                // 聚焦门槛 ≥8 个节点：普通人只有 3-6 个地址时"聚焦"无意义，还会误出"全览 1 处远方节点"
                chgisMap.invalidateSize();
                const allBounds = L.featureGroup(markers).getBounds();
                const allPts = gs.map(g => [g.y, g.x]);
                let initBounds = allBounds, initPad = 0.18, focusNote = '';
                let focusApplied = false;
                if (allPts.length >= 8) {
                    const lats = allPts.map(p => p[0]).sort((a, b) => a - b);
                    const lngs = allPts.map(p => p[1]).sort((a, b) => a - b);
                    const med = [lats[Math.floor(lats.length / 2)], lngs[Math.floor(lngs.length / 2)]];
                    const kx = Math.cos(med[0] * Math.PI / 180);
                    const d2 = p => (p[0] - med[0]) ** 2 + ((p[1] - med[1]) * kx) ** 2;
                    const near = [...allPts].sort((a, b) => d2(a) - d2(b));
                    const nFocus = Math.max(2, Math.ceil(allPts.length * 0.7));
                    const focusPts = near.slice(0, nFocus);
                    const fB = L.latLngBounds(focusPts);
                    const area = b => Math.max((b.getNorth() - b.getSouth()) * (b.getEast() - b.getWest()), 1e-9);
                    const nOut = allPts.length - nFocus;
                    if (nOut > 0 && area(fB) < area(allBounds) * 0.65) {
                        initBounds = fB; initPad = 0.25; focusApplied = true;
                        focusNote = `，已聚焦主要活动区（右上"全览"看全部 ${allPts.length} 节点）`;
                        const fctl = L.control({ position: 'topright' });
                        fctl.onAdd = () => {
                            const div = L.DomUtil.create('div', 'cbdb-traj-fitall');
                            div.textContent = `⤢ 全览 ${nOut} 处远方节点`;
                            L.DomEvent.disableClickPropagation(div);
                            div.onclick = () => chgisMap.flyToBounds(allBounds.pad(0.15), { maxZoom: 7 });
                            return div;
                        };
                        window._cbdbTrajFitAllCtl = fctl;
                        fctl.addTo(chgisMap);
                    }
                }
                if (!focusApplied && window._cbdbTrajFitAllCtl) { chgisMap.removeControl(window._cbdbTrajFitAllCtl); window._cbdbTrajFitAllCtl = null; }
                chgisMap.fitBounds(initBounds.pad(initPad), { maxZoom: 7 });
                // 分级文案：数据不足时诚实说明，不用"轨迹"误导
                const nMinor = minors.length;
                if (seq.length >= 2) {
                    showToast(`${pname} 人生轨迹：${seq.length} 个节点（按时间先后连线，点击节点看详情）${focusNote}`, 'success', 5000);
                } else if (seq.length === 1) {
                    showToast(`${pname}：仅 1 处带年份记录（${feats.length - nMinor > 1 ? '另有 ' + (feats.length - nMinor - 1) + ' 处' : ''}无法连成轨迹）——点击节点看详情`, 'warning', 6000);
                } else {
                    showToast(`${pname}：${nMinor} 处可定位记录均无年份，先后无法确定（小点）——点击看详情`, 'warning', 6000);
                }
            } catch (e) { console.error('轨迹渲染失败:', e); showToast('轨迹渲染失败: ' + e.message, 'error', 6000); }
        }, 300);
    } catch (e) { console.error('轨迹加载失败:', e); showToast('加载失败: ' + e.message, 'error', 6000); }
}

// 轨迹节点弹窗：聚合同地记录，显示类型/年份/此时官职/当时年龄
function cbdbTrajPopup(pname, person, items) {
    const place = items[0].place || '未知地点';
    const birth = person.birth || 0;
    const rows = items.map(p => {
        const cat = cbdbTrajCat(p.addr_type_code);
        let age = '';
        if (birth > 0 && p.firstyear > 0) age = `（${p.firstyear - birth} 岁）`;
        const yrs = (p.firstyear || p.lastyear)
            ? `${p.firstyear || '?'}–${p.lastyear || '?'}${age}` : '年份不详';
        let officeLine = '';
        if (p.source === 'posted' && p.office) {
            officeLine = `<div class="cbdb-map-popup-office">官职：${escapeHtml(p.office)}</div>`;
        } else if (p.offices && p.offices.length) {
            const same = p.offices.filter(o => o.place === p.place);
            const list = (same.length ? same : p.offices).slice(0, 3);
            officeLine = list.map(o =>
                `<div class="cbdb-map-popup-office">此时官职：${escapeHtml(o.office)} <span class="cbdb-map-popup-office-yr">${o.firstyear || '?'}-${o.lastyear || '?'}</span></div>`
            ).join('');
        }
        return `<div class="cbdb-traj-popup-row">
            <span class="cbdb-traj-popup-type" style="background:${cat.color}">${cat.label}</span>
            <span class="cbdb-traj-popup-yrs">${yrs}</span>
            ${officeLine}
        </div>`;
    }).join('');
    const life = (person.birth || person.death) ? `${person.birth || '?'}–${person.death || '?'}` : '生卒不详';
    return `<div class="cbdb-map-popup">
        <div class="cbdb-map-popup-name">${escapeHtml(pname)}</div>
        <div class="cbdb-map-popup-line">${escapeHtml(person.dynasty || '')} · ${life} · ${escapeHtml(place)}</div>
        <div class="cbdb-traj-popup-rows">${rows}</div>
        <a class="cbdb-map-popup-link" onclick="switchTab('cbdb'); loadCBDBPersonDetail(${parseInt(items[0].person_id) || 0})">在 CBDB 中查看 →</a>
    </div>`;
}

// 轨迹图例（左下）：只列实际出现的类别 + 数据覆盖边界说明
function cbdbAddTrajLegend(pname, seq, minors, nRec, meta) {
    const ctl = L.control({ position: 'bottomleft' });
    ctl.onAdd = () => {
        const div = L.DomUtil.create('div', 'cbdb-map-trajlegend');
        // 实际出现的类别（保持 CBDB_TRAJ_CATS 顺序）
        const present = new Set();
        seq.concat(minors).forEach(s => s.items.forEach(p =>
            present.add(cbdbTrajCat(p.addr_type_code).key)));
        const items = CBDB_TRAJ_CATS.filter(c => present.has(c.key)).map(c =>
            `<div class="cbdb-map-trajlegend-item"><span class="cbdb-traj-dot-sm" style="background:${c.color}"></span>${c.label}</div>`
        ).join('');
        const minorItem = minors.length
            ? `<div class="cbdb-map-trajlegend-item"><span class="cbdb-traj-dot-sm" style="background:#777;width:6px;height:6px"></span>无年份</div>` : '';
        // 数据覆盖：无坐标未显示的记录数（诚实呈现边界）
        const nocoord = (meta.addr_nocoord || 0) + (meta.posting_nocoord || 0);
        const lines = [];
        if (seq.length) lines.push(`${seq.length} 节点`);
        if (minors.length) lines.push(`${minors.length} 小点`);
        lines.push(`${nRec} 条有坐标`);
        if (nocoord) lines.push(`${nocoord} 条无坐标未显示`);
        div.innerHTML = `<div class="cbdb-map-trajlegend-title">${escapeHtml(pname)} · 人生轨迹</div>
            ${items}${minorItem}
            <div class="cbdb-map-trajlegend-info">${lines.join(' · ')}</div>
            <div class="cbdb-map-trajlegend-clear">✕ 清除标注</div>`;
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        div.querySelector('.cbdb-map-trajlegend-clear').onclick = () => {
            if (window.cbdbPersonLayer) { chgisMap.removeLayer(window.cbdbPersonLayer); window.cbdbPersonLayer = null; }
            if (window.cbdbPersonClearCtl) { chgisMap.removeControl(window.cbdbPersonClearCtl); window.cbdbPersonClearCtl = null; }
        };
        return div;
    };
    window.cbdbPersonClearCtl = ctl.addTo(chgisMap);
}

// 群体上地图主流程：取地址 → 按坐标聚合 → 智能渲染（少散珠/多聚簇）
async function cbdbPlotGroupOnMap() {
    const ids = window._cbdbMapLastIds || [];
    if (!ids.length) return;
    const fdef = CBDB_MAP_FILTERS.find(f => f.key === (window._cbdbMapAddrFilter || 'all')) || CBDB_MAP_FILTERS[0];
    const src = window._cbdbMapAddrSource || 'bio';
    // with_offices 只对散点级小群体开启：散点弹窗才显示"此时官职"，
    // 大群体走聚簇（弹窗是名单），全量任职匹配是浪费（2000 人×任职记录千万级循环）
    const wo = src === 'bio' && ids.length <= 50;
    showToast('正在获取地址坐标…', 'info', 1500);
    try {
        const res = await fetch('/api/cbdb/persons/geojson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids, addr_types: fdef.types, addr_source: src, with_offices: wo })
        });
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        const feats = data.features || [];
        if (!feats.length) { showToast('这些人物在该筛选下没有带坐标的地址记录', 'warning', 3500); return; }
        switchTab('map');
        const mctx = window._cbdbMapCtx;
        if (mctx) autoSwitchDynastyByYear(mctx.year || 0, mctx.dynastyName, mctx.preferName);
        setTimeout(() => {
            try {
                initMap();
                if (!chgisMap) { showToast('地图初始化失败', 'error'); return; }
                if (window.cbdbPersonLayer) { chgisMap.removeLayer(window.cbdbPersonLayer); window.cbdbPersonLayer = null; }
                if (window.cbdbPersonClearCtl) { chgisMap.removeControl(window.cbdbPersonClearCtl); window.cbdbPersonClearCtl = null; }
                if (window._cbdbTrajFitAllCtl) { chgisMap.removeControl(window._cbdbTrajFitAllCtl); window._cbdbTrajFitAllCtl = null; }
                window._cbdbMapGroupCache = {};  // 每次重绘清空，防旧弹窗串号

                // 按坐标（0.001°≈111m）聚合
                const groups = new Map();
                feats.forEach(f => {
                    const x = f.geometry.coordinates[0], y = f.geometry.coordinates[1];
                    const k = x.toFixed(3) + ',' + y.toFixed(3);
                    if (!groups.has(k)) groups.set(k, { x, y, items: [] });
                    groups.get(k).items.push(f.properties);
                });
                const gs = [...groups.values()];
                const markers = [];
                if (gs.length <= 40) {
                    // 少量散点：逐条金珠
                    const orbIcon = L.divIcon({
                        className: 'cbdb-orb-marker',
                        html: '<div class="cbdb-orb"></div>',
                        iconSize: [18, 18], iconAnchor: [9, 9], popupAnchor: [0, -11]
                    });
                    gs.forEach(g => g.items.forEach(p => markers.push(
                        L.marker([g.y, g.x], { icon: orbIcon }).bindPopup(cbdbMapPersonPopup(p), { maxWidth: 260, minWidth: 180 })
                    )));
                } else {
                    // 大规模：聚簇圆盘，直径随人数开方增长
                    gs.forEach((g, gi) => {
                        const n = g.items.length;
                        const d = Math.round(26 + Math.min(30, Math.sqrt(n) * 4));
                        const icon = L.divIcon({
                            className: 'cbdb-orb-marker',
                            html: `<div class="cbdb-cluster" style="width:${d}px;height:${d}px;font-size:${n >= 100 ? 13 : (n >= 10 ? 12 : 11)}px">${n}</div>`,
                            iconSize: [d, d], iconAnchor: [d / 2, d / 2], popupAnchor: [0, -d / 2]
                        });
                        const place = g.items[0].place || '未知地点';
                        const key = 'g' + gi + '_' + n;
                        window._cbdbMapGroupCache[key] = g.items.map(p => p.person_id);
                        markers.push(L.marker([g.y, g.x], { icon }).bindPopup(cbdbMapGroupPopup(place, g.items, key), { maxWidth: 300, minWidth: 220 }));
                    });
                }
                window.cbdbPersonLayer = L.layerGroup(markers).addTo(chgisMap);
                cbdbAddGroupControl(feats.length, gs.length);
                chgisMap.fitBounds(L.featureGroup(markers).getBounds().pad(0.15), { maxZoom: 10 });
                showToast(gs.length <= 40
                    ? `已标注 ${feats.length} 个地址点，点击珠子看详情`
                    : `已聚合 ${gs.length} 个地点（${feats.length} 条地址记录），点圆盘看名单`, 'success', 4000);
            } catch (e) { showToast('地图标注失败: ' + e.message, 'error'); }
        }, 300);
    } catch (e) { showToast('加载失败: ' + e.message, 'error'); }
}

// 单条地址弹窗（散点模式，属性来自 persons_geojson）
// 十期增强：offices 字段（年份交叠匹配的任职记录）+ posted 模式的 office 字段
function cbdbMapPersonPopup(p) {
    const life = (p.birth || p.death) ? `${p.birth || '?'}–${p.death || '?'}` : '生卒不详';
    const yrs = (p.firstyear || p.lastyear) ? `<div class="cbdb-map-popup-line">地址年份：${p.firstyear || '?'}–${p.lastyear || '?'}</div>` : '';
    let officeHtml = '';
    if (p.source === 'posted' && p.office) {
        officeHtml = `<div class="cbdb-map-popup-office">官职：${escapeHtml(p.office)}</div>`;
    } else if (p.offices && p.offices.length) {
        const same = p.offices.filter(o => o.place === p.place);
        const list = (same.length ? same : p.offices).slice(0, 2);
        officeHtml = list.map(o =>
            `<div class="cbdb-map-popup-office">此时官职：${escapeHtml(o.office)} <span class="cbdb-map-popup-office-yr">${o.firstyear || '?'}-${o.lastyear || '?'}</span></div>`
        ).join('');
    }
    const srcBadge = p.source === 'posted' ? '<span class="cbdb-map-popup-badge">任职地</span>' : '';
    return `<div class="cbdb-map-popup">
        <div class="cbdb-map-popup-name">${escapeHtml(p.name)}${srcBadge}</div>
        <div class="cbdb-map-popup-line">${escapeHtml(p.dynasty)} · ${life}</div>
        <div class="cbdb-map-popup-line">${escapeHtml(p.addr_type)}：${escapeHtml(p.place)}</div>
        ${yrs}
        ${officeHtml}
        <a class="cbdb-map-popup-link" onclick="switchTab('cbdb'); loadCBDBPersonDetail(${parseInt(p.person_id) || 0})">在 CBDB 中查看 →</a>
    </div>`;
}

// 聚簇弹窗：地名 + 名单（可点）+ 回灌 CBDB 列表
function cbdbMapGroupPopup(place, items, cacheKey) {
    const shown = items.slice(0, 40);
    const more = items.length - shown.length;
    const list = shown.map(p =>
        `<a class="cbdb-map-popup-person" onclick="switchTab('cbdb'); loadCBDBPersonDetail(${parseInt(p.person_id) || 0})">${escapeHtml(p.name)}<span>${escapeHtml(p.dynasty)} · ${escapeHtml(p.addr_type)}</span></a>`
    ).join('');
    return `<div class="cbdb-map-popup">
        <div class="cbdb-map-popup-name">${escapeHtml(place)}</div>
        <div class="cbdb-map-popup-line">共 ${items.length} 条人物地址记录</div>
        <div class="cbdb-map-popup-list">${list}${more > 0 ? `<div class="cbdb-map-popup-line">……另有 ${more} 条</div>` : ''}</div>
        <a class="cbdb-map-popup-link" onclick="cbdbMapGroupToList('${cacheKey}')">把这 ${items.length} 人载入 CBDB 列表 →</a>
    </div>`;
}

// 聚点 → CBDB 统一列表（闭环）
async function cbdbMapGroupToList(cacheKey) {
    const ids = (window._cbdbMapGroupCache || {})[cacheKey] || [];
    if (!ids.length) { showToast('名单缓存已失效，请重新标注', 'warning'); return; }
    switchTab('cbdb');
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading"></div> 查询中...';
    try {
        const res = await fetch('/api/cbdb/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filters: {}, person_ids: ids.slice(0, 5000) })
        });
        const data = await res.json();
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配人物</p>'; return; }
        cbdbRenderPersons(resultsDiv, data, {
            backTitle: '地图聚点（' + ids.length + ' 人）',
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '-' + p.deathyear : '?' },
                { label: '籍贯', render: p => escapeHtml(p.native_place) || '?' },
                { label: '指数年', render: p => p.index_year || '?' },
                { label: '性别', render: p => p.female ? '女' : '男' }
            ],
            export: { filename: `cbdb_地图聚点_${ids.length}人.csv`,
                headers: ['姓名', '朝代', '生卒', '籍贯', '指数年', '性别'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}-${p.deathyear}` : '',
                    p.native_place || '', p.index_year || '', p.female ? '女' : '男']) }
        });
        resultsDiv.scrollTop = 0;
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

// 右下角群体标注控制条：地址类型筛选 + 清除
function cbdbAddGroupControl(nRec, nPlace) {
    const ctl = L.control({ position: 'bottomright' });
    ctl.onAdd = () => {
        const div = L.DomUtil.create('div', 'cbdb-map-grpctl');
        const src = window._cbdbMapAddrSource || 'bio';
        // 来源切换（posted 模式无生活地址类型概念，隐藏筛选 chips）
        const srcSel = CBDB_MAP_SOURCES.map(s =>
            `<span class="cbdb-map-chip${s.key === src ? ' active' : ''}" data-src="${s.key}">${s.label}</span>`
        ).join('');
        const showFilters = src !== 'posted';
        const chips = CBDB_MAP_FILTERS.map(f =>
            `<span class="cbdb-map-chip${f.key === window._cbdbMapAddrFilter ? ' active' : ''}" data-k="${f.key}">${f.label}</span>`
        ).join('');
        div.innerHTML = `<div class="cbdb-map-grpctl-row">${srcSel}</div>
            ${showFilters ? `<div class="cbdb-map-grpctl-row">${chips}</div>` : ''}
            <div class="cbdb-map-grpctl-row"><span class="cbdb-map-grpctl-info">${nPlace} 地 · ${nRec} 条</span>
            <span class="cbdb-map-grpctl-clear">✕ 清除标注</span></div>`;
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        div.querySelectorAll('.cbdb-map-chip[data-src]').forEach(chip => {
            chip.onclick = () => {
                if (chip.dataset.src === (window._cbdbMapAddrSource || 'bio')) return;
                window._cbdbMapAddrSource = chip.dataset.src;
                cbdbPlotGroupOnMap();
            };
        });
        div.querySelectorAll('.cbdb-map-chip[data-k]').forEach(chip => {
            chip.onclick = () => {
                if (chip.dataset.k === window._cbdbMapAddrFilter) return;
                window._cbdbMapAddrFilter = chip.dataset.k;
                cbdbPlotGroupOnMap();
            };
        });
        div.querySelector('.cbdb-map-grpctl-clear').onclick = () => {
            if (window.cbdbPersonLayer) { chgisMap.removeLayer(window.cbdbPersonLayer); window.cbdbPersonLayer = null; }
            if (window.cbdbPersonClearCtl) { chgisMap.removeControl(window.cbdbPersonClearCtl); window.cbdbPersonClearCtl = null; }
            if (window._cbdbTrajFitAllCtl) { chgisMap.removeControl(window._cbdbTrajFitAllCtl); window._cbdbTrajFitAllCtl = null; }
        };
        return div;
    };
    window.cbdbPersonClearCtl = ctl.addTo(chgisMap);
}

function setCBDBExport(filename, headers, rows) {
    window._cbdbExport = { filename, headers, rows };
}

function exportCBDBCSV() {
    const exp = window._cbdbExport;
    if (!exp) { alert('当前没有可导出的结果'); return; }
    const esc = v => {
        const s = String(v == null ? '' : v);
        return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const lines = [exp.headers.map(esc).join(',')];
    exp.rows.forEach(r => lines.push(r.map(esc).join(',')));
    // BOM 保证 Excel 正确识别 UTF-8 中文
    const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = exp.filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

function cbdbGoBack() {
    const view = window._cbdbViewStack.pop();
    window._cbdbListView = null;
    window._cbdbExport = null;
    if (!view) { closeCBDBDetail(); return; }
    if (view.type === 'search') {
        if (window._cbdbType !== view.searchType) switchCBDBType(view.searchType);
        else renderCBDBSearchArea(view.searchType);
        const input = document.getElementById('cbdbSearchInput');
        if (input) input.value = view.query;
        searchCBDB();
        closeCBDBDetail();
    } else if (view.type === 'officePersons') {
        loadOfficePersons(view.officeId, view.title, view.filters);
        closeCBDBDetail();
    } else if (view.type === 'placePersons') {
        loadPlacePersons(view.addrId, view.includeSame);
        closeCBDBDetail();
    } else if (view.type === 'statusPersons') {
        loadStatusPersons(view.code, view.title, view.filters);
        closeCBDBDetail();
    } else if (view.type === 'textPersons') {
        loadTextPersons(view.textId, view.title);
        closeCBDBDetail();
    } else if (view.type === 'kinRecursive') {
        // 亲属递归视图本身渲染在右栏，直接恢复即可
        loadKinRecursive(view.id, view.title);
    } else if (view.type === 'entryPersons') {
        loadEntryPersons(view.entryCode, view.title, view.filters);
        closeCBDBDetail();
    }
}

function cbdbPushListView() {
    if (window._cbdbListView) {
        window._cbdbViewStack.push(window._cbdbListView);
        window._cbdbListView = null;
    }
}

function searchCBDBByName(name) {
    if (window._cbdbType !== 'person') switchCBDBType('person');
    else renderCBDBSearchArea('person');
    const input = document.getElementById('cbdbSearchInput');
    if (input) input.value = name;
    searchCBDB();
}

function showPlaceOnMap(lng, lat) {
    switchTab('map');
    setTimeout(() => {
        try {
            initMap();
            if (chgisMap && typeof flyToLocation === 'function') flyToLocation(lng, lat, 9);
        } catch (e) { /* 地图初始化失败时忽略 */ }
    }, 300);
}

// 社会关系：已选类型 chip
function renderAssocChips() {
    const box = document.getElementById('cbdbAssocChips');
    if (!box) return;
    const tp = window._cbdbAssocState.type;
    box.innerHTML = tp
        ? `<div class="cbdb-assoc-chip" onclick="cbdbClearAssocType()" title="点击清除已选类型">
             <b>${escapeHtml(tp.name_chn)}</b><span class="chip-code">code ${tp.code}</span><span class="chip-x">✕</span>
           </div>`
        : `<div class="cbdb-hint" style="margin:0">先在上方搜索并选择一种关系类型</div>`;
}

function cbdbClearAssocType() {
    window._cbdbAssocState.type = null;
    renderAssocChips();
}

// 社会关系检索执行：关系对表格（extraMeta 插槽）+ 涉及人物走统一表格（勾选/范围传递/导出全套）
async function runAssocQuery() {
    const tp = window._cbdbAssocState.type;
    const resultsDiv = document.getElementById('cbdbResults');
    if (!tp) { showToast('请先搜索并选择关系类型', 'warning'); return; }
    if (!resultsDiv) return;
    const pair = (document.getElementById('cbdbAssocPair') || {}).checked ? 1 : 0;
    const fromYear = (document.getElementById('cbdbAssocFrom') || {}).value || '';
    const toYear = (document.getElementById('cbdbAssocTo') || {}).value || '';
    const dy = (document.getElementById('cbdbDynasty') || {}).value || '';
    resultsDiv.innerHTML = '<div class="loading"></div> 查询中...';
    window._cbdbViewStack = [];
    window._cbdbListView = { type: 'assoc', query: tp.name_chn };
    window._cbdbExport = null;

    try {
        const params = new URLSearchParams({ code: tp.code, pair: String(pair), limit: '500' });
        if (fromYear) params.set('from_year', fromYear);
        if (toYear) params.set('to_year', toYear);
        if (dy) params.set('dy', dy);
        const res = await fetch('/api/cbdb/assoc/persons?' + params);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger)">${escapeHtml(data.error)}</p>`; return; }
        const rels = data.relations || [];
        const persons = data.persons || [];
        if (!rels.length) {
            resultsDiv.innerHTML = `<p style="color:var(--text-muted)">未找到「${escapeHtml(tp.name_chn)}」关系记录${pair ? '（含配对）' : ''}。提示：社会关系多未标年份，年份区间会大幅收窄结果</p>`;
            return;
        }
        const relRows = rels.map(r => `
            <tr>
                <td><span class="cbdb-name" onclick="loadCBDBPersonDetail(${r.a_id});event.stopPropagation()">${escapeHtml(r.a_name)}</span></td>
                <td class="cbdb-rel-arrow">${escapeHtml(r.relation)}</td>
                <td><span class="cbdb-name" onclick="loadCBDBPersonDetail(${r.b_id});event.stopPropagation()">${escapeHtml(r.b_name)}</span></td>
                <td>${r.year || '—'}</td>
                <td class="cbdb-rel-text">${escapeHtml((r.text && r.text !== '[n/a]') ? r.text : '')}</td>
            </tr>`).join('');
        const relTableHTML = `
            <div class="cbdb-subhead">关系对（共 ${data.total} 条${data.total > rels.length ? `，显示前 ${rels.length} 条` : ''}）</div>
            <table class="cbdb-table cbdb-rel-table">
                <thead><tr><th>人物 A</th><th>关系</th><th>人物 B</th><th>年份</th><th>文献</th></tr></thead>
                <tbody>${relRows}</tbody>
            </table>`;
        cbdbRenderPersons(resultsDiv, persons, {
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || '')}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty || '—') },
            ],
            extraMeta: relTableHTML,
            export: {
                filename: `cbdb_社会关系_${tp.name_chn}_${tp.code}${pair ? '_含配对' : ''}.csv`,
                headers: ['人物A', 'A_ID', '关系', '人物B', 'B_ID', '年份', '文献'],
                rows: rels.map(r => [r.a_name, r.a_id, r.relation, r.b_name, r.b_id, r.year || '', r.text || ''])
            }
        });
        document.getElementById('cbdbResults').scrollTop = 0;
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger)">查询失败：${escapeHtml(e.message)}</p>`;
    }
}

// 关系对表格（两人关系/地区关系/社会关系共用渲染）
function cbdbRelationsTableHTML(rels, total) {
    const rows = rels.map(r => `
        <tr>
            <td><span class="cbdb-name" onclick="loadCBDBPersonDetail(${r.a_id});event.stopPropagation()">${escapeHtml(r.a_name)}</span></td>
            <td class="cbdb-rel-arrow">${escapeHtml(r.relation)}</td>
            <td><span class="cbdb-name" onclick="loadCBDBPersonDetail(${r.b_id});event.stopPropagation()">${escapeHtml(r.b_name)}</span></td>
            <td>${r.year || '—'}</td>
            <td class="cbdb-rel-text">${escapeHtml((r.text && r.text !== '[n/a]') ? r.text : '')}</td>
        </tr>`).join('');
    return `
        <div class="cbdb-subhead">关系对（共 ${total} 条${total > rels.length ? `，显示前 ${rels.length} 条` : ''}）</div>
        <table class="cbdb-table cbdb-rel-table">
            <thead><tr><th>人物 A</th><th>关系</th><th>人物 B</th><th>年份</th><th>文献</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// 两人关系检索执行（原生 Query Pair-wise Associations）
async function runPairQuery() {
    const a = (window._cbdbPairState || {}).a;
    const b = (window._cbdbPairState || {}).b;
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    if (!a || !b) { showToast('请在两个输入框分别搜索并选择人物', 'warning'); return; }
    if (a.id === b.id) { showToast('双方不能是同一个人', 'warning'); return; }
    resultsDiv.innerHTML = '<div class="loading"></div> 查询中...';
    window._cbdbViewStack = [];
    window._cbdbListView = { type: 'pair', query: a.label + ' · ' + b.label };
    window._cbdbExport = null;
    try {
        const res = await fetch(`/api/cbdb/assoc/between?a=${a.id}&b=${b.id}`);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger)">${escapeHtml(data.error)}</p>`; return; }
        const rels = data.relations || [];
        const kin = data.kin || [];
        const life = p => (p.birthyear > 0 || p.deathyear > 0)
            ? `${p.birthyear > 0 ? p.birthyear : '?'}—${p.deathyear > 0 ? p.deathyear : '?'}` : '生卒不详';
        let body = '';
        if (kin.length) {
            body += `<div class="cbdb-subhead">直系亲属（${kin.length} 条，附五服）</div>
            <table class="cbdb-table cbdb-rel-table"><thead><tr><th>从</th><th>关系</th><th>至</th><th>服制</th><th>亲类型</th></tr></thead><tbody>
            ${kin.map(k => `<tr><td><span class="cbdb-name" onclick="loadCBDBPersonDetail(${k.from_id});event.stopPropagation()">${escapeHtml(k.from_name)}</span></td><td class="cbdb-rel-arrow">${escapeHtml(k.relation)}</td><td>${escapeHtml(k.to_name)}</td><td>${k.mourning ? `<span class="result-card-badge">${escapeHtml(k.mourning)}</span>` : '—'}</td><td style="font-size:12px;color:var(--text-muted)">${escapeHtml(k.kintype || '')}</td></tr>`).join('')}
            </tbody></table>`;
        }
        if (rels.length) {
            body += `<div class="cbdb-subhead">社会关系（${rels.length} 条，双向）</div>
            <table class="cbdb-table cbdb-rel-table"><thead><tr><th>从</th><th>关系</th><th>至</th><th>年份</th><th>文献</th></tr></thead><tbody>
            ${rels.map(r => `<tr><td><span class="cbdb-name" onclick="loadCBDBPersonDetail(${r.from_id});event.stopPropagation()">${escapeHtml(r.from_name)}</span></td><td class="cbdb-rel-arrow">${escapeHtml(r.relation)}</td><td>${escapeHtml(r.to_name)}</td><td>${r.year || '—'}</td><td class="cbdb-rel-text">${escapeHtml((r.text && r.text !== '[n/a]') ? r.text : '')}</td></tr>`).join('')}
            </tbody></table>`;
        }
        if (!rels.length && !kin.length) {
            body = '<p style="color:var(--text-muted);margin-top:8px">两人之间没有直接的社会关系或亲属记录（亲属为单向记录，若互为亲属但仅一方有记录，会显示在有记录的一侧）</p>';
        }
        setCBDBExport(`cbdb_两人关系_${data.a.name_chn}_${data.b.name_chn}.csv`,
            ['类型', '从', '从ID', '关系', '至', '至ID', '年份', '文献', '服制'],
            kin.map(k => ['亲属', k.from_name, k.from_id, k.relation, k.to_name, k.to_id, '', '', k.mourning])
                .concat(rels.map(r => ['社会', r.from_name, r.from_id, r.relation, r.to_name, r.to_id, r.year || '', (r.text || '').replace('[n/a]', ''), ''])));
        resultsDiv.innerHTML = `
            <div class="cbdb-pair-head">
                <span class="cbdb-name" onclick="loadCBDBPersonDetail(${data.a.id})">${escapeHtml(data.a.name_chn)}</span>
                <span class="cbdb-pair-vs">${escapeHtml(data.a.dynasty)} · ${life(data.a)}</span>
                <span class="cbdb-pair-mid">⇋</span>
                <span class="cbdb-name" onclick="loadCBDBPersonDetail(${data.b.id})">${escapeHtml(data.b.name_chn)}</span>
                <span class="cbdb-pair-vs">${escapeHtml(data.b.dynasty)} · ${life(data.b)}</span>
            </div>
            <div class="cbdb-toolbar">
                <span class="cbdb-result-meta" style="margin:0">${rels.length} 社会关系 · ${kin.length} 亲属</span>
                <button class="btn-secondary cbdb-export-btn" onclick="exportCBDBCSV()">⬇ 导出 CSV</button>
            </div>
            ${body}
            <div class="cbdb-subhead">亲属路径（BFS）</div>
            <div id="cbdbKinPathBox">
                <button class="btn-secondary" onclick="runKinPath(${data.a.id}, ${data.b.id})">🔍 查找最短亲属路径（6 步内）</button>
                <div id="cbdbKinPathResult" style="margin-top:6px;font-size:13px"></div>
            </div>`;
        resultsDiv.scrollTop = 0;
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger)">查询失败：${escapeHtml(e.message)}</p>`;
    }
}

// 两人最短亲属路径（KIN_DATA BFS）：路径人名链 + 整体称谓 + 五服徽标
async function runKinPath(aId, bId) {
    const box = document.getElementById('cbdbKinPathResult');
    if (!box) return;
    box.innerHTML = '<div class="loading"></div> 搜索中...';
    try {
        const res = await fetch('/api/cbdb/kin/path?a=' + aId + '&b=' + bId);
        const d = await res.json();
        if (d.error) { box.innerHTML = '<p style="color:var(--danger)">' + escapeHtml(d.error) + '</p>'; return; }
        if (!d.found) {
            box.innerHTML = '<p style="color:var(--text-muted)">' + escapeHtml(d.reason || '未找到路径') + '</p>';
            return;
        }
        const arrow = '<span style="color:var(--text-muted);margin:0 4px">→</span>';
        const names = (d.persons || []).map(p =>
            '<span class="cbdb-name" onclick="loadCBDBPersonDetail(' + p.id + ');event.stopPropagation()">' + escapeHtml(p.name_chn) + '</span>'
        ).join(arrow);
        const mo = d.mourning || {};
        const moBadge = mo.mourning
            ? '<span class="result-card-badge" style="margin-left:6px">' + escapeHtml(mo.mourning) + '</span>'
            : '';
        box.innerHTML =
            '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:2px;line-height:1.9">' + names + moBadge + '</div>'
            + '<div style="color:var(--text-muted);margin-top:4px">'
            + escapeHtml(d.rel_chain || '')
            + ' · ' + d.depth + ' 段关系'
            + (mo.kintype ? ' · ' + escapeHtml(mo.kintype) : '')
            + '</div>';
    } catch (e) {
        box.innerHTML = '<p style="color:var(--danger)">搜索失败：' + escapeHtml(e.message) + '</p>';
    }
}

// 地区关系检索执行（原生 Query Place Associations）：关系对 + 涉及人物走统一表格
async function runPlaceAssocQuery() {
    const place = (window._cbdbPlaceAssocState || {}).place;
    const tp = (window._cbdbPlaceAssocState || {}).type;
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    if (!place) { showToast('请先通过下拉选择地名', 'warning'); return; }
    const fromYear = (document.getElementById('cbdbPlaceAssocFrom') || {}).value || '';
    const toYear = (document.getElementById('cbdbPlaceAssocTo') || {}).value || '';
    const same = (document.getElementById('cbdbPlaceAssocSame') || {}).checked ? 1 : 0;
    const both = (document.getElementById('cbdbPlaceAssocBoth') || {}).checked ? 1 : 0;
    resultsDiv.innerHTML = '<div class="loading"></div> 查询中...';
    window._cbdbViewStack = [];
    window._cbdbListView = { type: 'placeassoc', query: place.label };
    window._cbdbExport = null;
    try {
        const params = new URLSearchParams({ same: String(same), both: String(both), limit: '500' });
        if (tp) { params.set('code', String(tp.code)); params.set('pair', '1'); }
        if (fromYear) params.set('from_year', fromYear);
        if (toYear) params.set('to_year', toYear);
        const res = await fetch(`/api/cbdb/places/${place.id}/assoc?` + params);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger)">${escapeHtml(data.error)}</p>`; return; }
        const rels = data.relations || [];
        const persons = data.persons || [];
        if (!rels.length) {
            resultsDiv.innerHTML = `<p style="color:var(--text-muted)">${escapeHtml(place.label)}地区人物之间未找到社会关系记录${tp ? `（${escapeHtml(tp.name_chn)}）` : ''}。提示：社会关系多未标年份，年份区间会大幅收窄结果</p>`;
            return;
        }
        cbdbRenderPersons(resultsDiv, persons, {
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || '')}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty || '—') },
            ],
            extraMeta: cbdbRelationsTableHTML(rels, data.total) +
                `<div class="cbdb-hint" style="margin-top:6px">地区人物共 ${data.place_persons} 人（籍贯/居址/任职地/索引地址${same ? '，同坐标并入' : ''}），上表为关系涉及人物</div>`,
            export: {
                filename: `cbdb_地区关系_${place.label}${tp ? '_' + tp.name_chn : ''}.csv`,
                headers: ['人物A', 'A_ID', '关系', '人物B', 'B_ID', '年份', '文献'],
                rows: rels.map(r => [r.a_name, r.a_id, r.relation, r.b_name, r.b_id, r.year || '', r.text || ''])
            }
        });
        resultsDiv.scrollTop = 0;
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger)">查询失败：${escapeHtml(e.message)}</p>`;
    }
}

async function searchCBDB() {
    // 社会关系/两人关系/地区关系有自己的表单与执行函数，这里仅做兜底转发
    if (window._cbdbType === 'assoc') { runAssocQuery(); return; }
    if (window._cbdbType === 'pair') { runPairQuery(); return; }
    if (window._cbdbType === 'placeassoc') { runPlaceAssocQuery(); return; }
    const input = document.getElementById('cbdbSearchInput');
    const yearInput = document.getElementById('cbdbYearInput');
    const q = input ? input.value.trim() : (yearInput ? yearInput.value.trim() : '');
    if (!q) { alert('请输入检索词'); return; }
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading"></div> 查询中...';
    window._cbdbViewStack = [];
    window._cbdbListView = { type: 'search', query: q, searchType: window._cbdbType };
    window._cbdbExport = null;

    try {
        if (window._cbdbType === 'person') {
            const dy = (document.getElementById('cbdbDynasty') || {}).value || '';
            const gender = (document.getElementById('cbdbGender') || {}).value || '';
            const place = (window._cbdbPersonState || {}).place;
            const byF = (document.getElementById('cbdbBirthFrom') || {}).value || '';
            const byT = (document.getElementById('cbdbBirthTo') || {}).value || '';
            const dyF = (document.getElementById('cbdbDeathFrom') || {}).value || '';
            const dyT = (document.getElementById('cbdbDeathTo') || {}).value || '';
            const ixF = (document.getElementById('cbdbIndexFrom') || {}).value || '';
            const ixT = (document.getElementById('cbdbIndexTo') || {}).value || '';
            const res = await fetch(`/api/cbdb/search?name=${encodeURIComponent(q)}${dy ? '&dy=' + encodeURIComponent(dy) : ''}${gender ? '&gender=' + gender : ''}${place ? '&addr_id=' + place.id : ''}${byF ? '&by_from=' + byF : ''}${byT ? '&by_to=' + byT : ''}${dyF ? '&dy_from=' + dyF : ''}${dyT ? '&dy_to=' + dyT : ''}${ixF ? '&index_from=' + ixF : ''}${ixT ? '&index_to=' + ixT : ''}`);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到结果</p>'; return; }
            cbdbRenderPersons(resultsDiv, data, {
                columns: [
                    { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                    { label: '朝代', render: p => escapeHtml(p.dynasty) },
                    { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                    { label: '籍贯', render: p => escapeHtml(p.native_place) || '—' }
                ],
                export: { filename: `cbdb_人名_${q}.csv`, headers: ['姓名', '朝代', '生卒', '籍贯'],
                    rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                        p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                        p.native_place || '']) }
            });
            return;
        } else if (window._cbdbType === 'office') {
            const cat = ((document.getElementById('cbdbOfficeCat') || {}).value || '').trim();
            const res = await fetch(`/api/cbdb/offices/search?q=${encodeURIComponent(q)}${cat ? '&category=' + encodeURIComponent(cat) : ''}`);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配官职</p>'; return; }
            resultsDiv.innerHTML = `
                <div class="cbdb-result-meta">共 ${data.length} 个官职，点击查看任职者列表</div>
                ${data.map(o => `
                    <div class="result-card" onclick="loadOfficePersons(${o.office_id}, '${escapeHtml(o.office_chn)}')">
                        <div class="result-card-title">${escapeHtml(o.office_chn)}</div>
                        <div class="result-card-body">
                            ${o.dynasty ? `<span class="result-card-badge">${escapeHtml(o.dynasty)}</span>` : ''}
                            ${o.category ? `<span class="result-card-badge">${escapeHtml(o.category)}</span>` : ''}
                            ${o.trans ? `<span style="font-size:12px;color:var(--text-muted)">${escapeHtml(o.trans)}</span>` : ''}
                        </div>
                    </div>`).join('')}`;
        } else if (window._cbdbType === 'status') {
            const res = await fetch(`/api/cbdb/status/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配身份类型</p>'; return; }
            resultsDiv.innerHTML = `
                <div class="cbdb-result-meta">共 ${data.length} 种身份类型，点击查看人物列表</div>
                ${data.map(s => `
                    <div class="result-card" onclick="loadStatusPersons(${s.code}, '${escapeHtml(s.name_chn)}')">
                        <div class="result-card-title">${escapeHtml(s.name_chn)}</div>
                        ${s.name_eng ? `<div class="result-card-body"><span style="font-size:12px;color:var(--text-muted)">${escapeHtml(s.name_eng)}</span></div>` : ''}
                    </div>`).join('')}`;
        } else if (window._cbdbType === 'text') {
            const res = await fetch(`/api/cbdb/texts/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配著作</p>'; return; }
            resultsDiv.innerHTML = `
                <div class="cbdb-result-meta">共 ${data.length} 部著作，点击查看相关人物</div>
                ${data.map(tx => `
                    <div class="result-card" onclick="loadTextPersons(${tx.text_id}, '${escapeHtml(tx.title_chn)}')">
                        <div class="result-card-title">${escapeHtml(tx.title_chn)}${tx.extant ? ' <span class="result-card-badge">存</span>' : ''}</div>
                        <div class="result-card-body">
                            ${tx.dynasty ? `<span class="result-card-badge">${escapeHtml(tx.dynasty)}</span>` : ''}
                            ${tx.title ? `<span style="font-size:12px;color:var(--text-muted)">${escapeHtml(tx.title)}</span>` : ''}
                        </div>
                    </div>`).join('')}`;
        } else if (window._cbdbType === 'year') {
            const dy = (document.getElementById('cbdbDynasty') || {}).value || '';
            let url = `/api/cbdb/year/people?year=${encodeURIComponent(q)}${dy ? '&dy=' + encodeURIComponent(dy) : ''}`;
            const yEntry = window._cbdbYearEntry;
            if (yEntry && yEntry.id) url += `&entry=${encodeURIComponent(yEntry.id)}`;
            // 三期：查询范围取交集
            if (window._cbdbScope && window._cbdbScope.ids.length) {
                url += `&ids=${window._cbdbScope.ids.join(',')}`;
            }
            const res = await fetch(url);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            const persons = data.persons || [];
            if (!persons.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">该年份未找到在世人物</p>'; return; }
            const scopeNote = (window._cbdbScope && window._cbdbScope.ids.length) ? `（∩ 查询范围 ${window._cbdbScope.ids.length} 人）` : '';
            const entryNote = data.entry_name ? `（入仕：${escapeHtml(data.entry_name)}）` : '';
            cbdbRenderPersons(resultsDiv, persons, {
                extraMeta: `<div class="cbdb-result-meta" style="margin-top:4px">${data.year || q} 年在世${entryNote}，数据库共 ${data.total} 人，显示前 ${persons.length} 位（按索引年排序）${scopeNote}</div>`,
                columns: [
                    { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                    { label: '朝代', render: p => escapeHtml(p.dynasty) },
                    { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                    { label: '索引年', render: p => p.index_year || '—' }
                ],
                export: { filename: `cbdb_${q}年在世.csv`, headers: ['姓名', '朝代', '生卒', '索引年'],
                    rows: persons.map(p => [p.name_chn || p.name, p.dynasty,
                        p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                        p.index_year || '']) }
            });
            return;
        } else if (window._cbdbType === 'entry') {
            const res = await fetch(`/api/cbdb/entries/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配入仕方式</p>'; return; }
            resultsDiv.innerHTML = `
                <div class="cbdb-result-meta">共 ${data.length} 种入仕方式，点击查看人物列表</div>
                ${data.map(en => `
                    <div class="result-card" onclick="loadEntryPersons(${en.code}, '${escapeHtml(en.name_chn)}')">
                        <div class="result-card-title">${escapeHtml(en.name_chn)}</div>
                        ${en.name_eng ? `<div class="result-card-body"><span style="font-size:12px;color:var(--text-muted)">${escapeHtml(en.name_eng)}</span></div>` : ''}
                    </div>`).join('')}`;
        } else {
            const adminType = ((document.getElementById('cbdbAdminType') || {}).value || '').trim();
            const pFrom = ((document.getElementById('cbdbPlaceFrom') || {}).value || '').trim();
            const pTo = ((document.getElementById('cbdbPlaceTo') || {}).value || '').trim();
            let url = `/api/cbdb/places/search?q=${encodeURIComponent(q)}`;
            if (adminType) url += `&admin_type=${encodeURIComponent(adminType)}`;
            if (pFrom) url += `&from_year=${encodeURIComponent(pFrom)}`;
            if (pTo) url += `&to_year=${encodeURIComponent(pTo)}`;
            const res = await fetch(url);
            const data = await res.json();
            if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
            if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配地名</p>'; return; }
            window._cbdbPlaceCache = {};
            data.forEach(pl => { window._cbdbPlaceCache[pl.addr_id] = pl; });
            resultsDiv.innerHTML = `
                <div class="cbdb-result-meta">共 ${data.length} 个地名，点击查看相关人物</div>
                ${data.map(pl => `
                    <div class="result-card" onclick="loadPlacePersons(${pl.addr_id})">
                        <div class="result-card-title">${escapeHtml(pl.name_chn)} <span style="font-size:12px;color:var(--text-muted)">${escapeHtml(pl.name)}</span></div>
                        <div class="result-card-body">
                            ${pl.firstyear ? `<span class="result-card-badge">${pl.firstyear}${pl.lastyear ? '—' + pl.lastyear : ''}</span>` : ''}
                            ${pl.admin_type ? `<span class="result-card-badge">${cbdbAdminTypeLabel(pl.admin_type)}</span>` : ''}
                        </div>
                    </div>`).join('')}`;
        }
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger);">查询失败：${e.message}</p>`;
    }
}

async function runAdvancedQuery() {
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    const gv = id => ((document.getElementById(id) || {}).value || '').trim();
    const st = window._cbdbAdvState || {};
    const name = gv('cbdbAdvName');
    const dy = gv('cbdbDynasty');
    const gender = gv('cbdbAdvGender');
    const filters = {};
    const desc = [];
    if (name) { filters.name = name; desc.push('姓名=' + name); }
    if (dy) { filters.dy = dy; desc.push('朝代'); }
    if (gender) { filters.gender = gender; desc.push(gender === '1' ? '女' : '男'); }
    const yr = (fromId, toId, keyF, keyT, label) => {
        const f = gv(fromId), t = gv(toId);
        if (f) filters[keyF] = f;
        if (t) filters[keyT] = t;
        if (f || t) desc.push(label);
    };
    yr('cbdbAdvFrom', 'cbdbAdvTo', 'from_year', 'to_year', '指数年');
    yr('cbdbAdvBirthFrom', 'cbdbAdvBirthTo', 'birth_from', 'birth_to', '生年');
    yr('cbdbAdvDeathFrom', 'cbdbAdvDeathTo', 'death_from', 'death_to', '卒年');
    if (st.place) { filters.place_id = st.place.id; filters.addr_type = gv('cbdbAdvAddrType') || '1'; desc.push('地址=' + st.place.label); }
    if (st.entry) { filters.entry_code = st.entry.id; desc.push('入仕=' + st.entry.label); }
    yr('cbdbAdvEntryFrom', 'cbdbAdvEntryTo', 'entry_from', 'entry_to', '入仕年');
    if (st.office) { filters.office_id = st.office.id; desc.push('职官=' + st.office.label); }
    yr('cbdbAdvOfficeFrom', 'cbdbAdvOfficeTo', 'office_from', 'office_to', '任职年');
    if (st.status) { filters.status_id = st.status.id; desc.push('身份=' + st.status.label); }
    if (st.text) { filters.text_id = st.text.id; desc.push('著作=' + st.text.label); }
    if (st.assoc) { filters.assoc_code = st.assoc.id; desc.push('关系=' + st.assoc.label); }

    if (!Object.keys(filters).length) { alert('请至少填写一个查询条件'); return; }

    resultsDiv.innerHTML = '<div class="loading"></div> 查询中...';
    window._cbdbViewStack = [];
    window._cbdbListView = null;
    window._cbdbExport = null;

    try {
        const scope = window._cbdbScope;
        const useScope = scope && scope.ids.length;
        let res;
        if (useScope) {
            res = await fetch('/api/cbdb/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filters, person_ids: scope.ids })
            });
        } else {
            const params = new URLSearchParams();
            Object.entries(filters).forEach(([k, v]) => params.set(k, v));
            res = await fetch(`/api/cbdb/query?${params.toString()}`);
        }
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到匹配人物</p>'; return; }
        if (useScope) desc.push(`范围内${scope.ids.length}人`);
        cbdbRenderPersons(resultsDiv, data, {
            extraMeta: useScope ? `<div class="cbdb-result-meta" style="color:var(--accent)">⇅ 已应用查询范围（${scope.ids.length} 人）取交集</div>` : '',
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '-' + p.deathyear : '?' },
                { label: '籍贯', render: p => escapeHtml(p.native_place) || '?' },
                { label: '指数年', render: p => p.index_year || '?' },
                { label: '性别', render: p => p.female ? '女' : '男' }
            ],
            export: { filename: `cbdb_综合查询_${desc.join('_') || '全部'}.csv`,
                headers: ['姓名', '朝代', '生卒', '籍贯', '指数年', '性别'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}-${p.deathyear}` : '',
                    p.native_place || '', p.index_year || '', p.female ? '女' : '男']) }
        });
    } catch (e) {
        resultsDiv.innerHTML = `<p style="color:var(--danger);">查询失败：${e.message}</p>`;
    }
}

// 通用：官职/入仕/社会区分图的筛选条（年份+地址，原生 CBDB 查询维度）
function renderFilterBar(kind, id, title, filters) {
    filters = filters || {};
    window._cbdbFilterAddr = filters.addrId ? { id: filters.addrId, label: filters.addrLabel || '' } : null;
    const addrLabel = kind === 'status' ? '' : (filters.addrLabel || '');
    const addrInput = kind === 'status' ? '' : `
        <input type="text" id="fltAddr" placeholder="${kind === 'office' ? '任职地（可空）' : '入仕地（可空）'}" value="${escapeHtml(addrLabel)}" autocomplete="off" style="flex:1.4;min-width:0">
        <div class="cbdb-ac" id="fltAddrList"></div>`;
    const applyFn = kind === 'office' ? 'applyOfficeFilters' : (kind === 'entry' ? 'applyEntryFilters' : 'applyStatusFilters');
    return `<div class="cbdb-filter-bar">
        <input type="number" id="fltFrom" placeholder="${kind === 'office' ? '任年起' : (kind === 'entry' ? '入仕年起' : '身份起')}" value="${filters.from || ''}" style="width:76px">
        <span style="color:var(--text-muted)">—</span>
        <input type="number" id="fltTo" placeholder="止" value="${filters.to || ''}" style="width:76px">
        ${addrInput}
        <button class="btn-secondary" onclick="${applyFn}(${id}, '${escapeHtml(title)}')">应用过滤</button>
    </div>`;
}

function bindFilterAddrAutocomplete() {
    bindCBDBAutocomplete('fltAddr', 'fltAddrList',
        async q => {
            const res = await fetch(`/api/cbdb/places/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            return (Array.isArray(data) ? data : []).map(p => ({ id: p.addr_id, label: p.name_chn, sub: p.firstyear ? `${p.firstyear}—${p.lastyear || ''}` : (p.admin_type || '') }));
        },
        item => {
            window._cbdbFilterAddr = item;
            const inp = document.getElementById('fltAddr');
            if (inp) inp.value = item.label;
        });
}

async function loadOfficePersons(officeId, title, filters) {
    cbdbPushListView();
    window._cbdbListView = { type: 'officePersons', officeId: officeId, title: title, filters: filters || null };
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';
    try {
        const params = new URLSearchParams();
        if (filters && filters.from) params.set('from_year', filters.from);
        if (filters && filters.to) params.set('to_year', filters.to);
        if (filters && filters.addrId) params.set('addr_id', filters.addrId);
        const res = await fetch(`/api/cbdb/offices/${officeId}/persons${params.toString() ? '?' + params.toString() : ''}`);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">${data.error}</p>`; return; }
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = renderCBDBBackBar(title) + renderFilterBar('office', officeId, title, filters) + '<p style="color:var(--text-muted)">暂无任职记录（过滤条件可能过窄）</p>'; bindFilterAddrAutocomplete(); return; }
        cbdbRenderPersons(resultsDiv, data, {
            backTitle: title,
            extraMeta: renderFilterBar('office', officeId, title, filters),
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                { label: '任期', render: p => p.firstyear ? p.firstyear + (p.lastyear && p.lastyear !== p.firstyear ? '—' + p.lastyear : '') : '—' }
            ],
            export: { filename: `cbdb_官职_${title}.csv`, headers: ['姓名', '朝代', '生卒', '官名', '任期起', '任期止'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                    p.office_chn || title, p.firstyear || '', p.lastyear || '']) }
        });
        bindFilterAddrAutocomplete();
    } catch (e) {
        resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

function applyOfficeFilters(officeId, title) {
    const addr = window._cbdbFilterAddr;
    loadOfficePersons(officeId, title, {
        from: (document.getElementById('fltFrom') || {}).value || '',
        to: (document.getElementById('fltTo') || {}).value || '',
        addrId: addr ? addr.id : '',
        addrLabel: addr ? addr.label : ''
    });
}

function applyEntryFilters(entryCode, title) {
    const addr = window._cbdbFilterAddr;
    loadEntryPersons(entryCode, title, {
        from: (document.getElementById('fltFrom') || {}).value || '',
        to: (document.getElementById('fltTo') || {}).value || '',
        addrId: addr ? addr.id : '',
        addrLabel: addr ? addr.label : '',
        useIndex: (document.getElementById('fltUseIndex') || {}).checked || false
    });
}

function applyStatusFilters(code, title) {
    loadStatusPersons(code, title, {
        from: (document.getElementById('fltFrom') || {}).value || '',
        to: (document.getElementById('fltTo') || {}).value || ''
    });
}

async function loadStatusPersons(code, title, filters) {
    cbdbPushListView();
    window._cbdbListView = { type: 'statusPersons', code: code, title: title, filters: filters || null };
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';
    try {
        const params = new URLSearchParams();
        if (filters && filters.from) params.set('from_year', filters.from);
        if (filters && filters.to) params.set('to_year', filters.to);
        const res = await fetch(`/api/cbdb/status/${code}/persons${params.toString() ? '?' + params.toString() : ''}`);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">${data.error}</p>`; return; }
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = renderCBDBBackBar(title) + renderFilterBar('status', code, title, filters) + '<p style="color:var(--text-muted)">暂无人物记录（过滤条件可能过窄）</p>'; return; }
        cbdbRenderPersons(resultsDiv, data, {
            backTitle: title,
            extraMeta: renderFilterBar('status', code, title, filters),
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                { label: '身份期', render: p => p.firstyear ? p.firstyear + (p.lastyear && p.lastyear !== p.firstyear ? '—' + p.lastyear : '') : '—' }
            ],
            export: { filename: `cbdb_社会区分_${title}.csv`, headers: ['姓名', '朝代', '生卒', '身份起', '身份止'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                    p.firstyear || '', p.lastyear || '']) }
        });
    } catch (e) {
        resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

async function loadTextPersons(textId, title) {
    cbdbPushListView();
    window._cbdbListView = { type: 'textPersons', textId: textId, title: title };
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';
    try {
        const res = await fetch(`/api/cbdb/texts/${textId}/persons`);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">${data.error}</p>`; return; }
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = renderCBDBBackBar(title) + '<p style="color:var(--text-muted)">暂无相关人物</p>'; return; }
        cbdbRenderPersons(resultsDiv, data, {
            backTitle: title,
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                { label: '角色', render: p => escapeHtml(p.role || '—') }
            ],
            export: { filename: `cbdb_著作_${title}.csv`, headers: ['姓名', '朝代', '生卒', '角色'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                    p.role || '']) }
        });
    } catch (e) {
        resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

async function loadPlacePersons(addrId, includeSame) {
    const place = window._cbdbPlaceCache[addrId] || {};
    const title = place.name_chn || ('地名 #' + addrId);
    cbdbPushListView();
    window._cbdbListView = { type: 'placePersons', addrId: addrId, includeSame: !!includeSame };
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';
    try {
        const res = await fetch(`/api/cbdb/places/${addrId}/persons${includeSame ? '?include_same_coord=1' : ''}`);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">${data.error}</p>`; return; }
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = renderCBDBBackBar(title) + '<p style="color:var(--text-muted)">暂无相关人物</p>'; return; }
        const hasCoord = place.x_coord && place.y_coord;
        const toggleBtn = hasCoord ? `<button class="btn-secondary" style="margin-left:8px" onclick="loadPlacePersons(${addrId}, ${includeSame ? 'false' : 'true'})">${includeSame ? '✓ 已并入同坐标地址' : '并入同坐标地址'}</button>` : '';
        cbdbRenderPersons(resultsDiv, data, {
            backTitle: title,
            extraMeta: `<div class="cbdb-result-meta">共 ${data.length} 位相关人物${includeSame ? '（含同坐标地址）' : ''}${toggleBtn}</div>`,
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                { label: '关联', render: p => escapeHtml(p.link_type) }
            ],
            export: { filename: `cbdb_地名_${title}.csv`, headers: ['姓名', '朝代', '生卒', '关联'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                    p.link_type || '']) },
            extraHTML: hasCoord ? `<div style="margin-top:12px"><button class="btn-secondary" onclick="showPlaceOnMap(${place.x_coord}, ${place.y_coord})">🗺️ 在地图中查看${escapeHtml(title)}</button></div>` : ''
        });
    } catch (e) {
        resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

async function loadEntryPersons(entryCode, title, filters) {
    cbdbPushListView();
    window._cbdbListView = { type: 'entryPersons', entryCode: entryCode, title: title, filters: filters || null };
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';
    try {
        const params = new URLSearchParams();
        if (filters && filters.from) params.set('from_year', filters.from);
        if (filters && filters.to) params.set('to_year', filters.to);
        if (filters && filters.addrId) params.set('addr_id', filters.addrId);
        if (filters && filters.useIndex) params.set('use_index', '1');
        const res = await fetch(`/api/cbdb/entries/${entryCode}/persons${params.toString() ? '?' + params.toString() : ''}`);
        const data = await res.json();
        if (data.error) { resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">${data.error}</p>`; return; }
        if (!Array.isArray(data) || !data.length) { resultsDiv.innerHTML = renderCBDBBackBar(title) + renderFilterBar('entry', entryCode, title, filters) + '<p style="color:var(--text-muted)">暂无人物记录（过滤条件可能过窄）</p>'; bindFilterAddrAutocomplete(); return; }
        cbdbRenderPersons(resultsDiv, data, {
            backTitle: title,
            extraMeta: renderFilterBar('entry', entryCode, title, filters),
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn || p.name)}</span>` },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                { label: '入仕年', render: p => p.year || '—' },
                { label: '榜次/科场', render: p => escapeHtml([p.exam_rank, p.exam_field].filter(Boolean).join(' · ')) || '—' }
            ],
            export: { filename: `cbdb_入仕_${title}.csv`, headers: ['姓名', '朝代', '生卒', '入仕方式', '入仕年', '榜次', '科场'],
                rows: data.map(p => [p.name_chn || p.name, p.dynasty,
                    p.birthyear > 0 && p.deathyear > 0 ? `${p.birthyear}—${p.deathyear}` : '',
                    p.entry_name || title, p.year || '', p.exam_rank || '', p.exam_field || '']) }
        });
    } catch (e) {
        resultsDiv.innerHTML = renderCBDBBackBar(title) + `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

// ── 右栏视图切换：详情（默认）↔ 关系网络（点击才放大）──────────
function showCBDBDetailView() {
    const dv = document.getElementById('cbdbDetailView');
    const nv = document.getElementById('cbdbNetworkView');
    if (dv) dv.classList.remove('collapsed');
    if (nv) nv.classList.add('collapsed');
}

function showCBDBNetworkView() {
    const dv = document.getElementById('cbdbDetailView');
    const nv = document.getElementById('cbdbNetworkView');
    if (dv) dv.classList.add('collapsed');
    if (nv) nv.classList.remove('collapsed');
}

// 点「查看关系网络」：加载并切到网络视图
async function loadCBDBNetworkAndShow(id) {
    showCBDBNetworkView();
    await loadCBDBNetwork(id);
}

// 详情关闭：右栏回默认提示（左栏列表不动）
function closeCBDBDetail() {
    const panel = document.getElementById('cbdbDetailPanel');
    if (panel) panel.innerHTML = '<div class="cbdb-empty-hint">在左侧检索并点击人物，这里显示完整详情</div>';
}

async function loadCBDBPersonDetail(id) {
    const detail = document.getElementById('cbdbDetailPanel');
    if (!detail) return;
    cbdbPushListView();
    showCBDBDetailView();
    detail.innerHTML = '<div class="loading" style="margin:20px auto;display:block"></div>';

    try {
        const res = await fetch(`/api/cbdb/person/${id}`);
        const p = await res.json();
        if (p.error) {
            detail.innerHTML = renderCBDBBackBar('') + `<p style="color:var(--danger);">${p.error}</p>`;
            return;
        }

        const fullName = p.name_chn || [p.surname_chn, p.mingzi_chn].filter(Boolean).join('') || p.name;
        const altNames = (p.alt_names || []).map(a => (a.type ? a.type + '：' : '') + a.name).join('，');
        const lifeYears = (p.birthyear > 0 || p.deathyear > 0)
            ? `${p.birthyear > 0 ? p.birthyear : '?'} — ${p.deathyear > 0 ? p.deathyear : '?'}`
            : '生卒年不详';

        detail.innerHTML = `
            ${renderCBDBBackBar(fullName)}
            <div class="cbdb-person-name">${escapeHtml(fullName)}${p.name_chn && p.name ? ` <span class="cbdb-person-pinyin">(${escapeHtml(p.name)})</span>` : ''}</div>
            <div class="cbdb-person-meta">
                <span class="result-card-badge">${escapeHtml(p.dynasty || '朝代未知')}</span>
                <span class="result-card-badge">${lifeYears}</span>
            </div>
            ${altNames ? `<div class="detail-row"><span class="detail-label">字号别称</span><span class="detail-value">${escapeHtml(altNames)}</span></div>` : ''}
            ${(p.addresses || []).length ? `<div class="cbdb-subhead">地址履历</div>
                <div class="cbdb-grid">${p.addresses.map(a => `<div class="cbdb-cell" title="${escapeHtml(a.place)}"><span class="cell-tag">${escapeHtml(a.type || '地址')}</span><span class="cell-main">${escapeHtml(a.place)}</span>${a.firstyear ? `<span class="cell-years">${a.firstyear}${a.lastyear && a.lastyear !== a.firstyear ? '—' + a.lastyear : ''}</span>` : ''}</div>`).join('')}</div>` : ''}
            ${(p.postings || []).length ? `<div class="cbdb-subhead">官职履历（前 ${p.postings.length} 条）</div>
                <div class="cbdb-grid">${p.postings.map(o => `<div class="cbdb-cell">${o.firstyear ? `<span class="cell-years">${o.firstyear}${o.lastyear && o.lastyear !== o.firstyear ? '—' + o.lastyear : ''}</span>` : ''}<span class="cell-main">${escapeHtml(o.office)}</span></div>`).join('')}</div>` : ''}
            ${(p.statuses || []).length ? `<div class="cbdb-subhead">社会区分</div>
                <div class="cbdb-grid">${p.statuses.map(s => `<div class="cbdb-cell">${s.firstyear ? `<span class="cell-years">${s.firstyear}${s.lastyear && s.lastyear !== s.firstyear ? '—' + s.lastyear : ''}</span>` : ''}<span class="cell-main">${escapeHtml(s.status)}</span></div>`).join('')}</div>` : ''}
            ${(p.texts || []).length ? `<div class="cbdb-subhead">著作（${p.texts.length} 种）</div>
                <div class="cbdb-grid">${p.texts.map(t => `<div class="cbdb-cell">${t.dynasty ? `<span class="cell-tag">${escapeHtml(t.dynasty)}</span>` : ''}<span class="cell-main">${escapeHtml(t.title)}${t.extant ? ' <span class="result-card-badge">存</span>' : ''}${t.role ? ` <span class="cell-role">${escapeHtml(t.role)}</span>` : ''}</span></div>`).join('')}</div>` : ''}
            ${p.notes ? `<div class="detail-row"><span class="detail-label">备注</span><span class="detail-value">${escapeHtml(p.notes)}</span></div>` : ''}
            <div style="margin-top:16px">
                <button class="btn-primary" onclick="loadCBDBNetworkAndShow(${p.id})">🕸️ 查看关系网络</button>
                <button class="btn-secondary" style="margin-left:8px" onclick="loadKinRecursive(${p.id}, '${escapeHtml(fullName)}')">👨‍👩‍👧 亲属递归检索</button>
                <button class="btn-secondary" style="margin-left:8px" title="在史料地图上按时间画出此人的生平轨迹（生活地址+任职地）" onclick="cbdbShowPersonTrajectory(${p.id}, '${escapeHtml(fullName)}', ${p.birthyear || 0}, '${escapeHtml(p.dynasty || '')}')">🗺️ 人生轨迹</button>
            </div>
        `;
        detail.scrollTop = 0;
    } catch (e) {
        detail.innerHTML = renderCBDBBackBar('') + `<p style="color:var(--danger);">加载失败：${e.message}</p>`;
    }
}

// 详情页"人生轨迹"入口：单人物直接进轨迹模式（生活地址+任职地，朝代图层按生年联动）
function cbdbShowPersonTrajectory(id, name, birthyear, dynasty) {
    window._cbdbLastPersons = [{ id, index_year: birthyear || 0, dynasty: dynasty || '' }];
    window._cbdbMapLastIds = [id];
    cbdbShowOnMap();
}

async function loadKinRecursive(id, name) {
    const detail = document.getElementById('cbdbDetailPanel');
    if (!detail) return;
    cbdbPushListView();
    showCBDBDetailView();
    window._cbdbListView = { type: 'kinRecursive', id: id, title: name || ('人物 #' + id) };
    window._cbdbExport = null;
    detail.innerHTML = `
        ${renderCBDBBackBar((name || '') + ' · 亲属递归')}
        <div class="cbdb-adv-form">
            <div class="cbdb-adv-row" style="flex-wrap:wrap;gap:6px">
                <label>先世</label><input type="number" id="kinUp" value="2" min="0" max="10" style="width:58px">
                <label>后世</label><input type="number" id="kinDown" value="2" min="0" max="10" style="width:58px">
                <label>旁系</label><input type="number" id="kinCol" value="1" min="0" max="10" style="width:58px">
                <label>姻亲</label><input type="number" id="kinMar" value="1" min="0" max="10" style="width:58px">
            </div>
            <div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">
                <button class="btn-primary" onclick="runKinRecursive(${id})">递归查询</button>
                <button class="btn-secondary" onclick="document.getElementById('kinUp').value=4;document.getElementById('kinDown').value=4;document.getElementById('kinCol').value=3;document.getElementById('kinMar').value=1;runKinRecursive(${id})">⚰️ 五服一键</button>
            </div>
            <div class="cbdb-hint">四参数对应 CBDB 原生亲属检索：先世/后世/旁系/姻亲各维允许的步数；结果附《五服》服制（斬衰/齊衰/期年/大功/小功/緦麻，依 CBDB KIN_Mourning 表）</div>
        </div>
        <div id="kinResults" style="margin-top:10px"></div>`;
}

async function runKinRecursive(id) {
    const box = document.getElementById('kinResults');
    if (!box) return;
    const up = (document.getElementById('kinUp') || {}).value || '2';
    const down = (document.getElementById('kinDown') || {}).value || '2';
    const col = (document.getElementById('kinCol') || {}).value || '1';
    const mar = (document.getElementById('kinMar') || {}).value || '1';
    box.innerHTML = '<div class="loading"></div> 递归展开中（首次查询需加载亲属索引，约数秒）…';
    try {
        const res = await fetch(`/api/cbdb/person/${id}/kin/recursive?up=${up}&down=${down}&col=${col}&mar=${mar}`);
        const data = await res.json();
        if (data.error) { box.innerHTML = `<p style="color:var(--danger);">${data.error}</p>`; return; }
        const persons = data.persons || [];
        if (!persons.length) { box.innerHTML = '<p style="color:var(--text-muted)">该参数范围内未找到亲属</p>'; return; }
        cbdbRenderPersons(box, persons, {
            extraMeta: data.truncated ? '<div class="cbdb-result-meta" style="color:var(--danger)">⚠️ 已达 5000 人上限，结果不完整</div>' : '',
            columns: [
                { label: '姓名', render: p => `<span class="cbdb-name">${escapeHtml(p.name_chn)}</span>` },
                { label: '关系', render: p => escapeHtml(p.relation) },
                { label: '朝代', render: p => escapeHtml(p.dynasty) },
                { label: '生卒', render: p => (p.birthyear > 0 && p.deathyear > 0) ? p.birthyear + '—' + p.deathyear : '—' },
                { label: '服制', render: p => p.mourning ? `<span class="result-card-badge">${escapeHtml(p.mourning)}</span>` : '—' },
                { label: '亲类型', render: p => `<span style="font-size:12px;color:var(--text-muted)">${escapeHtml(p.kintype || '')}</span>` }
            ],
            export: { filename: `cbdb_亲属递归_${data.root}.csv`,
                headers: ['姓名', '关系', '朝代', '生', '卒', '服制', '亲类型', '先世', '后世', '旁系', '姻亲', '关系串'],
                rows: persons.map(p => [p.name_chn, p.relation, p.dynasty,
                    p.birthyear || '', p.deathyear || '', p.mourning, p.kintype,
                    p.up, p.down, p.col, p.mar, p.path_rel]) }
        });
    } catch (e) {
        box.innerHTML = `<p style="color:var(--danger);">查询失败：${e.message}</p>`;
    }
}

// ── 三期：关系网络（右侧面板，力导向图）────────────────────
window._cbdbNetState = { includeKin: false, dy: '' };

async function loadCBDBNetwork(id) {
    const panel = document.getElementById('cbdbNetwork');
    if (!panel) return;
    _cbdbNetState.id = id;
    panel.innerHTML = '<div class="loading" style="margin:30px auto;display:block"></div>';
    const params = new URLSearchParams();
    if (_cbdbNetState.includeKin) params.set('include_kin', '1');
    if (_cbdbNetState.dy) params.set('dy', _cbdbNetState.dy);
    try {
        const res = await fetch(`/api/cbdb/network/${id}?${params.toString()}`);
        const data = await res.json();
        if (data.error) { panel.innerHTML = `<p style="color:var(--danger);padding:20px">${data.error}</p>`; return; }
        renderNetworkPanel(panel, data, id);
    } catch (e) {
        panel.innerHTML = `<p style="color:var(--danger);padding:20px">网络加载失败：${e.message}</p>`;
    }
}

function renderNetworkPanel(panel, data, centerId, group) {
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    const kinCount = edges.filter(e => e.kind === 'kin').length;
    const refetch = group ? 'loadCBDBGroupNetwork()' : `loadCBDBNetwork(${centerId})`;

    const typeCounts = {};
    edges.forEach(e => { const t = netEdgeType(e); typeCounts[t] = (typeCounts[t] || 0) + 1; });

    panel.innerHTML = `
        <div class="cbdb-net-controls">
            <label class="cbdb-net-check"><input type="checkbox" ${_cbdbNetState.includeKin ? 'checked' : ''} onchange="_cbdbNetState.includeKin=this.checked;${refetch}"> 混入亲属</label>
            <select id="cbdbNetDy" onchange="_cbdbNetState.dy=this.value;${refetch}">
                <option value="">全部朝代</option>
            </select>
            <span class="cbdb-net-stat">${group ? '👥 ' + escapeHtml(group.label) + ' · ' : ''}${nodes.length} 节点 · ${edges.length} 边${kinCount ? ` · 亲属 ${kinCount}` : ''}${data.meta && data.meta.kin_expanded ? `（外延 ${data.meta.kin_expanded} 人）` : ''}</span>
        </div>
        <div class="cbdb-net-graph-wrap">
            <div id="cbdbNetGraph" class="cbdb-net-graph"></div>
            <div class="cbdb-net-hint-overlay">滚轮缩放 · 拖拽平移 · 点节点看详情 · 双击以 TA 为中心</div>
        </div>
        <div class="net-chips" id="cbdbNetTypeFilters">
            ${Object.keys(NET_TYPE_STYLE).map(t =>
                `<button class="net-chip on" data-nettype="${t}" onclick="toggleNetType(this)"><i style="background:${NET_TYPE_STYLE[t].color}"></i>${t}<b>${typeCounts[t] || 0}</b></button>`
            ).join('')}
            <span class="cbdb-net-stat" id="cbdbNetFilterStat"></span>
        </div>
        <div class="cbdb-net-legend">
            ${group ? '<span><i class="dot" style="background:#7fb069"></i>群组成员</span>' : '<span><i class="dot" style="background:#d4af6e"></i>中心</span>'}
            <span><i class="dot" style="background:#6f87a8"></i>关联人物</span>
        </div>`;

    // 朝代下拉（异步填充，保留选中）
    fetch('/api/cbdb/dynasties').then(r => r.json()).then(list => {
        const sel = document.getElementById('cbdbNetDy');
        if (sel && Array.isArray(list)) {
            sel.innerHTML = '<option value="">全部朝代</option>' +
                list.map(d => `<option value="${d.code}" ${String(d.code) === String(_cbdbNetState.dy) ? 'selected' : ''}>${escapeHtml(d.name)}</option>`).join('');
        }
    }).catch(() => {});

    window._cbdbNetData = { nodes, edges, centerId };
    const graph = document.getElementById('cbdbNetGraph');
    if (!graph) return;
    if (nodes.length <= 1) {
        graph.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px">暂无关系数据</div>';
        return;
    }
    drawNetGraph(graph, nodes, edges, centerId);
}

// 力导向布局（纯 SVG，无依赖；220 轮同步模拟，≤150 节点瞬时完成）
// 边关系类型归类（供 drawNetGraph 与筛选复用）
function netEdgeType(e) {
    const r = e.relation || '';
    if (e.kind === 'kin') {
        if (/妻|夫|婿|媳|岳|舅|姨|嫂|姊夫|妹夫|姻|婦|壻/.test(r)) return '姻亲';
        return '血亲';
    }
    if (/師|门|門|弟子|學|学|生|友|問|问|講|讲|授|同年|座主|從游|过从|過從|書院/.test(r)) return '师友学术';
    if (/恩主|薦|荐|舉|举|同僚|宰|參|参|黜|贬|貶|劾|使|判|知州|太守|守|尉|丞|郎|御史|宰相|執政|除|拜|迁|遷|罷|免/.test(r)) return '政治行政';
    if (/詩|诗|文|序|跋|字說|字说|祭|書信|唱和|題|题|賦|赋|銘|铭|記|记|传|傳|論|论/.test(r)) return '文学创作';
    return '其他交游';
}

const NET_TYPE_STYLE = {
    '血亲':     { color: '#e2725b', type: 'solid',  width: 2.2 },
    '姻亲':     { color: '#c97b8e', type: 'dashed', width: 1.8 },
    '师友学术': { color: '#6a9bd0', type: 'solid',  width: 1.7 },
    '政治行政': { color: '#9a82d4', type: 'solid',  width: 1.7 },
    '文学创作': { color: '#6faa84', type: 'solid',  width: 1.6 },
    '其他交游': { color: '#8a93a0', type: 'solid',  width: 1.1 }
};

// ECharts 力导向图：roam 缩放平移 / 类型着色 / 边标签 / 点击详情
function drawNetGraph(container, nodes, edges, centerId) {
    if (typeof echarts === 'undefined') {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px">图表组件未加载（static/js/lib/echarts.min.js 缺失）</div>';
        return;
    }
    if (!nodes || nodes.length <= 1) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px">暂无关系数据</div>';
        return;
    }

    const byId = {};
    nodes.forEach(n => { byId[n.id] = n; n.deg = 0; });
    edges.forEach(e => {
        const a = byId[e.source], b = byId[e.target];
        if (!a || !b) return;
        a.deg++; b.deg++;
    });

    const n = nodes.length;
    const repulsion = Math.round(Math.min(Math.max(n * 5, 280), 700));
    const edgeLength = n > 90 ? [45, 105] : n > 45 ? [48, 110] : [50, 115];
    const gravity = n > 90 ? 0.16 : 0.12;
    const initZoom = n > 90 ? 0.7 : 1;
    // 高度数节点始终标注（叶子太多时按度数取前若干）
    const degRank = nodes.slice().sort((a, b) => (b.deg || 0) - (a.deg || 0));
    const labelSet = new Set(degRank.slice(0, n > 60 ? 9 : 18).map(nd => nd.id));
    const NAME_FONT = '"KaiTi","STKaiti","FZKaiS","STSong","SimSun",serif';
    // 球状渐变节点：比平涂更有质感（中心鎏金 / 成员松绿 / 关联黛蓝）
    const orb = (c1, c2) => new echarts.graphic.RadialGradient(0.5, 0.36, 0.78, [
        { offset: 0, color: c1 }, { offset: 1, color: c2 }
    ]);
    const ORB = { center: orb('#f9e7b6', '#bd8c3f'), member: orb('#b3d29a', '#5f8a53'), assoc: orb('#c2d6e8', '#5d7fa3') };

    const chartNodes = nodes.map(nd => {
        const isCenter = nd.id === centerId;
        return {
            id: String(nd.id),
            name: nd.name_chn || nd.name || String(nd.id),
            symbolSize: isCenter ? 28 : Math.min(8 + (nd.deg || 0) * 1.4, 22),
            category: isCenter ? 0 : (nd.member ? 1 : 2),
            label: {
                show: isCenter || n <= 26 || labelSet.has(nd.id),
                position: isCenter ? 'bottom' : 'right',
                distance: isCenter ? 7 : 5,
                fontSize: isCenter ? 14 : 12,
                fontWeight: isCenter ? 'bold' : 'normal',
                color: isCenter ? '#ecd9a8' : '#d9d4c8'
            },
            itemStyle: Object.assign(
                { color: isCenter ? ORB.center : (nd.member ? ORB.member : ORB.assoc) },
                isCenter
                    ? { borderColor: 'rgba(255,244,214,0.9)', borderWidth: 2, shadowBlur: 24, shadowColor: 'rgba(212,175,110,0.65)' }
                    : { borderColor: 'rgba(240,238,230,0.3)', borderWidth: 1, shadowBlur: Math.min(4 + (nd.deg || 0) * 1.5, 12), shadowColor: 'rgba(160,190,230,0.3)' }
            ),
            _raw: nd
        };
    });

    const chartLinks = edges.map((e, i) => {
        const t = netEdgeType(e);
        const st = NET_TYPE_STYLE[t];
        const weak = t === '其他交游';
        return {
            source: String(e.source),
            target: String(e.target),
            _type: t,
            label: {
                show: false,
                formatter: e.relation || '',
                fontSize: 11,
                color: '#e8e2d4',
                backgroundColor: 'rgba(14,15,20,0.88)',
                borderColor: st.color + '66',
                borderWidth: 1,
                borderRadius: 4,
                padding: [2, 5]
            },
            lineStyle: {
                color: st.color,
                type: st.type,
                width: weak ? 1 : st.width,
                curveness: (i % 2 ? -1 : 1) * 0.05,
                opacity: weak ? 0.3 : 0.48
            },
            emphasis: { label: { show: true }, lineStyle: { opacity: 0.95, width: st.width + 1 } }
        };
    });

    if (container._echart) { container._echart.dispose(); container._echart = null; }
    const chart = echarts.init(container);
    chart.setOption({
        animationDuration: 800,
        animationDurationUpdate: 300,
        backgroundColor: 'transparent',
        tooltip: {
            backgroundColor: 'rgba(22,23,29,0.96)',
            borderWidth: 1,
            borderColor: 'rgba(201,169,110,0.25)',
            textStyle: { color: '#e8e4dc', fontSize: 12 },
            formatter: p => {
                if (p.dataType === 'node') {
                    const raw = (p.data && p.data._raw) || {};
                    const life = (raw.birthyear > 0 || raw.deathyear > 0)
                        ? (raw.birthyear > 0 ? raw.birthyear : '?') + '–' + (raw.deathyear > 0 ? raw.deathyear : '?') : '生卒不详';
                    return '<div style="font-family:' + NAME_FONT + ';font-size:15px;color:#ecd9a8;margin-bottom:2px">' + escapeHtml(p.data.name) + '</div>'
                        + '<span style="color:#a0a0b0">' + escapeHtml(raw.dynasty || '') + ' · ' + life + ' · 关系数 ' + (raw.deg || 0) + '</span>'
                        + '<br><span style="color:#6b6b7b;font-size:11px">单击看详情 · 双击以 TA 为中心</span>';
                }
                const d = p.data || {};
                const rel = (d.label && d.label.formatter) || '';
                const sa = byId[d.source], tb = byId[d.target];
                const sn = sa ? (sa.name_chn || sa.name) : d.source;
                const tn = tb ? (tb.name_chn || tb.name) : d.target;
                const st = NET_TYPE_STYLE[d._type] || NET_TYPE_STYLE['其他交游'];
                return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + st.color + ';margin-right:6px"></span>'
                    + '<b style="color:#e8e4dc">' + escapeHtml(d._type) + '</b><br>'
                    + escapeHtml(String(sn)) + ' — ' + escapeHtml(rel) + ' → ' + escapeHtml(String(tn));
            }
        },
        series: [{
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            zoom: initZoom,
            center: ['50%', '47%'],
            force: { repulsion: repulsion, edgeLength: edgeLength, gravity: gravity, friction: 0.25 },
            categories: [
                { name: '中心', itemStyle: { color: '#d4af6e' } },
                { name: '群组成员', itemStyle: { color: '#7fb069' } },
                { name: '关联人物', itemStyle: { color: '#6f87a8' } }
            ],
            data: chartNodes,
            links: chartLinks,
            label: {
                fontFamily: NAME_FONT,
                textBorderColor: 'rgba(8,9,12,0.85)',
                textBorderWidth: 3
            },
            labelLayout: { hideOverlap: true },
            emphasis: { focus: 'adjacency', lineStyle: { width: 2.6 }, label: { fontWeight: 'bold' } }
        }]
    });
    chart.on('click', p => {
        if (p.dataType === 'node' && p.data && p.data.id) loadCBDBPersonDetail(Number(p.data.id));
    });
    chart.on('dblclick', p => {
        const nid = p.data && p.data.id ? Number(p.data.id) : null;
        if (p.dataType === 'node' && nid && nid !== centerId) {
            loadCBDBNetworkAndShow(nid);
        }
    });
    container._echart = chart;
}

// 关系类型筛选（纯前端过滤边，不重新请求；图例胶囊即开关）
function toggleNetType(chip) {
    chip.classList.toggle('on');
    applyNetTypeFilter();
}

function applyNetTypeFilter() {
    const box = document.getElementById('cbdbNetTypeFilters');
    const graph = document.getElementById('cbdbNetGraph');
    const stash = window._cbdbNetData;
    if (!box || !graph || !stash) return;
    const on = new Set();
    box.querySelectorAll('.net-chip.on').forEach(i => on.add(i.dataset.nettype));
    const filtered = stash.edges.filter(e => on.has(netEdgeType(e)));
    const visible = new Set();
    filtered.forEach(e => { visible.add(e.source); visible.add(e.target); });
    visible.add(stash.centerId);
    const filteredNodes = stash.nodes.filter(n => visible.has(n.id));
    const stat = document.getElementById('cbdbNetFilterStat');
    if (stat) stat.textContent = '显示 ' + filtered.length + ' / ' + stash.edges.length + ' 条关系 · ' + filteredNodes.length + ' 人';
    drawNetGraph(graph, filteredNodes, filtered, stash.centerId);
}

// ── AI 助手 ────────────────────────────────────────────
const AI_KB_TRIGGERS = ['论文', '写作', '注释', '引用', '参考文献', '书评', '札记', '规范', '标题', '摘要', '选题', '文献综述', '学术史', '投稿', '期刊', '摘要', '翻译', '史料', '长编', '繁体', '体例', '考证', '目录', '检索', '工具书', '类书', '版本', '校勘', '墓志', '简牍', '敦煌'];

function _kbKbForPrompt(text) {
    try {
        if (!_kbData || !Array.isArray(_kbData.entries)) return '';
        const hit = AI_KB_TRIGGERS.some(k => (text || '').includes(k));
        if (!hit) return '';
        const lines = _kbData.entries.map(e => '\u00b7 ' + e.text + '(' + (e.src || '') + ')');
        return '\n\n用户的问题是学术写作/规范/史料方法方向。以下为本地知识库(荣新江《学术训练与学术规范》第二版要点),回答时优先参照其中方法论,可引用但不必逐条列举:\n' + lines.join('\n');
    } catch (e) { return ''; }
}

let _aiKbExtra = ''; // 手动引用的知识库条目(拼接进 system prompt)
let _aiModel = localStorage.getItem('jx_ai_model') || '';

// ── 历史研究提示词库: 点击填入输入框可编辑(框架主导权: AI 给料,人来改) ──
const AI_PROMPTS = [
  { cat: '读史料', items: [
    { label: '📋 史料摘要', text: '请对以下史料做学术摘要：提取时间、地点、人物、事件，分析其史料价值（成书背景、作者立场、记载可靠性）。史料：' },
    { label: '📜 古文今译', text: '请把以下史料翻译成现代汉语，保持原意，人名地名官名首次出现括注原文；译后简要说明其中关键的制度或典故。史料：' },
    { label: '🔎 史料批判', text: '请从史料学角度批判性考察以下记载：它成书于何时、作者可能站在什么立场、有没有讳饰或夸大、与同类史料相比可信度如何？史料：' },
    { label: '⚖️ 史料对比', text: '以下是对同一事件的两段记载。请逐条比对其异同，分析差异可能反映的史书体例、作者立场或史料来源问题。记载一：\n记载二：' },
    { label: '🏛️ 职官制度释读', text: '请解释以下史料中涉及的官名、机构及其职掌，说明该职官在当时的政治地位，并提示相关研究可检索的工具书（如《中国历代官制大辞典》、CBDB 职官检索）。史料：' },
  ]},
  { cat: '写作与论证', items: [
    { label: '✏️ 论证分析', text: '请分析以下论证的结构：论点是什么、证据链是否完整、有没有跳跃或循环论证、可补充哪类反证？我的论证：' },
    { label: '🎯 选题打磨', text: '我在考虑这个论文选题：【 】。请帮我：1）用一句话概括它的学术问题意识；2）列出 3 个可能的创新点或贡献；3）指出最明显的两个薄弱处；4）建议两类必须读的核心研究。' },
    { label: '🧩 段落逻辑检查', text: '请检查以下段落的论证逻辑：每句在论证链中的功能、有没有重复或断裂、论据与论点的对应关系。要求逐句批注，不要重写原文。段落：' },
    { label: '📝 引言/结论重写建议', text: '请针对以下引言/结论给出重写建议：1）它目前的问题（空泛/重复/与正文脱节等）；2）一个可行的三段式结构（问题-方法-贡献）；3）要求保留我的核心观点，只动组织方式。文本：' },
    { label: '📖 概念解释', text: '请解释以下史学概念：它的学术定义、提出者或经典使用、在研究中常见的误用、以及适合进一步阅读的文献。概念：' },
  ]},
  { cat: '自检与攻防', items: [
    { label: '⚔️ 反方质询', text: '请扮演一位严苛的同行评审，对我以下论点提出最有力的 5 条反驳（包括史料反证的可能、概念误用、时代错置），然后给我的应对策略各写一句。论点：' },
    { label: '🧪 证据充分性检查', text: '我目前的证据链：【 】。请评估：1）核心论点有几条独立证据支撑；2）有没有单源孤证；3）还缺什么类型的材料（传世/出土/文集/方志/域外文献）才能闭环。' },
    { label: '🔍 时代错置扫描', text: '请扫描以下文字，找出可能的时代错置：用后出的概念/制度/观念描述前代的地方，逐条指出并给出更严谨的替代表述。文本：' },
    { label: '🗂️ 综述框架', text: '我的研究主题：【 】。请帮我搭一个文献综述框架：1）按问题意识分 3-4 个板块；2）每个板块列出该领域的代表学者与代表作类型；3）指出板块之间的承转逻辑。' },
  ]},
  { cat: '语言', items: [
    { label: '🌐 学术英语润色', text: '请将以下中文学术表述翻译成学术英语（历史学专业），保持术语准确（首次出现括注拉丁转写），句式符合英文学术写作习惯。文本：' },
    { label: '📰 英文摘要撰写', text: '请基于以下中文摘要撰写英文摘要（150-250 词）：遵循国际史学期刊惯例，包含问题意识、材料、方法、贡献。中文摘要：' },
    { label: '🇯🇵 日文史料汉读辅助', text: '请帮助阅读以下日文论著（训读体/学术日语）：1）概括作者的核心论点；2）指出关键术语的日文原文与中文对应；3）如有汉文史料引用，说明其与中国史料的异文。文本：' },
  ]},
];

function aiPromptLibToggle() {
    const panel = document.getElementById('aiPromptLibPanel');
    if (!panel) return;
    if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
    panel.style.display = '';
    panel.innerHTML = AI_PROMPTS.map((g, gi) =>
        '<div class="pl-cat"><div class="pl-cat-title">' + g.cat + '</div>' +
        g.items.map(it => '<div class="pl-item" onclick="aiPromptUse(' + gi + ',\'' + it.label.slice(0,2) + '\', this)">' + it.label + '</div>').join('') + '</div>'
    ).join('');
    // 给每项存 index 更稳: 重渲染带 data 属性
    panel.querySelectorAll('.pl-item').forEach((el, k) => {
        let flat = [];
        AI_PROMPTS.forEach(g => g.items.forEach(it => flat.push(it)));
        el.onclick = () => aiPromptPick(flat[k]);
    });
}
window.aiPromptLibToggle = aiPromptLibToggle;

function aiPromptPick(item) {
    const input = document.getElementById('aiChatInput');
    if (input) { input.value = item.text; input.focus(); }
    const panel = document.getElementById('aiPromptLibPanel');
    if (panel) panel.style.display = 'none';
    showToast('提示词已填入,可修改后再发送', 'success');
}
window.aiPromptPick = aiPromptPick;

// ── 模型选择 ──
async function loadAiModels() {
    const sel = document.getElementById('aiModelSelect');
    if (!sel) return;
    try {
        const d = await (await fetch('/api/ai/models')).json();
        const models = d.models || [];
        sel.innerHTML = models.map(m =>
            '<option value="' + m.id + '"' + (m.id === (window._aiModel || d.default) ? ' selected' : '') + '>' + m.name + '</option>'
        ).join('');
        const cur = models.find(m => m.id === (window._aiModel || d.default));
        const desc = document.getElementById('aiModelDesc');
        if (desc) desc.textContent = cur ? cur.desc : '';
        window._aiModel = sel.value;
    } catch (e) {
        sel.innerHTML = '<option>模型清单加载失败</option>';
    }
}
window.loadAiModels = loadAiModels;

function aiModelChange() {
    const sel = document.getElementById('aiModelSelect');
    if (!sel) return;
    window._aiModel = sel.value;
    localStorage.setItem('jx_ai_model', sel.value);
    showToast('已切换模型', 'success');
}
window.aiModelChange = aiModelChange;


function aiKbRefToggle() {
    const panel = document.getElementById('aiKbRefPanel');
    if (!panel) return;
    if (panel.style.display === 'none') {
        panel.style.display = '';
        aiKbRefRender();
    } else {
        panel.style.display = 'none';
    }
}
window.aiKbRefToggle = aiKbRefToggle;

async function aiKbRefRender() {
    const panel = document.getElementById('aiKbRefPanel');
    if (!panel) return;
    try {
        if (!_kbData) {
            const res = await fetch('/api/writing-kb');
            _kbData = await res.json();
        }
        const themes = _kbData.themes || [];
        const entries = _kbData.entries || [];
        panel.innerHTML = '<div class="kb-chips" style="margin-bottom:8px">' +
            themes.map(t => {
                const n = entries.filter(e => e.theme === t.key).length;
                return '<span class="kb-chip" onclick="aiKbRefPick(\'' + t.key + '\')" style="color:' + (t.color || '#c9a96e') + ';border-color:' + (t.color || '#c9a96e') + '55">' + (t.label || t.key) + '·' + n + '</span>';
            }).join('') + '</div>' +
            '<div class="ai-kbref-list" id="aiKbRefList"><div class="empty-hint">点上面主题挑条目，选中后 AI 会带着它回答</div></div>';
    } catch (e) {
        panel.innerHTML = '<div class="empty-hint">知识库加载失败</div>';
    }
}

function aiKbRefPick(themeKey) {
    const entries = (_kbData && _kbData.entries) || [];
    const list = document.getElementById('aiKbRefList');
    if (!list) return;
    const sub = entries.filter(e => e.theme === themeKey);
    list.innerHTML = sub.map(e => {
        const short = (e.text || '').slice(0, 42) + ((e.text || '').length > 42 ? '…' : '');
        return '<div class="ai-kbref-item" onclick="aiKbRefUse(' + e.id + ')">' + escapeHtml(short) + '</div>';
    }).join('') || '<div class="empty-hint">该主题暂无条目</div>';
}
window.aiKbRefPick = aiKbRefPick;

function aiKbRefUse(id) {
    const entries = (_kbData && _kbData.entries) || [];
    const e = entries.find(x => x.id === id);
    if (!e) return;
    _aiKbExtra = '\n\n用户手动引用的学术规范条目（回答时请结合这条展开）：「' + e.text + '」（出处：' + (e.src || '') + '）';
    const badge = document.getElementById('aiKbRefBadge');
    if (badge) {
        badge.style.display = '';
        badge.textContent = '已引用：' + (e.text || '').slice(0, 18) + '…';
    }
    showToast('已引用这条规范，下一轮对话生效', 'success');
}
window.aiKbRefUse = aiKbRefUse;

function aiKbRefClear() {
    _aiKbExtra = '';
    const badge = document.getElementById('aiKbRefBadge');
    if (badge) badge.style.display = 'none';
}
window.aiKbRefClear = aiKbRefClear;

async function sendAIChat() {
    const input = document.getElementById('aiChatInput');
    const messages = document.getElementById('aiChatMessages');
    if (!input || !messages) return;
    const text = input.value.trim();
    if (!text) return;

    // 添加用户消息
    messages.innerHTML += `<div class="ai-message user"><div class="ai-bubble">${escapeHtml(text)}</div></div>`;
    input.value = '';
    messages.scrollTop = messages.scrollHeight;

    // 显示加载
    const loadingId = 'ai-loading-' + Date.now();
    messages.innerHTML += `<div class="ai-message system" id="${loadingId}"><div class="ai-bubble"><div class="loading"></div> 思考中...</div></div>`;
    messages.scrollTop = messages.scrollHeight;

    try {
        const _aiKb = _kbKbForPrompt(text);
        const msgs = [
            { role: 'system', content: '你是「六月息」内置的历史学研究助手，擅长史料解读、历史概念阐释与史学论证。请用准确、清晰的中文回答，必要时引用具体史实，并适当使用小标题与分段以提升可读性。' + _aiKb + (_aiKbExtra || '') },
            ...(Array.isArray(window._aiHistory) ? window._aiHistory : []),
            { role: 'user', content: text }
        ];
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: msgs, model: window._aiModel || undefined })
        });
        const data = await res.json();

        // 移除加载
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        const content = data.response || (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || '';
        if (data.error) {
            messages.innerHTML += `<div class="ai-message system"><div class="ai-bubble">错误：${escapeHtml(data.error)}</div></div>`;
        } else if (content) {
            window._aiHistory = msgs.slice(1).concat([{ role: 'assistant', content: content }]).slice(-10);
            messages.innerHTML += `<div class="ai-message ai"><div class="ai-bubble">${formatAIResponse(content)}</div></div>`;
        } else {
            messages.innerHTML += `<div class="ai-message system"><div class="ai-bubble">未收到有效回复</div></div>`;
        }
    } catch (e) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();
        messages.innerHTML += `<div class="ai-message system"><div class="ai-bubble">请求失败：${escapeHtml(e.message)}</div></div>`;
    }

    messages.scrollTop = messages.scrollHeight;
}

function aiQuickAction(type) {
    const prompts = {
        summarize: '请帮我总结以下历史文献的核心内容，提取时间、地点、人物、事件等关键信息：\n\n【请粘贴史料内容】',
        analyze: '请分析以下历史论证的逻辑结构，指出其薄弱环节和可能存在的问题：\n\n【请粘贴论证内容】',
        concept: '请解释以下历史概念的内涵、演变过程及其在特定历史时期的意义：\n\n【请输入概念名称】',
        compare: '请比较分析以下两段史料对同一事件记载的差异及其可能原因：\n\n【史料一】\n\n【史料二】'
    };
    const input = document.getElementById('aiChatInput');
    if (input) {
        input.value = prompts[type] || '';
        input.focus();
    }
}

function setAIInput(text) {
    const input = document.getElementById('aiChatInput');
    if (input) { input.value = text; input.focus(); }
}

function formatAIResponse(text) {
    // 简单的 markdown 格式转换
    return escapeHtml(text)
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── 系统状态 ───────────────────────────────────────────
async function checkStatus() {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    if (!dot || !text) return;

    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        const obsidianOk = data.obsidian;
        const deepseekOk = data.deepseek;

        dot.classList.remove('warn', 'error');
        if (obsidianOk && deepseekOk) {
            dot.style.background = 'var(--success)';
            text.textContent = '全部就绪';
        } else if (obsidianOk || deepseekOk) {
            dot.classList.add('warn');
            text.textContent = '部分就绪';
        } else {
            dot.classList.add('error');
            text.textContent = 'API 未连接';
        }
    } catch {
        dot.classList.add('error');
        text.textContent = '后端未启动';
    }
}

// ── 全局搜索（顶部搜索栏）─────────────────────────────
async function globalSearch() {
    const input = document.getElementById('obsidianSearchInput');
    const query = input ? input.value.trim() : '';
    if (!query) return;

    // 在 Obsidian Vault 中搜索
    switchTab('cbdb'); // 复用 CBDB 结果区
    const resultsDiv = document.getElementById('cbdbResults');
    if (!resultsDiv) return;
    resultsDiv.innerHTML = '<div class="loading" style="margin:12px auto;display:block"></div><p style="text-align:center;color:var(--text-muted);font-size:13px">搜索 Vault 中...</p>';

    try {
        const res = await fetch(`/api/obsidian/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
            resultsDiv.innerHTML = data.slice(0, 10).map(f => `
                <div class="doc-item" onclick="openObsidianURI('${f.path || f}')">
                    <div class="doc-icon">📄</div>
                    <div class="doc-info">
                        <div class="doc-title">${(f.basename || f).replace('.md', '')}</div>
                        <div class="doc-meta">${f.path || ''}</div>
                    </div>
                </div>
            `).join('');
        } else {
            resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-text">未找到结果</div><div class="empty-state-hint">请检查 Obsidian 是否已连接</div></div>';
        }
    } catch (e) {
        resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">搜索失败</div><div class="empty-state-hint">请检查 Obsidian 是否已连接</div></div>';
    }
}

// ── 史料地图 ───────────────────────────────────────────
let chgisMap = null;
let currentDynastyLayer = null;
let markerLayers = [];

function initMap() {
    if (chgisMap) return;
    const mapEl = document.getElementById('leafletMap');
    if (!mapEl || typeof L === 'undefined') return;

    chgisMap = L.map('leafletMap', {
        center: [35, 110],
        zoom: 5,
        zoomControl: true,
        attributionControl: false
    });

    // 添加底图图层（中文标注优先：高德；CSS 反色滤镜实现暗夜风格）
    const gaodeUrl = 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}';
    const gaodeOpts = { maxZoom: 19, subdomains: ['1', '2', '3', '4'] };
    const DARK_FILTER = 'invert(1) hue-rotate(180deg) saturate(0.35) brightness(0.9) contrast(0.95)';
    window.baseLayers = {};
    window.baseLayers['深色'] = L.tileLayer(gaodeUrl, gaodeOpts);
    // 瓦片容器在图层 add 后才存在，监听 add 事件挂滤镜（重复切换后容器复用，只挂一次即可）
    window.baseLayers['深色'].on('add', function () {
        const c = window.baseLayers['深色'].getContainer();
        if (c) c.style.filter = DARK_FILTER;
    });
    window.baseLayers['浅色'] = L.tileLayer(gaodeUrl, gaodeOpts);
    window.baseLayers['暗灰(英文)'] = L.layerGroup([
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 }),
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, pane: 'shadowPane' })
    ]);

    // 默认使用深色底图
    window.baseLayers['深色'].addTo(chgisMap);
    const darkContainer = window.baseLayers['深色'].getContainer();
    if (darkContainer) darkContainer.style.filter = DARK_FILTER;

    // 添加图层切换控件
    L.control.layers(window.baseLayers, null, { position: 'topright' }).addTo(chgisMap);

    // 地图 → CBDB 反查开关（任务2）
    window._cbdbReverseOn = false;
    cbdbAddReverseControl();
    chgisMap.on('click', cbdbMapClickReverse);

    // 地图加载完成后调整大小
    setTimeout(() => chgisMap.invalidateSize(), 100);
}

// 朝代 → 都城键（对应 CHGIS_CAPITALS）
const DYNASTY_CAPITALS = {
    xia: ['yangcheng'],
    shang: ['yinxu'],
    zhou_west: ['haojing'],
    zhou_east: ['luoyi_zhou'],
    qin: ['xianyang'],
    han_west: ['changan_han'],
    han_east: ['luoyang_han'],
    wei: ['luoyang_wei'],
    shu: ['chengdu_shu'],
    wu: ['jianye'],
    jin_west: ['luoyang_jin'],
    jin_east: ['jiankang'],
    tang: ['chang_an', 'luoyang'],
    song_north: ['kaifeng'],
    song_south: ['hangzhou'],
    yuan: ['beijing_yuan'],
    ming: ['nanjing_ming', 'beijing_ming'],
    qing: ['beijing_ming'],
    southern_northern: ['pingcheng', 'luoyang_beiwei', 'ye', 'changan_bei', 'jiankang'],
    sui: ['daxing'],
    five_dynasties: ['kaifeng', 'luoyang', 'taiyuan', 'jiangning', 'hangzhou_wuyue', 'fuzhou', 'changsha', 'guangzhou', 'jiangling', 'chengdu']
};

async function switchDynasty(dynastyKey) {
    if (!chgisMap) initMap();
    if (!chgisMap) return;

    // 高亮按钮
    document.querySelectorAll('.dynasty-btn').forEach(b => b.classList.remove('active'));
    const activeBtn = document.querySelector(`.dynasty-btn[data-dynasty="${dynastyKey}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    const infoLabel = document.getElementById('mapDynastyLabel');
    if (infoLabel) infoLabel.textContent = '加载中...';

    // 清除旧图层
    if (currentDynastyLayer) {
        chgisMap.removeLayer(currentDynastyLayer);
        currentDynastyLayer = null;
    }
    markerLayers.forEach(l => chgisMap.removeLayer(l));
    markerLayers = [];

    // 朝代轮廓与 CCTS 疆域层任一开启 → 侧栏收窄放大图区
    window._dynastyOn = dynastyKey !== 'none';
    if (window._applyMapFocus) window._applyMapFocus();

    // “无”：仅底图
    if (dynastyKey === 'none') {
        if (infoLabel) infoLabel.textContent = '未选择朝代';
        return;
    }

    const dynasty = (typeof CHGIS_DYNASTIES !== 'undefined') ? CHGIS_DYNASTIES[dynastyKey] : null;
    if (!dynasty) {
        if (infoLabel) infoLabel.textContent = '未知朝代：' + dynastyKey;
        return;
    }

    if (infoLabel) infoLabel.textContent = '加载中...';

    // 疆域边界：本地 CHGIS_BORDERS 已含全部 18 朝
    const borderFeature = (typeof CHGIS_BORDERS !== 'undefined') ? CHGIS_BORDERS[dynastyKey] : null;
    if (borderFeature) {
        try {
            currentDynastyLayer = L.geoJSON(borderFeature, {
                style: (feature) => {
                    const c = (feature && feature.properties && feature.properties.color) || dynasty.color || '#c9a96e';
                    return { color: c, weight: 2, fillColor: c, fillOpacity: 0.12 };
                }
            }).addTo(chgisMap);
        } catch (e) {
            console.error('[switchDynasty] 边界渲染失败', e);
        }
    }

    // 添加都城标记（CHGIS_CAPITALS 按朝代键取）
    const capitalKeys = DYNASTY_CAPITALS[dynastyKey] || [];
    const capitals = (typeof CHGIS_CAPITALS !== 'undefined')
        ? capitalKeys.map(k => CHGIS_CAPITALS[k]).filter(Boolean)
        : [];
    capitals.forEach(cap => {
        if (cap.lat && cap.lng) {
            const marker = L.marker([cap.lat, cap.lng], {
                icon: L.divIcon({
                    className: 'capital-marker',
                    html: `<div style="background:var(--accent);width:12px;height:12px;border-radius:50%;border:2px solid #fff;"></div>`,
                    iconSize: [12, 12],
                    iconAnchor: [6, 6]
                })
            }).addTo(chgisMap);
            marker.bindPopup(`
                <strong>${cap.name}</strong><br>
                <span style="font-size:11px;color:#666;">今${cap.modern || '位置不详'}</span>
                ${cap.period ? `<br><span style="font-size:11px;color:#999;">${cap.period}</span>` : ''}
            `);
            markerLayers.push(marker);
        }
    });

    // 信息标签与视野（隐藏容器/无效中心时跳过飞行，否则 flyTo 在动画每帧抛 Invalid LatLng NaN）
    const capNames = capitals.map(c => c.name).join('、');
    if (infoLabel) infoLabel.textContent = `${dynasty.name}（${dynasty.period}）` + (capNames ? ` · 都城：${capNames}` : '');
    const ctr = dynasty.center;
    if (Array.isArray(ctr) && Number.isFinite(ctr[0]) && Number.isFinite(ctr[1]) && chgisMap.getContainer().clientHeight > 0) {
        chgisMap.flyTo([ctr[1], ctr[0]], dynasty.zoom || 6, { duration: 1.2 });
    } else if (currentDynastyLayer) {
        try {
            const b = currentDynastyLayer.getBounds();
            if (b.isValid() && chgisMap.getContainer().clientHeight > 0) chgisMap.fitBounds(b.pad(0.1));
        } catch (e) { /* 隐藏容器下 fitBounds 同样不可用，静默跳过 */ }
    }
}

function updateMapMarkers() {
    if (!chgisMap) return;
    // 清除旧标记（保留都城）
    markerLayers.forEach(l => chgisMap.removeLayer(l));
    markerLayers = [];
}

function searchMapPlace() {
    const input = document.getElementById('mapPlaceInput');
    const query = input ? input.value.trim() : '';
    if (!query || !chgisMap) return;

    const resultsDiv = document.getElementById('mapSearchResults');
    if (!resultsDiv) return;

    // 在都城中搜索
    const cityResults = [];
    if (typeof CHGIS_CAPITALS !== 'undefined') {
        Object.values(CHGIS_CAPITALS).forEach(cap => {
            if ((cap.name && cap.name.includes(query)) || (cap.modern && cap.modern.includes(query))) {
                cityResults.push({ name: cap.name, modern: cap.modern, lat: cap.lat, lng: cap.lng, dynasty: cap.dynasty, type: '都城' });
            }
        });
    }

    // 在 places.js 中搜索
    const placeResults = [];
    if (PLACES_DB) {
        PLACES_DB.forEach(place => {
            if ((place.ancient && place.ancient.includes(query)) || (place.modern && place.modern.includes(query))) {
                placeResults.push({ name: place.ancient, modern: place.modern, lat: place.lat, lng: place.lng, dynasty: place.dynasty, type: place.type, notes: place.notes });
            }
        });
    }

    const allResults = [...cityResults, ...placeResults];

    if (allResults.length === 0) {
        resultsDiv.innerHTML = '<p style="color:var(--text-muted)">未找到相关地点</p>';
        return;
    }

    resultsDiv.innerHTML = allResults.slice(0, 20).map(r => {
        const hasCoords = r.lat && r.lng;
        const name = r.name || '';
        const modern = r.modern || '';
        return `
            <div class="map-result-item" ${hasCoords ? `onclick="flyToLocation(${r.lng}, ${r.lat}, 10)"` : ''}
                style="${hasCoords ? 'cursor:pointer;' : ''}">
                <div class="map-result-name">${name} ${modern ? `<span style="font-size:11px;color:var(--text-muted);">（今${modern}）</span>` : ''}</div>
                <div class="map-result-info">${r.dynasty || ''} ${r.type || r.notes || ''}</div>
            </div>
        `;
    }).join('');
}

function flyToLocation(lng, lat, zoom) {
    if (!chgisMap) return;
    chgisMap.flyTo([lat, lng], zoom || 10, { duration: 1.5 });
}

// ── 生卒年 ↔ 朝代图层联动（任务3）────────────────────────
// CBDB 朝代名 → CHGIS 图层键（名称歧义时年份优先，名称仅兜底）
const CBDB_DYNASTY_NAME_TO_KEY = {
    '夏': 'xia', '商': 'shang',
    '西周': 'zhou_west', '周': 'zhou_west', '东周': 'zhou_east', '春秋': 'zhou_east', '战国': 'zhou_east',
    '秦': 'qin', '西汉': 'han_west', '汉': 'han_west', '东汉': 'han_east',
    '曹魏': 'wei', '魏': 'wei', '蜀汉': 'shu', '蜀': 'shu', '孙吴': 'wu', '吴': 'wu',
    '西晋': 'jin_west', '东晋': 'jin_east', '晋': 'jin_west', '南北朝': 'southern_northern',
    '隋': 'sui', '唐': 'tang', '五代': 'five_dynasties', '五代十国': 'five_dynasties',
    '北宋': 'song_north', '宋': 'song_north', '南宋': 'song_south',
    '元': 'yuan', '明': 'ming', '清': 'qing'
};

function _parseDynastyPeriod(period) {
    // "约前2070—前1600" | "前206—公元8" | "25—220" | "618—907" → {from, to}（天文纪年，无 0 年误差可忽略）
    if (!period) return null;
    const parts = period.replace(/约|公?元|\s/g, '').split(/[—–～~-]/);
    if (parts.length < 2) return null;
    const parse = s => {
        const neg = s.indexOf('前') === 0;
        const n = parseInt(s.replace('前', ''), 10);
        return isNaN(n) ? null : (neg ? -n : n);
    };
    const a = parse(parts[0]), b = parse(parts[1]);
    if (a === null || b === null) return null;
    return { from: Math.min(a, b), to: Math.max(a, b) };
}

let _dynastyYearTable = null;
function dynastyYearTable() {
    if (_dynastyYearTable) return _dynastyYearTable;
    _dynastyYearTable = [];
    if (typeof CHGIS_DYNASTIES === 'undefined') return _dynastyYearTable;
    Object.keys(CHGIS_DYNASTIES).forEach(key => {
        const d = CHGIS_DYNASTIES[key];
        const r = _parseDynastyPeriod(d.period);
        if (r) _dynastyYearTable.push({ key, name: d.name, from: r.from, to: r.to, span: r.to - r.from });
    });
    return _dynastyYearTable;
}

function dynastyKeyForYear(year) {
    if (!year || year < -2100 || year > 2026) return null;
    // 命中多个区间时取 from 最大者（新朝建立之年归新朝：618→唐、907→五代、1127→南宋）；
    // from 相同再比 span 最小
    let best = null;
    dynastyYearTable().forEach(d => {
        if (year >= d.from && year <= d.to) {
            if (!best || d.from > best.from || (d.from === best.from && d.span < best.span)) best = d;
        }
    });
    return best ? best.key : null;
}

function autoSwitchDynastyByYear(year, dynastyName, preferName) {
    let key = null;
    if (preferName && dynastyName) key = CBDB_DYNASTY_NAME_TO_KEY[dynastyName] || null;
    if (!key) key = dynastyKeyForYear(year);
    if (!key && dynastyName) key = CBDB_DYNASTY_NAME_TO_KEY[dynastyName] || null;
    if (!key) return;
    const cur = document.querySelector('.dynasty-btn.active');
    if (cur && cur.dataset.dynasty === key) return;
    switchDynasty(key);
    if (typeof CHGIS_DYNASTIES !== 'undefined' && CHGIS_DYNASTIES[key]) {
        showToast(`朝代图层已联动：${CHGIS_DYNASTIES[key].name}（${CHGIS_DYNASTIES[key].period}）`, 'info', 2600);
    }
}

// ── 地图 → CBDB 反查（任务2）────────────────────────────
let _cbdbRevPin = null;

function cbdbAddReverseControl() {
    const ctl = L.control({ position: 'bottomleft' });
    ctl.onAdd = () => {
        const div = L.DomUtil.create('div', 'cbdb-map-revctl');
        div.innerHTML = '<span class="cbdb-map-chip" id="cbdbRevChip" title="开启后点击地图任意位置，反查最近的 CBDB 地名，点地名载入相关人物">⌖ 点图反查</span>';
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        div.querySelector('#cbdbRevChip').onclick = () => cbdbToggleReverse();
        return div;
    };
    ctl.addTo(chgisMap);
}

function cbdbToggleReverse() {
    window._cbdbReverseOn = !window._cbdbReverseOn;
    const chip = document.getElementById('cbdbRevChip');
    if (chip) chip.classList.toggle('active', !!window._cbdbReverseOn);
    if (chgisMap) chgisMap.getContainer().classList.toggle('cbdb-rev-on', !!window._cbdbReverseOn);
    if (!window._cbdbReverseOn) cbdbClearRevPin();
    showToast(window._cbdbReverseOn ? '反查已开启：点击地图任意位置，找附近 CBDB 地名' : '反查已关闭', 'info', 2200);
}

function cbdbClearRevPin() {
    if (_cbdbRevPin && chgisMap) { chgisMap.removeLayer(_cbdbRevPin); _cbdbRevPin = null; }
}

async function cbdbMapClickReverse(e) {
    if (!window._cbdbReverseOn) return;
    const t = e.originalEvent && e.originalEvent.target;
    if (t && (t.closest('.leaflet-marker-icon') || t.closest('.leaflet-popup') || t.closest('.leaflet-control-container'))) return;
    cbdbClearRevPin();
    const seq = (window._cbdbRevSeq = (window._cbdbRevSeq || 0) + 1);  // 竞态令牌：慢响应不得覆盖新点击的弹窗
    const lat = e.latlng.lat, lng = e.latlng.lng;
    const pinIcon = L.divIcon({
        className: 'cbdb-rev-pin',
        html: '<div class="cbdb-rev-dot"></div>',
        iconSize: [14, 14], iconAnchor: [7, 7], popupAnchor: [0, -10]
    });
    _cbdbRevPin = L.marker([lat, lng], { icon: pinIcon, bubblingMouseEvents: false }).addTo(chgisMap);
    _cbdbRevPin.bindPopup('<div class="cbdb-map-popup"><div class="cbdb-map-popup-line">正在查询 CBDB 地名…</div></div>', { maxWidth: 300 }).openPopup();
    const alive = () => seq === window._cbdbRevSeq && _cbdbRevPin;
    const failPopup = msg => { if (alive()) _cbdbRevPin.setPopupContent(`<div class="cbdb-map-popup"><div class="cbdb-map-popup-line" style="color:#d98a8a">${escapeHtml(msg)}</div></div>`); };
    try {
        const res = await fetch(`/api/cbdb/places/nearest?x=${lng.toFixed(4)}&y=${lat.toFixed(4)}`);
        if (!alive()) return;
        if (!res.ok) {
            let msg = `HTTP ${res.status}`;
            try { const ed = await res.json(); if (ed.error) msg = ed.error; } catch (_) {}
            failPopup(msg);
            return;
        }
        const data = await res.json();
        if (!alive()) return;
        if (data.error) { failPopup(data.error); return; }
        if (!Array.isArray(data) || !data.length) {
            _cbdbRevPin.setPopupContent('<div class="cbdb-map-popup"><div class="cbdb-map-popup-line">100km 内没有 CBDB 地名记录</div></div>');
            return;
        }
        window._cbdbRevCache = {};
        const rows = data.map(p => {
            window._cbdbRevCache[p.addr_id] = p;
            const life = (p.firstyear || p.lastyear) ? `${p.firstyear || '?'}–${p.lastyear || '?'}` : '存续不详';
            const same = p.same_coord_count > 1 ? ` · 含同址${p.same_coord_count}条` : '';
            return `<a class="cbdb-map-popup-person" onclick="cbdbReverseDig(${p.addr_id}, ${p.x_coord}, ${p.y_coord}, ${p.firstyear || 0}, ${p.lastyear || 0})">`
                + `${escapeHtml(p.name_chn)}<span>${cbdbAdminTypeLabel(p.admin_type)} · ${p.dist_km}km${same} · ${life}</span></a>`;
        }).join('');
        _cbdbRevPin.setPopupContent(`<div class="cbdb-map-popup">
            <div class="cbdb-map-popup-name">附近 CBDB 地名</div>
            <div class="cbdb-map-popup-line">点任一地名将相关人物载入 CBDB 列表</div>
            <div class="cbdb-map-popup-list">${rows}</div></div>`);
        _cbdbRevPin.openPopup();
    } catch (err) {
        failPopup('查询失败：' + err.message);
    }
}

// 反查结果 → CBDB 人物列表（闭环：地图挖人），并按地名存续期中段联动朝代图层
async function cbdbReverseDig(addrId, x, y, fy, ly) {
    const place = (window._cbdbRevCache || {})[addrId] || {};
    cbdbClearRevPin();
    window._cbdbPlaceCache = window._cbdbPlaceCache || {};
    window._cbdbPlaceCache[addrId] = { name_chn: place.name_chn || ('地名 #' + addrId), x_coord: x, y_coord: y };
    const mid = (fy > 0 && ly > 0) ? Math.round((fy + ly) / 2) : (fy > 0 ? fy : ly);
    // 先切页签：autoSwitch 的 flyTo 若在可见地图上起跳、随后容器被隐藏，
    // Leaflet 在 0 尺寸容器上做动画会每帧抛 Invalid LatLng NaN
    switchTab('cbdb');
    autoSwitchDynastyByYear(mid, null);
    await loadPlacePersons(addrId, true);
}

// ── 史学工具 ───────────────────────────────────────────
function initToolTabs() {
    // 工具标签页切换（进入 tools 页时调用，防止重复绑定）
    if (initToolTabs._bound) return;
    initToolTabs._bound = true;
    document.querySelectorAll('.tool-nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tool = btn.dataset.tool;
            document.querySelectorAll('.tool-nav-btn').forEach(b => b.classList.toggle('active', b === btn));
            document.querySelectorAll('.tool-panel').forEach(p => {
                p.classList.toggle('active', p.id === 'tool-' + tool);
            });
        });
    });
}

function switchEraMode(mode) {
    // 年号换算模式切换（mode 与 HTML data-mode 一致：era-to-year / year-to-era）
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    const eraPanel = document.getElementById('era-to-year-panel');
    const yearPanel = document.getElementById('year-to-era-panel');
    if (mode === 'era-to-year') {
        if (eraPanel) eraPanel.style.display = '';
        if (yearPanel) yearPanel.style.display = 'none';
    } else {
        if (eraPanel) eraPanel.style.display = 'none';
        if (yearPanel) yearPanel.style.display = '';
    }
}

function filterEraByDynasty() {
    // 朝代筛选：作用于当前已渲染的年号结果卡片（HTML 里 onchange 不传参）
    const select = document.getElementById('eraDynastySelect');
    const container = document.getElementById('eraResults');
    if (!select || !container) return;
    const dynasty = select.value;
    container.querySelectorAll('.result-card').forEach(card => {
        const badge = card.querySelector('.result-card-badge');
        const match = !dynasty || (badge && badge.textContent.trim() === dynasty);
        card.style.display = match ? '' : 'none';
    });
}

function searchEra() {
    const input = document.getElementById('eraNameInput');
    const container = document.getElementById('eraResults');
    if (!input || !container) return;
    const query = input.value.trim();
    if (!query) return;

    const eras = ERA_NAMES_DB || [];
    const results = eras.filter(e => e.era && e.era.includes(query));

    if (results.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted)">未找到相关年号</p>';
        return;
    }

    container.innerHTML = results.map(e => `
        <div class="result-card">
            <div class="result-card-title">${e.era}</div>
            <div class="result-card-body">
                <span class="result-card-badge">${e.dynasty || ''}</span>
                <span class="result-card-badge">公元 ${e.startYear} — ${e.endYear}</span>
            </div>
            ${e.notes ? `<div class="result-card-row"><span class="result-card-label">备注</span><span class="result-card-value">${e.notes}</span></div>` : ''}
        </div>
    `).join('');
    container.innerHTML += toolSourcesHtml('era');
    searchEraBook(query, container);
}

async function searchEraBook(query, container) {
    try {
        const d = await (await fetch('/api/tools/era/book?q=' + encodeURIComponent(query))).json();
        if (!d.ok || !d.items || !d.items.length) return;
        const items = d.items.slice(0, 6);
        const bookHtml = '<div class="era-book-block">' +
            '<div class="era-book-title">📖 原书考证 · 李崇智《中国历代年号考》</div>' +
            items.map(it => {
                const span = it.year_span ? ('<span class="result-card-badge">' + escapeHtml(it.year_span) + '</span>') : '';
                return '<div class="result-card era-book-item">' +
                    '<div class="result-card-title">' + escapeHtml((it.eras && it.eras.length ? it.eras.join(' / ') : it.ruler) || '') +
                    ' <span style="font-size:12px;color:var(--text-muted)">' + escapeHtml(it.ruler || '') + '</span></div>' +
                    '<div class="result-card-body">' + span + '<span class="result-card-badge">书页 ' + it.page + '</span></div>' +
                    (it.note ? '<div class="result-card-row"><span class="result-card-label">按语</span><span class="result-card-value">' + escapeHtml(it.note.slice(0, 220)) + '</span></div>' : '') +
                '</div>';
            }).join('') +
            (d.total > 6 ? '<div class="era-book-more">共 ' + d.total + ' 条，检索词再精确些可收窄</div>' : '') +
        '</div>';
        container.insertAdjacentHTML('beforeend', bookHtml);
    } catch (e) { /* 原书块失败不影响主结果 */ }
}

function searchYear() {
    const yearInput = document.getElementById('yearInput');
    const container = document.getElementById('yearResults');
    if (!yearInput || !container) return;

    const year = parseInt(yearInput.value);
    if (!year || isNaN(year)) {
        container.innerHTML = '<p style="color:var(--text-muted)">请输入有效的公元年份（1—1912）</p>';
        return;
    }

    // 使用内置年号数据
    const eras = ERA_NAMES_DB || [];
    const matches = [];

    eras.forEach(e => {
        if (year >= e.startYear && year <= e.endYear) {
            const nth = year - e.startYear + 1;
            matches.push({ ...e, nth });
        }
    });

    if (matches.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted)">该年份不在数据库范围内（唐—清）</p>';
        return;
    }

    container.innerHTML = matches.map(e => `
        <div class="result-card">
            <div class="result-card-title">${e.era}${e.nth}年</div>
            <div class="result-card-body">
                <span class="result-card-badge">第${e.nth} 年</span>
                <span class="result-card-badge">${e.dynasty}</span>
                <span class="result-card-badge">公元 ${e.startYear} — ${e.endYear}</span>
            </div>
            ${e.notes ? `<div class="result-card-row"><span class="result-card-label">备注</span><span class="result-card-value">${e.notes}</span></div>` : ''}
        </div>
    `).join('');
    searchYearBook(year, container);
}

async function searchYearBook(year, container) {
    try {
        const d = await (await fetch('/api/tools/era/book?q=' + year)).json();
        if (!d.ok || !d.items || !d.items.length) return;
        const items = d.items.slice(0, 6);
        container.insertAdjacentHTML('beforeend', '<div class="era-book-block">' +
            '<div class="era-book-title">📖 原书考证 · 李崇智《中国历代年号考》</div>' +
            items.map(it => {
                const span = it.year_span ? ('<span class="result-card-badge">' + escapeHtml(it.year_span) + '</span>') : '';
                return '<div class="result-card era-book-item">' +
                    '<div class="result-card-title">' + escapeHtml((it.eras && it.eras.length ? it.eras.join(' / ') : it.ruler) || '') +
                    ' <span style="font-size:12px;color:var(--text-muted)">' + escapeHtml(it.ruler || '') + '</span></div>' +
                    '<div class="result-card-body">' + span + '<span class="result-card-badge">书页 ' + it.page + '</span></div>' +
                    (it.note ? '<div class="result-card-row"><span class="result-card-label">按语</span><span class="result-card-value">' + escapeHtml(it.note.slice(0, 220)) + '</span></div>' : '') +
                '</div>';
            }).join('') +
        '</div>');
    } catch (e) { /* 原书块失败不影响主结果 */ }
}

function searchOfficial() {
    const input = document.getElementById('officialInput');
    const container = document.getElementById('officialResults');
    if (!input || !container) return;
    const query = input.value.trim();
    if (!query) return;

    const officials = OFFICIALS_DB || [];
    const results = officials.filter(o =>
        (o.name && o.name.includes(query)) ||
        (o.duties && o.duties.includes(query))
    );

    if (results.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted)">未找到相关职官</p>';
        return;
    }

    container.innerHTML = results.map(o => `
        <div class="result-card">
            <div class="result-card-title">${o.name}</div>
            <div class="result-card-body">
                <span class="result-card-badge">${o.dynasty || ''}</span>
                <span class="result-card-badge">${o.rank || ''}</span>
            </div>
            ${o.duties ? `<div class="result-card-row"><span class="result-card-label">职掌</span><span class="result-card-value">${o.duties}</span></div>` : ''}
            ${o.notes ? `<div class="result-card-row"><span class="result-card-label">备注</span><span class="result-card-value">${o.notes}</span></div>` : ''}
        </div>
    `).join('');
    container.innerHTML += toolSourcesHtml('official');
}

function searchPlace() {
    const input = document.getElementById('placeInput');
    const container = document.getElementById('placeResults');
    if (!input || !container) return;
    const query = input.value.trim();
    if (!query) return;

    const places = PLACES_DB || [];
    const results = places.filter(p =>
        (p.ancient && p.ancient.includes(query)) ||
        (p.modern && p.modern.includes(query))
    );

    if (results.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted)">未找到相关地名</p>';
        return;
    }

    container.innerHTML = results.map(p => `
        <div class="result-card">
            <div class="result-card-title">${p.ancient}（今${p.modern}）</div>
            <div class="result-card-body">
                <span class="result-card-badge">${p.dynasty || ''}</span>
                <span class="result-card-badge">${p.province || p.type || ''}</span>
            </div>
            ${p.notes ? `<div class="result-card-row"><span class="result-card-label">备注</span><span class="result-card-value">${p.notes}</span></div>` : ''}
            ${p.lat ? `<div class="result-card-row"><span class="result-card-label">坐标</span><span class="result-card-value">${p.lat}, ${p.lng}</span></div>` : ''}
        </div>
    `).join('');
    container.innerHTML += toolSourcesHtml('place');
}

// ── 史学工具溯源层: 数据来源声明 + 在线核查路径 ──
const TOOL_SOURCES = {
    taboo: {
        title: '避讳',
        book: '王建《史讳辞典》（中华书局）',
        online: [
            { label: '🏛️ CBDB 查该帝王', act: "cbdb" },
            { label: '📖 汉典查字源', url: 'https://www.zdic.net/' },
        ],
        note: '本库为常用帝讳简表；具体讳例以原书及出土文献为准'
    },
    phonology: {
        title: '音韵',
        book: '陈彭年等《广韵》（泽存堂本）',
        online: [
            { label: '🎵 韵典网·广韵查询', url: 'https://ytenx.org/' },
            { label: '📖 汉典查该字', url: 'https://www.zdic.net/' },
        ],
        note: '反切、声类、韵部据《广韵》；中古音拟音各家不同，本库不录'
    },
    era: {
        title: '年号',
        book: '李崇智《中国历代年号考》（中华书局修订本）',
        online: [
            { label: '🏛️ CBDB 年号/帝王核查', act: "cbdb" },
            { label: '🌐 维基年号列表', url: 'https://zh.wikipedia.org/wiki/中国年号列表' },
        ],
        note: '年号起讫换算用公历年末惯例，跨公元年份以实年核之'
    },
    official: {
        title: '职官',
        book: '吕宗力《中国历代官制大辞典》（商务印书馆）',
        online: [
            { label: '🏛️ CBDB 职官检索（站内联动）', act: "cbdb_office" },
        ],
        note: '职名释义为通制概述；具体朝代沿革请以该朝会要/职官志为准'
    },
    place: {
        title: '地名',
        book: '谭其骧主编《中国历史地图集》（地图出版社）',
        online: [
            { label: '🗺️ CHGIS 地图核查（站内联动）', act: "map" },
            { label: '🏛️ CBDB 地名检索（站内联动）', act: "cbdb_place" },
        ],
        note: '今地对照为大体方位；沿革细节请以 CHGIS 及原书图幅为准'
    },
    version: {
        title: '版本',
        book: '《中国古籍善本书目》（上海古籍出版社）',
        online: [
            { label: '📚 国家图书馆 OPAC 查善本', url: 'http://opac.nlc.cn/' },
            { label: '📖 中国哲学书电子化计划', url: 'https://ctext.org/zh' },
        ],
        note: '版本信息为通行要目；善本馆藏以国图 OPAC 及各馆藏目为准'
    },
};

function toolSourcesHtml(key) {
    const cfg = TOOL_SOURCES[key];
    if (!cfg) return '';
    const btns = (cfg.online || []).map((o, i) => {
        if (o.act === 'cbdb') return '<button class="tool-src-btn" onclick="toolSrcGoto(\'' + key + '\',\'cbdb\')">' + o.label + '</button>';
        if (o.act === 'cbdb_office') return '<button class="tool-src-btn" onclick="toolSrcGoto(\'' + key + '\',\'cbdb_office\')">' + o.label + '</button>';
        if (o.act === 'cbdb_place') return '<button class="tool-src-btn" onclick="toolSrcGoto(\'' + key + '\',\'cbdb_place\')">' + o.label + '</button>';
        if (o.act === 'map') return '<button class="tool-src-btn" onclick="toolSrcGoto(\'' + key + '\',\'map\')">' + o.label + '</button>';
        return '<a class="tool-src-btn" href="' + o.url + '" target="_blank" rel="noopener">' + o.label + '</a>';
    }).join('');
    return '<div class="tool-sources"><div class="tool-sources-head">📎 来源与核查</div>' +
        '<div class="tool-sources-book">本库依据：' + cfg.book + '</div>' +
        '<div class="tool-sources-note">' + cfg.note + '</div>' +
        '<div class="tool-sources-btns">' + btns + '</div></div>';
}
window.toolSourcesHtml = toolSourcesHtml;

function toolSrcGoto(toolKey, target) {
    // 站内联动: 把当前搜索词带过去
    const inputMap = { taboo: 'tabooInput', phonology: 'phonologyInput', era: 'eraNameInput', official: 'officialInput', place: 'placeInput', version: 'versionInput' };
    const q = (document.getElementById(inputMap[toolKey]) || {}).value || '';
    if (target === 'cbdb' || target === 'cbdb_office' || target === 'cbdb_place') {
        switchTab('cbdb');
        if (target === 'cbdb_office' && typeof switchCBDBType === 'function') switchCBDBType('office');
        if (target === 'cbdb_place' && typeof switchCBDBType === 'function') switchCBDBType('place');
        if (target === 'cbdb' && typeof switchCBDBType === 'function') switchCBDBType('person');
        const inp = document.getElementById('cbdbSearchInput');
        if (inp && q) inp.value = q;
        return;
    }
    if (target === 'map') {
        switchTab('map');
        const mi = document.querySelector('#placeInput, .map-search-input');
        if (mi && q) { mi.value = q; }
        return;
    }
}
window.toolSrcGoto = toolSrcGoto;

function searchTaboo() {
    const input = document.getElementById('tabooInput');
    const container = document.getElementById('tabooResults');
    if (!input || !container) return;
    const query = input.value.trim();
    if (!query) return;

    const taboos = TABOO_DB || [];
    const results = taboos.filter(t =>
        (t.name && t.name.includes(query)) ||
        (t.tabooChars && t.tabooChars.includes(query)) ||
        (t.alternatives && t.alternatives.includes(query))
    );

    if (results.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted)">未找到相关避讳记录</p>';
        return;
    }

    container.innerHTML = results.map(t => {
        const tabooList = t.tabooChars.split(',').map(c => `<span class="taboo-highlight">${c.trim()}</span>`).join('');
        const altList = t.alternatives.split('/').map(a => `<span class="taboo-alt">${a.trim()}</span>`).join('');
        return `
            <div class="result-card">
                <div class="result-card-title">${t.name}</div>
                <div class="result-card-body">
                    <span class="result-card-badge">${t.dynasty || ''}</span>
                    <span class="result-card-badge">${t.emperor || ''}</span>
                </div>
                <div class="result-card-row"><span class="result-card-label">避讳字</span><span class="result-card-value">${tabooList}</span></div>
                <div class="result-card-row"><span class="result-card-label">替代字</span><span class="result-card-value">${altList}</span></div>
                ${t.notes ? `<div class="result-card-row"><span class="result-card-label">实例</span><span class="result-card-value">${t.notes}</span></div>` : ''}
            </div>
        `;
    }).join('');
    container.innerHTML += toolSourcesHtml('taboo');
}

function searchPhonology() {
    const input = document.getElementById('phonologyInput');
    const container = document.getElementById('phonologyResults');
    if (!input || !container) return;
    const query = input.value.trim();
    if (!query) return;

    const chars = query.split('');
    const data = PHONOLOGY_DB || [];

    const results = chars.map(ch => {
        const entry = data.find(e => e.char === ch);
        if (!entry) return { char: ch, found: false };
        return { char: ch, found: true, ...entry };
    });

    container.innerHTML = results.map(r => {
        if (!r.found) {
            return `<div class="result-card"><div class="result-card-title">「${r.char}」</div><p style="color:var(--text-muted)">未找到「${r.char}」的中古音记录。数据库收录约120个常用字，可尝试：天、地、人、王、大、小、上、下、中、东、西、南、北 等</p></div>`;
        }
        return `
            <div class="result-card">
                <div class="result-card-title">${r.char}</div>
                <div class="result-card-body">
                    <span class="result-card-badge">${r.dynasty || '中古'}</span>
                </div>
                <table class="phonology-table">
                    <thead><tr><th>声母</th><th>今音</th><th>反切</th><th>韵部</th><th>声调</th></tr></thead>
                    <tbody><tr>
                        <td>${r.initials || '—'}</td>
                        <td>${r.pinyin || '—'}</td>
                        <td>${r.fanqie || '—'}</td>
                        <td>${r.rhyme || '—'}</td>
                        <td>${r.tone || '—'}</td>
                    </tr></tbody>
                </table>
                ${r.notes ? `<div class="result-card-row"><span class="result-card-label">备注</span><span class="result-card-value">${r.notes}</span></div>` : ''}
            </div>
        `;
    }).join('');
    container.innerHTML += toolSourcesHtml('phonology');
}

function searchVersion() {
    const input = document.getElementById('versionInput');
    const container = document.getElementById('versionResults');
    if (!input || !container) return;
    const query = input.value.trim();
    if (!query) return;

    const versions = VERSIONS_DB || [];
    const results = versions.filter(v =>
        (v.title && v.title.includes(query)) ||
        (v.author && v.author.includes(query))
    );

    if (results.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted)">未找到相关版本记录</p>';
        return;
    }

    container.innerHTML = results.map(v => `
        <div class="result-card">
            <div class="result-card-title">${v.title}</div>
            <div class="result-card-body">
                <span class="result-card-badge">${v.author || ''}</span>
                <span class="result-card-badge">${v.dynasty || ''}</span>
                <span class="result-card-badge">${v.category || ''}</span>
            </div>
            ${v.versions ? v.versions.map(ver => `
                <div class="version-info-row">
                    <span class="version-book-title">${ver.title || ''}</span>
                    <span class="version-info">${ver.name}${ver.notes ? ' · ' + ver.notes : ''}</span>
                </div>
            `).join('') : ''}
        </div>
    `).join('');
    container.innerHTML += toolSourcesHtml('version');
}

// ── 初始化 ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    checkStatus();
    checkAppUpdate(false);
    injectPluginTabs();
    // 仪表盘为默认页时直接锁滚动(不经过 switchTab)
    const dash = document.getElementById('dashboard');
    if (dash && dash.classList.contains('active')) {
        document.documentElement.classList.add('dash-fit');
        document.body.classList.add('dash-fit');
    }

    // 定期检查状态
    setInterval(checkStatus, 60000);

    // 绑定搜索
    const searchInput = document.getElementById('obsidianSearchInput');
    if (searchInput) searchInput.addEventListener('keypress', e => { if (e.key === 'Enter') globalSearch(); });

    // 绑定回车键
    const aiInput = document.getElementById('aiChatInput');
    if (aiInput) aiInput.addEventListener('keypress', e => { if (e.key === 'Enter') sendAIChat(); });

    const cbdbInput = document.getElementById('cbdbSearchInput');
    if (cbdbInput) cbdbInput.addEventListener('keypress', e => { if (e.key === 'Enter') searchCBDB(); });

    // 加载仪表盘
    loadDashboard();
});


// ===== CBDB AI 自然语言检索 =====

const CBDB_AI_PROMPT = `你是六月息（CBDB 中国历代人物传记资料库）的检索助手。用户用自然语言描述查询需求，你输出一个 JSON 对象指定检索参数。

可用检索类型及参数：

1. person（人名搜索）
   {"tab":"person","params":{"name":"姓名","dynasty":"朝代中文名","gender":"0"或"1","birth_from":数字,"birth_to":数字,"death_from":数字,"death_to":数字,"index_from":数字,"index_to":数字}}

2. office（官名搜索）
   {"tab":"office","params":{"q":"官名关键词","category":"门类（可省略）"}}

3. place（地名搜索）
   {"tab":"place","params":{"q":"地名","admin_type":"府/州/县/路/省/道/军/郡（可省略）","from_year":数字,"to_year":数字}}

4. entry（入仕方式）
   {"tab":"entry","params":{"q":"入仕方式关键词"}}

5. status（社会区分）
   {"tab":"status","params":{"q":"社会区分关键词"}}

6. text（著作检索）
   {"tab":"text","params":{"q":"著作关键词"}}

7. year（某年在世的人物）
   {"tab":"year","params":{"year":数字,"dynasty":"朝代中文名（可省略）","entry":"入仕方式关键词（可省略，如 进士）"}}

8. pair（两人关系）
   {"tab":"pair","params":{"a":"人名A","b":"人名B"}}

9. social（某人的社会关系/交游/门生故吏）
   {"tab":"social","params":{"name":"姓名"}}

10. kin（某人的亲属/家族/五服）
   {"tab":"kin","params":{"name":"姓名"}}

11. entry_range（某年号/时期通过某方式入仕的人物）
   {"tab":"entry_range","params":{"entry":"入仕关键词","from_year":起始年,"to_year":结束年}}
   用于"XX年间通过YY入仕/做官/中举/及第"。入仕年份必须落在 [from_year, to_year]。

常用年号起止年（换算后填入 from_year/to_year）：
乾隆1736-1795 雍正1723-1735 康熙1662-1722 嘉庆1796-1820 道光1821-1850 咸丰1851-1861 同治1862-1874 光绪1875-1908
洪武1368-1398 永乐1403-1424 嘉靖1522-1566 万历1573-1620
太平兴国976-984 景德1004-1007 天圣1023-1032 熙宁1068-1077 元祐1086-1094 政和1111-1118 绍兴1131-1162 嘉定1208-1224
贞观627-649 开元713-741 天宝742-756
太和477-499 正始504-508（北魏）
表中查不到的年号按你所知换算；确实不知道就不猜，在 explanation 里向用户说明。

规则：
- 只输出 JSON，不要输出任何其他文字
- 额外可选字段： "action":"detail"（用户想看某人详情/人生轨迹/履历时设置）； "explanation":"一句话向用户解释你的理解"
- 用户说"XX的人生轨迹""XX的经历""XX在N-M岁"时：tab用person，name填XX，action设detail，其他参数全部留空（详情页会显示完整履历）
- "XX的社会关系""XX和谁交游""XX的门生"→ tab用social；"XX的亲属""XX的家族""XX的五服"→ tab用kin
- "Y年在世的XX（入仕方式）"（Y是具体数字年份）→ tab用year，year填Y，entry填入仕方式关键词
- 年号/某年间 + 入仕（如"乾隆年间通过武举做官"）→ tab用entry_range，entry填入仕关键词，from_year/to_year填该年号起止。**严禁取"代表年份"**（如"取乾隆中期1750年"）——year 检索只是"某一年在世"，既不等于入仕时间更不是区间，是错误逻辑
- 年龄换算：如"苏轼30-40岁"，苏轼生于1036年，30-40岁≈1066-1076，把换算后年份填入index_from/index_to，并在explanation中说明
- 朝代保留中文名（如"宋""唐""北魏"）
- 不确定的参数不要猜，只输出有把握的`;

async function cbdbAIAssist() {
    const input = document.getElementById('cbdbAIInput');
    const statusEl = document.getElementById('cbdbAIStatus');
    const q = input ? input.value.trim() : '';
    if (!q) return;

    if (statusEl) statusEl.innerHTML = '<span class="cbdb-ai-thinking">&#x1F914; 正在理解你的问题…</span>';

    try {
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: [
                    { role: 'system', content: CBDB_AI_PROMPT },
                    { role: 'user', content: q }
                ]
            })
        });
        const data = await res.json();
        const text = data.response || (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || '';

        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            if (statusEl) statusEl.innerHTML = '<span style="color:var(--danger)">AI 未能理解这个问题，请换个方式描述</span>';
            return;
        }

        let parsed;
        try { parsed = JSON.parse(jsonMatch[0]); } catch (e) {
            if (statusEl) statusEl.innerHTML = '<span style="color:var(--danger)">解析失败，请重试</span>';
            return;
        }

        if (statusEl) {
            const exp = parsed.explanation ? '：' + escapeHtml(parsed.explanation) : '';
            statusEl.innerHTML = '<span class="cbdb-ai-ok">&#x2713;' + exp + '</span>';
        }

        await cbdbAIExecute(parsed);
    } catch (e) {
        if (statusEl) statusEl.innerHTML = '<span style="color:var(--danger)">请求失败: ' + escapeHtml(e.message) + '</span>';
    }
}

async function cbdbAIExecute(parsed) {
    const tab = parsed.tab || 'person';
    const params = parsed.params || {};

    if (tab === 'social') { await cbdbAIShowSocial(params); return; }
    if (tab === 'kin') { await cbdbAIShowKin(params); return; }
    if (tab === 'entry_range') { await cbdbAIShowEntryRange(params); return; }

    switchCBDBType(tab);
    await new Promise(function(r) { return setTimeout(r, 500); });

    if (tab === 'pair') { await cbdbAIExecutePair(params); return; }

    if (parsed.action === 'detail') {
        // Detail mode: search by name only, auto-open first result
        var nameParams = { name: params.name, dynasty: params.dynasty };
        await cbdbAIFillParams(tab, nameParams);
        searchCBDB();
        setTimeout(function() { cbdbAIOpenFirstResult(); }, 3000);
    } else {
        await cbdbAIFillParams(tab, params);
        searchCBDB();
    }
}

async function cbdbAIFillParams(tab, params) {
    function setVal(id, val) {
        var el = document.getElementById(id);
        if (el && val !== undefined && val !== null && val !== '') el.value = String(val);
    }
    function selectDynasty(dynastyName) {
        if (!dynastyName) return;
        setTimeout(function() {
            var sel = document.getElementById('cbdbDynasty');
            if (!sel) return;
            for (var i = 0; i < sel.options.length; i++) {
                var opt = sel.options[i];
                if (opt.textContent.trim() === dynastyName.trim() || opt.textContent.indexOf(dynastyName) !== -1) {
                    sel.value = opt.value;
                    break;
                }
            }
        }, 600);
    }

    if (tab === 'person') {
        setVal('cbdbSearchInput', params.name);
        setVal('cbdbGender', params.gender);
        setVal('cbdbBirthFrom', params.birth_from);
        setVal('cbdbBirthTo', params.birth_to);
        setVal('cbdbDeathFrom', params.death_from);
        setVal('cbdbDeathTo', params.death_to);
        setVal('cbdbIndexFrom', params.index_from);
        setVal('cbdbIndexTo', params.index_to);
        selectDynasty(params.dynasty);
    } else if (tab === 'office') {
        setVal('cbdbSearchInput', params.q);
        setVal('cbdbOfficeCat', params.category);
    } else if (tab === 'place') {
        setVal('cbdbSearchInput', params.q);
        setVal('cbdbPlaceFrom', params.from_year);
        setVal('cbdbPlaceTo', params.to_year);
        if (params.admin_type) {
            var sel = document.getElementById('cbdbAdminType');
            if (sel) {
                for (var i = 0; i < sel.options.length; i++) {
                    if (sel.options[i].textContent.indexOf(params.admin_type) !== -1) { sel.value = sel.options[i].value; break; }
                }
            }
        }
    } else if (tab === 'year') {
        setVal('cbdbYearInput', params.year);
        selectDynasty(params.dynasty);
        if (params.entry) {
            // 后端支持关键词或代码直传；存进 picker 状态让 searchCBDB 带入请求
            window._cbdbYearEntry = { id: params.entry, label: params.entry };
            var yeInput = document.getElementById('cbdbYearEntry');
            if (yeInput) yeInput.value = params.entry;
        }
    } else if (tab === 'entry' || tab === 'status' || tab === 'text') {
        setVal('cbdbSearchInput', params.q);
    }
}

async function cbdbAIExecutePair(params) {
    if (!params.a || !params.b) { showToast('AI 解析缺少人名', 'warning'); return; }

    async function searchPerson(name) {
        var res = await fetch('/api/cbdb/search?name=' + encodeURIComponent(name));
        var data = await res.json();
        return (Array.isArray(data) && data.length) ? data[0] : null;
    }

    try {
        var results = await Promise.all([searchPerson(params.a), searchPerson(params.b)]);
        var pa = results[0], pb = results[1];
        if (!pa || !pb) { showToast('未找到对应人物，请手动输入', 'warning'); return; }

        window._cbdbPairState = { a: { id: pa.id, label: pa.name_chn || pa.name }, b: { id: pb.id, label: pb.name_chn || pb.name } };
        document.getElementById('cbdbPairA').value = pa.name_chn || pa.name;
        document.getElementById('cbdbPairB').value = pb.name_chn || pb.name;

        runPairQuery();
    } catch (e) {
        showToast('人物查找失败: ' + e.message, 'error');
    }
}

function cbdbAIOpenFirstResult() {
    var results = document.getElementById('cbdbResults');
    if (!results) return;
    var firstName = results.querySelector('.cbdb-name');
    if (firstName) firstName.click();
}

// AI 意图：解析姓名 → 第一人（与 cbdbAIExecutePair 同一策略）
async function cbdbAIResolveFirstPerson(name) {
    var res = await fetch('/api/cbdb/search?name=' + encodeURIComponent(name));
    var data = await res.json();
    return (Array.isArray(data) && data.length) ? data[0] : null;
}

// AI 意图 social：某人的社会关系列表（ASSOC_DATA 全类型，直接出关系对表格）
async function cbdbAIShowSocial(params) {
    if (!params.name) { showToast('AI 解析缺少人名', 'warning'); return; }
    var p = await cbdbAIResolveFirstPerson(params.name);
    if (!p) { showToast('未找到人物：' + params.name, 'warning'); return; }
    var centerName = p.name_chn || p.name;
    var detail = document.getElementById('cbdbDetailPanel');
    if (!detail) return;
    cbdbPushListView();
    showCBDBDetailView();
    window._cbdbListView = { type: 'aiSocial', id: p.id, title: centerName + ' 的社会关系' };
    window._cbdbExport = null;
    detail.innerHTML = renderCBDBBackBar(centerName + ' 的社会关系') +
        '<div class="loading" style="margin:20px auto;display:block"></div>';
    try {
        var res = await fetch('/api/cbdb/person/' + p.id + '/assoc');
        var rels = await res.json();
        var list = Array.isArray(rels) ? rels : [];
        var rows = list.map(function(r) {
            return { a_id: p.id, a_name: centerName, relation: r.relation,
                     b_id: r.id, b_name: r.name_chn, year: r.year, text: r.text_title };
        });
        detail.innerHTML = renderCBDBBackBar(centerName + ' 的社会关系') +
            '<div class="cbdb-subhead">共 ' + list.length + ' 条关系记录（双击人名看详情；想看亲属请用亲属递归）</div>' +
            (list.length ? cbdbRelationsTableHTML(rows, list.length)
                         : '<p style="color:var(--text-muted);padding:12px 0">数据库中未记录此人的社会关系。</p>');
    } catch (e) {
        detail.innerHTML = renderCBDBBackBar(centerName + ' 的社会关系') +
            '<p style="color:var(--danger);">加载失败: ' + escapeHtml(e.message) + '</p>';
    }
}

// AI 意图 kin：某人亲属递归（默认五服参数 4/4/3/1 直接出结果）
async function cbdbAIShowKin(params) {
    if (!params.name) { showToast('AI 解析缺少人名', 'warning'); return; }
    var p = await cbdbAIResolveFirstPerson(params.name);
    if (!p) { showToast('未找到人物：' + params.name, 'warning'); return; }
    loadKinRecursive(p.id, p.name_chn || p.name);
    setTimeout(function() {
        var set = function(id, v) { var el = document.getElementById(id); if (el) el.value = v; };
        set('kinUp', 4); set('kinDown', 4); set('kinCol', 3); set('kinMar', 1);
        runKinRecursive(p.id);
    }, 600);
}

// AI 意图 entry_range：某年号/时期通过某方式入仕的人物（入仕年须落在区间，
// 取"代表年份"再叠加 year 检索是错误逻辑——那查的是"某一年在世"）
async function cbdbAIShowEntryRange(params) {
    if (!params.entry) { showToast('AI 解析缺少入仕方式', 'warning'); return; }
    if (!params.from_year || !params.to_year) { showToast('AI 解析缺少起止年份', 'warning'); return; }
    var res = await fetch('/api/cbdb/entries/resolve?q=' + encodeURIComponent(params.entry));
    var info = await res.json();
    if (info.error) { showToast(info.error, 'warning'); return; }
    switchCBDBType('entry');
    var title = info.name + '（' + params.from_year + '–' + params.to_year + '）';
    // use_index：入仕年多未标（c_year=0），用索引年兜底——否则无年份记录会漏进其他朝代
    loadEntryPersons(info.code, title, { from: params.from_year, to: params.to_year, useIndex: true });
}

// ── 活动足迹统一上报(后端 jsonl 追加) ────────────────
window._logActivity = function (type, label) {
    try {
        fetch('/api/activity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: type, label: String(label || '').slice(0, 100) })
        });
    } catch (e) {}
};

// 顶部全局搜索: Enter 跳到 CBDB 人名检索
(function () {
    const bindTopSearch = () => {
        const gs = document.getElementById('globalSearch');
        if (!gs || gs.dataset.bound) return;
        gs.dataset.bound = '1';
        gs.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            const q = gs.value.trim();
            if (!q) return;
            window._logActivity('search', '顶部搜索：' + q);
            switchTab('cbdb');
            if (window._cbdbType !== 'person') switchCBDBType('person');
            const inp = document.getElementById('cbdbSearchInput');
            if (inp) { inp.value = q; }
            if (typeof searchCBDB === 'function') searchCBDB();
        });
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindTopSearch);
    } else {
        bindTopSearch();
    }
    // 插件 nav 注入: 启动即拉取
    if (typeof loadPluginNav === 'function') loadPluginNav();
if (typeof loadAiModels === 'function') loadAiModels();
})();
