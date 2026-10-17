/* 文献图谱 (litgraph) 插件前端: 导入建图 + ECharts 力导向 + 侧栏题录/跳转 */
(function () {
  let _chart = null;
  let _graph = null;

  const KIND_COLOR = { seed: '#d4af37', ref: '#c0392b', citedby: '#2e5e8c', both: '#7d5ba6', related: '#4a7c59', ext: '#8a8f98' };
  const KIND_LABEL = { seed: '种子', ref: '参考文献', citedby: '引证文献', both: '双向(引证+参考)', related: '相关文献', ext: '扩展节点' };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    }, opts || {}));
    return r.json();
  }

  function renderGraph(graph) {
    _graph = graph;
    const el = document.getElementById('litGraph');
    if (!el || typeof echarts === 'undefined') return;
    if (_chart) { _chart.dispose(); _chart = null; }
    _chart = echarts.init(el, null, { renderer: 'canvas' });
    const deg = {};
    graph.edges.forEach(e => { deg[e.s] = (deg[e.s] || 0) + 1; deg[e.t] = (deg[e.t] || 0) + 1; });
    const cssText = (getComputedStyle(document.body).getPropertyValue('--text') || '#888').trim() || '#888';
    const nodes = graph.nodes.map(nd => ({
      id: nd.id, name: nd.title,
      symbolSize: nd.kind === 'seed' ? 46 : Math.min(40, 14 + 5 * (deg[nd.id] || 1) + (nd.n > 1 ? 6 : 0)),
      itemStyle: { color: KIND_COLOR[nd.kind] || '#999' },
      label: { show: nd.kind === 'seed' || (deg[nd.id] || 0) >= 4,
        fontSize: 11, color: cssText,
        formatter: () => nd.title.length > 16 ? nd.title.slice(0, 16) + '…' : nd.title },
      _nd: nd,
    }));
    const links = graph.edges.map(e => ({
      source: e.s, target: e.t,
      lineStyle: { color: e.dash ? '#9ab3a5' : '#b8b2a4', width: e.dash ? 1 : 1.2,
        curveness: 0.08, type: e.dash ? 'dashed' : 'solid' },
    }));
    // R113: 力导向参数随规模自适应(沿用 CBDB 关系图经验)
    const N = graph.nodes.length;
    const repulsion = N > 120 ? 640 : N > 60 ? 480 : 320;
    const edgeLen = N > 120 ? [70, 160] : [60, 130];
    const friction = N > 60 ? 0.18 : 0.25;
    const gEl = document.getElementById('litGraph');
    if (gEl) gEl.classList.toggle('lit-empty', !N);
    _chart.setOption({
      animationDuration: 400,
      tooltip: {
        formatter: p => {
          if (p.dataType !== 'node') return '';
          const nd = p.data._nd;
          return '<b>' + esc(nd.title) + '</b><br/>' +
            KIND_LABEL[nd.kind] + (nd.year ? ' · ' + esc(nd.year) : '') + '<br/>' +
            esc((nd.authors || []).slice(0, 3).join(', ')) + '<br/>' +
            '<span style="color:#888">' + (nd.oa_id && nd.kind !== 'seed' ? '单击看题录 · 双击再扩一层' : '点击看题录与跳转') + '</span>';
        }
      },
      series: [{
        type: 'graph', layout: 'force', roam: true, draggable: true,
        fitView: true,
        layoutAnimation: N <= 120,
        force: { repulsion: repulsion, edgeLength: edgeLen, gravity: 0.12,
                 friction: friction },
        emphasis: { focus: 'adjacency', lineStyle: { width: 2.6, color: '#8a6d1d' },
          label: { show: true, fontSize: 11,
            formatter: p => { const t = p.data._nd.title; return t.length > 22 ? t.slice(0, 22) + '…' : t; } } },
        data: nodes, links: links,
      }],
    });
    _chart.off('click');
    window.__litChart = _chart; // R113 调试句柄(保留无害)
    _chart.on('click', p => {
      if (p.dataType === 'node') showPanel(p.data._nd, deg);
    });
    // R113b: 力导向跑完后按真实包围盒校正视野(种子节点在视野外问题)
    _chart.off('finished');
    let _fitted = false;
    _chart.on('finished', () => {
      if (_fitted) return;
      _fitted = true;
      try {
        const data2 = _chart.getModel().getSeriesByIndex(0).getData();
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, cnt = 0;
        for (let i = 0; i < data2.count(); i++) {
          const l = data2.getItemLayout(i);
          if (!l) continue;
          const x = (l[0] !== undefined ? l[0] : l.x);
          const y = (l[1] !== undefined ? l[1] : l.y);
          if (isNaN(x) || isNaN(y)) continue;
          if (x < minX) minX = x; if (x > maxX) maxX = x;
          if (y < minY) minY = y; if (y > maxY) maxY = y;
          cnt++;
        }
        if (!cnt) return;
        const W = gEl.clientWidth - 24, H = gEl.clientHeight - 24;
        const bw = Math.max(maxX - minX, 40), bh = Math.max(maxY - minY, 40);
        const zoomFit = Math.min(W / bw, H / bh, 4) * 0.94;
        // graph.center = 视野中央对准的布局坐标点; zoom = 布局→像素缩放
        _chart.setOption({ series: [{
          center: [(minX + maxX) / 2, (minY + maxY) / 2], zoom: zoomFit }] });
      } catch (e) { /* 视野校正失败不阻断渲染 */ }
    });
    // R113: 双击节点直接级联扩展
    _chart.off('dblclick');
    _chart.on('dblclick', p => {
      if (p.dataType !== 'node') return;
      const nd = p.data._nd;
      if (!nd.oa_id) { litToast('该节点无 OpenAlex 标识(可能来自知网导出), 无法扩展'); return; }
      if (nd.kind === 'seed') { litToast('种子节点已全量扩展, 双击其它节点'); return; }
      if (!current || !current.gid) { litToast('请先保存图谱再扩展'); return; }
      expandNode(nd.id, null);
    });
    // 图例胶囊带计数 + 出度/入度统计
    const st = graph.stats || {};
    const cnt = {};
    graph.nodes.forEach(nd => { cnt[nd.kind] = (cnt[nd.kind] || 0) + 1; });
    const lg = document.getElementById('litLegend');
    if (lg) {
      lg.innerHTML = ['seed', 'ref', 'citedby', 'both', 'related', 'ext'].filter(k => cnt[k]).map(k =>
        '<span class="lg"><i style="background:' + KIND_COLOR[k] + '"></i>' + KIND_LABEL[k] +
        ' <b style="color:var(--text)">' + cnt[k] + '</b></span>').join('') +
        (st.n_citedby_total ? '<span style="margin-left:auto">全库被引命中 <b style="color:var(--text)">' +
          st.n_citedby_total + '</b> 篇</span>' : '');
    }
    const stat = document.getElementById('litStats');
    if (stat) {
      stat.textContent = '种子: ' + graph.seed_title + '\n参考文献 ' + st.n_ref +
        ' 篇 · 引证 ' + st.n_citedby + ' 篇' + (st.n_related ? ' · 相关 ' + st.n_related + ' 条' : '') +
        ' · 节点 ' + st.n_nodes + ' · 合并同名 ' + (st.n_merged || 0) + ' 条\n保存于 ' + (graph.ts || '');
    }
  }

  function showPanel(nd, deg) {
    const p = document.getElementById('litPanel');
    if (!p) return;
    p.style.display = 'block';
    const q = encodeURIComponent(nd.title);
    p.innerHTML =
      '<h4>' + esc(nd.title) + '</h4>' +
      '<div class="lit-meta">' +
      '类型: ' + (KIND_LABEL[nd.kind] || nd.kind) + '\n' +
      (nd.authors && nd.authors.length ? '作者: ' + esc(nd.authors.join(', ')) + '\n' : '') +
      (nd.source ? '出处: ' + esc(nd.source) + '\n' : '') +
      (nd.year ? '年份: ' + esc(nd.year) + '\n' : '') +
      (nd.cited_by_count ? '被引数: ' + esc(nd.cited_by_count) + '\n' : '') +
      (nd.doi ? 'DOI: ' + esc(nd.doi) + '\n' : '') +
      '连接度: ' + (deg[nd.id] || 0) + (nd.n > 1 ? '\n同名合并 ×' + nd.n : '') +
      '</div>' +
      (nd.oa_id && nd.kind !== 'seed' && current && current.gid
        ? '<a class="btn lit-ext-btn" data-nid="' + esc(nd.id) + '" style="background:linear-gradient(135deg,#8a93a0,#6e7784);color:#fff;border-color:transparent;font-weight:600">🔍 以此为种子再扩一层</a>' : '') +
      (nd.oa_id ? '<a class="btn" target="_blank" href="https://openalex.org/' + esc(nd.oa_id) + '">在 OpenAlex 查看 ↗</a>' : '') +
      (nd.doi ? '<a class="btn" target="_blank" href="https://doi.org/' + esc(nd.doi) + '">DOI 原文 ↗</a>' : '') +
      '<a class="btn" target="_blank" href="https://kns.cnki.net/kns8s/defaultresult/index?kw=' + q + '">在知网检索 ↗</a>' +
      '<a class="btn" target="_blank" href="https://www.ncpssd.org/Literature/articlelist?searchValue=' + q + '">在国社科文献中心检索 ↗</a>';
    const extBtn = panel.querySelector('.lit-ext-btn');
    if (extBtn) extBtn.addEventListener('click', () => expandNode(extBtn.getAttribute('data-nid'), extBtn));
  }

  function litToast(msg) {
    let t = document.getElementById('litToast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'litToast';
      t.style.cssText = 'position:fixed;bottom:26px;left:50%;transform:translateX(-50%);z-index:99999;' +
        'background:rgba(38,42,50,.94);color:#fff;padding:9px 20px;border-radius:999px;font-size:12.5px;' +
        'box-shadow:0 5px 18px rgba(0,0,0,.28);transition:opacity .3s;pointer-events:none;max-width:70%';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = '1';
    clearTimeout(litToast._t);
    litToast._t = setTimeout(() => { t.style.opacity = '0'; }, 3600);
  }

  async function expandNode(nodeId, btn) {
    if (!current || !current.gid) return;
    const gid = current.gid;
    const old = btn ? btn.textContent : '';
    if (btn) { btn.textContent = '⏳ 扩展中(1-3 分钟)…'; btn.style.pointerEvents = 'none'; }
    litToast('正在向 OpenAlex 拉取该节点的引用网络…');
    try {
      const r = await fetch('/api/litgraph/oa_expand_node', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gid: gid, node_id: nodeId })
      });
      const d = await r.json();
      if (!r.ok || !d.ok) { litToast(d.error || '扩展失败'); if (btn) { btn.textContent = old; btn.style.pointerEvents = ''; } return; }
      renderGraph(d.graph, null);
      current = { graph: d.graph, gid: gid };
      litToast('已并入 ' + d.added.nodes + ' 个新节点（引用' + d.added.ref + '/被引' + d.added.citedby + '/相关' + d.added.related + '），全图 ' + d.graph.stats.n_nodes + ' 节点');
    } catch (e) {
      litToast('扩展失败: ' + String(e).slice(0, 60));
      if (btn) { btn.textContent = old; btn.style.pointerEvents = ''; }
    }
  }

  async function loadSavedList() {
    const box = document.getElementById('litSaved');
    if (!box) return;
    const d = await api('/api/litgraph/list');
    const items = (d.items || []).slice(0, 12);
    box.innerHTML = items.length
      ? '<div style="color:#888;margin-bottom:3px">已存图谱:</div>' + items.map(it =>
        '<a data-gid="' + esc(it.gid) + '">' + esc(it.seed_title.slice(0, 16)) +
        (it.seed_title.length > 16 ? '…' : '') + ' <span style="color:#aaa">' +
        esc((it.ts || '').slice(5, 16)) + '</span></a>').join('')
      : '';
    box.querySelectorAll('a[data-gid]').forEach(a => a.addEventListener('click', async () => {
      const g = await api('/api/litgraph/graph/' + a.getAttribute('data-gid'));
      if (g.graph) renderGraph(g.graph);
    }));
  }

  async function doImport() {
    const btn = document.getElementById('litBuild');
    const seed = document.getElementById('litSeed').value.trim();
    if (!seed) { alert('先填种子文献标题'); return; }
    btn.disabled = true; btn.textContent = '解析中…';
    try {
      const d = await api('/api/litgraph/import', {
        method: 'POST',
        body: JSON.stringify({
          seed_title: seed,
          refs: document.getElementById('litRefs').value,
          citedby: document.getElementById('litCitedby').value,
        }),
      });
      if (d.error) { alert(d.error); return; }
      renderGraph(d.graph);
      loadSavedList();
    } catch (e) {
      alert('导入失败: ' + e);
    } finally {
      btn.disabled = false; btn.textContent = '生成图谱';
    }
  }

  // ── OpenAlex 种子制建图 ────────────────────────────────
  let _oaSelected = null;

  async function oaSearch() {
    const q = document.getElementById('litOaQ').value.trim();
    const box = document.getElementById('litOaCands');
    const btn = document.getElementById('litOaSearch');
    const build = document.getElementById('litOaBuild');
    if (!q) { alert('先填标题或 DOI'); return; }
    _oaSelected = null; build.style.display = 'none';
    btn.disabled = true; btn.textContent = '搜索中…';
    box.innerHTML = '<div style="font-size:12px;color:#888">正在问 OpenAlex(慢网络可能 1 分钟内)…</div>';
    try {
      const d = await api('/api/litgraph/oa_search', {
        method: 'POST', body: JSON.stringify({ query: q }),
      });
      if (d.error) { box.innerHTML = '<div style="font-size:12px;color:#c0392b">' + esc(d.error) + '</div>'; return; }
      if (!d.candidates || !d.candidates.length) {
        box.innerHTML = '<div style="font-size:12px;color:#888">OpenAlex 未命中。换个标题/拼写, 或改用上方知网导出。</div>';
        return;
      }
      box.innerHTML = d.candidates.map((c, i) => {
        const au = (c.authors || []).slice(0, 2).join(', ');
        const sub = [au, c.year, c.source, c.cited_by_count ? '被引' + c.cited_by_count : '',
          c.type ? '类型:' + c.type : '', c.n_refs_total ? '参考文献' + c.n_refs_total + '条' : ''
        ].filter(Boolean).join(' · ');
        const warn = c.type === 'review' || c.type === 'book-review'
          ? '<span class="warn"> ⚠书评(无参考文献列表,建议选书/文章本身)</span>' : '';
        return '<label class="lit-cand"><input type="radio" name="litOaCand" value="' + i + '">' +
          '<span class="t">' + esc(c.title) + '</span>' + warn + '<br>' +
          '<span class="s">' + esc(sub) + '</span></label>';
      }).join('');
      box.querySelectorAll('input[name=litOaCand]').forEach(r => r.addEventListener('change', () => {
        _oaSelected = d.candidates[parseInt(r.value, 10)];
        build.style.display = _oaSelected ? 'block' : 'none';
      }));
    } catch (e) {
      box.innerHTML = '<div style="font-size:12px;color:#c0392b">搜索失败: ' + esc(e) + '</div>';
    } finally {
      btn.disabled = false; btn.textContent = '搜索';
    }
  }

  async function oaBuild() {
    if (!_oaSelected) return;
    const btn = document.getElementById('litOaBuild');
    const st = document.getElementById('litOaStats');
    btn.disabled = true; btn.textContent = '正在拉取参考文献与被引…';
    st.textContent = 'OpenAlex 拉取中, 慢网络可能 1-3 分钟, 勿关闭窗口';
    try {
      const d = await api('/api/litgraph/oa_expand', {
        method: 'POST',
        body: JSON.stringify({ openalex_id: _oaSelected.oa_id }),
      });
      if (d.error) { alert(d.error); st.textContent = ''; return; }
      renderGraph(d.graph);
      const s = d.graph.stats || {};
      st.textContent = (d.graph.source_note || '') + '\n保存于 ' + (d.graph.ts || '');
      loadSavedList();
    } catch (e) {
      alert('建图失败: ' + e);
      st.textContent = '';
    } finally {
      btn.disabled = false; btn.textContent = '用选中项生成图谱';
    }
  }

  document.addEventListener('jx-plugin-page', ev => {
    if (!ev.detail || ev.detail.pid !== 'litgraph') return;
    const btn = document.getElementById('litBuild');
    if (btn) btn.addEventListener('click', doImport);
    const oaSearchBtn = document.getElementById('litOaSearch');
    if (oaSearchBtn) oaSearchBtn.addEventListener('click', oaSearch);
    const oaQ = document.getElementById('litOaQ');
    if (oaQ) oaQ.addEventListener('keydown', e => { if (e.key === 'Enter') oaSearch(); });
    const oaBuildBtn = document.getElementById('litOaBuild');
    if (oaBuildBtn) oaBuildBtn.addEventListener('click', oaBuild);
    const graphBox = document.getElementById('litGraph');
    if (graphBox && typeof echarts !== 'undefined' && !_chart) {
      _chart = echarts.init(graphBox);
      _chart.setOption({ title: { text: '粘贴题录后点"生成图谱"', left: 'center', top: 'middle',
        textStyle: { color: '#b0aa9a', fontSize: 14, fontWeight: 'normal' } } });
    }
    loadSavedList();
    // 窗口尺寸变化自适应
    window.addEventListener('resize', () => { if (_chart) _chart.resize(); });
  });
})();
