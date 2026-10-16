/* 文献图谱 (litgraph) 插件前端: 导入建图 + ECharts 力导向 + 侧栏题录/跳转 */
(function () {
  let _chart = null;
  let _graph = null;

  const KIND_COLOR = { seed: '#d4af37', ref: '#c0392b', citedby: '#2e5e8c', both: '#7d5ba6' };
  const KIND_LABEL = { seed: '种子', ref: '参考文献', citedby: '引证文献', both: '双向(引证+参考)' };

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
    const nodes = graph.nodes.map(nd => ({
      id: nd.id, name: nd.title,
      symbolSize: nd.kind === 'seed' ? 46 : Math.min(40, 14 + 5 * (deg[nd.id] || 1) + (nd.n > 1 ? 6 : 0)),
      itemStyle: { color: KIND_COLOR[nd.kind] || '#999' },
      label: { show: nd.kind === 'seed', fontSize: 12, formatter: () => nd.title.length > 18 ? nd.title.slice(0, 18) + '…' : nd.title },
      _nd: nd,
    }));
    const links = graph.edges.map(e => ({
      source: e.s, target: e.t,
      lineStyle: { color: '#b8b2a4', width: 1.2, curveness: 0.08 },
    }));
    _chart.setOption({
      animationDuration: 400,
      tooltip: {
        formatter: p => {
          if (p.dataType !== 'node') return '';
          const nd = p.data._nd;
          return '<b>' + esc(nd.title) + '</b><br/>' +
            KIND_LABEL[nd.kind] + (nd.year ? ' · ' + esc(nd.year) : '') + '<br/>' +
            esc((nd.authors || []).slice(0, 3).join(', ')) + '<br/>' +
            '<span style="color:#888">点击看题录与跳转</span>';
        }
      },
      series: [{
        type: 'graph', layout: 'force', roam: true, draggable: true,
        force: { repulsion: 320, edgeLength: [60, 130], gravity: 0.12,
                 friction: 0.25 },
        emphasis: { focus: 'adjacency', lineStyle: { width: 2.6, color: '#8a6d1d' } },
        data: nodes, links: links,
      }],
    });
    _chart.on('click', p => {
      if (p.dataType === 'node') showPanel(p.data._nd, deg);
    });
    // 出度/入度图例计数
    const st = graph.stats || {};
    const stat = document.getElementById('litStats');
    if (stat) {
      stat.textContent = '种子: ' + graph.seed_title + '\n参考文献 ' + st.n_ref +
        ' 篇 · 引证 ' + st.n_citedby + ' 篇 · 节点 ' + st.n_nodes +
        ' · 合并同名 ' + (st.n_merged || 0) + ' 条\n保存于 ' + (graph.ts || '');
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
      (nd.oa_id ? '<a class="btn" target="_blank" href="https://openalex.org/' + esc(nd.oa_id) + '">在 OpenAlex 查看 ↗</a>' : '') +
      (nd.doi ? '<a class="btn" target="_blank" href="https://doi.org/' + esc(nd.doi) + '">DOI 原文 ↗</a>' : '') +
      '<a class="btn" target="_blank" href="https://kns.cnki.net/kns8s/defaultresult/index?kw=' + q + '">在知网检索 ↗</a>' +
      '<a class="btn" target="_blank" href="https://www.ncpssd.org/Literature/articlelist?searchValue=' + q + '">在国社科文献中心检索 ↗</a>';
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
          ? '<span style="color:#c0392b;font-size:11px"> ⚠书评(无参考文献列表,建议选书/文章本身)</span>' : '';
        return '<label style="display:block;padding:5px 6px;border:1px solid #e3e0d8;border-radius:5px;margin-bottom:5px;cursor:pointer">' +
          '<input type="radio" name="litOaCand" value="' + i + '" style="margin-right:5px">' +
          '<b style="font-size:12px">' + esc(c.title) + '</b>' + warn + '<br>' +
          '<span style="font-size:11px;color:#888">' + esc(sub) + '</span></label>';
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
