# -*- coding: utf-8 -*-
"""R107 文献图谱(litgraph)插件测试"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('JX_LITGRAPH_DIR', tempfile.mkdtemp(prefix='jx_litgraph_test_'))
sys.path.insert(0, ROOT)

_pass = 0
_fail = 0


def check(name, cond, info=''):
    global _pass, _fail
    if cond:
        _pass += 1
        print('  [ok] %s' % name)
    else:
        _fail += 1
        print('  [FAIL] %s | %s' % (name, info))


import importlib.util as _iu

spec = _iu.spec_from_file_location('litp', os.path.join(ROOT, 'plugins', 'litgraph', 'parser.py'))
litp = _iu.module_from_spec(spec)
spec.loader.exec_module(litp)

# ── 1. Refworks 解析 ─────────────────────────────────────
RW = """RT Journal Article
SR 1
A1 荣新江
T1 北魏洛阳的明确布局与选址研究
JF 历史研究
YR 2020
VO 38
IS 4
OP 45-60

RT Journal Article
SR 1
A1 张三
A1 李四
T1 中古都城制度论稿
JF 北京大学学报
YR 2018

"""
rws = litp.parse_refworks(RW)
check('refworks 记录数=2', len(rws) == 2, str(len(rws)))
check('refworks 标题/作者/刊/年', rws[0]['title'].startswith('北魏洛阳')
      and rws[0]['authors'] == ['荣新江'] and rws[0]['source'] == '历史研究'
      and rws[0]['year'] == '2020', json.dumps(rws[0], ensure_ascii=False))
check('refworks 多作者', len(rws[1]['authors']) == 2, str(rws[1]['authors']))

# ── 2. GB/T 7714 解析 ────────────────────────────────────
GBT = """[1] 宿白. 北魏洛阳城和北邙陵墓——鲜卑遗迹辑录之三[J]. 文物, 1978(7): 42-52.
[2] 杨衒之. 洛阳伽蓝记[M]. 北京: 中华书局, 1963: 15.
[3] 钱国祥, 谢虎军, 钱润源. 北魏洛阳外郭城和水道的勘查与发掘[J]. 考古学报, 2016(3): 377-410.
"""
gs = litp.parse_gbt(GBT)
check('gbt 行数=3', len(gs) == 3, str(len(gs)))
check('gbt 期刊型', gs[0]['doctype'] == 'J' and '宿白' in gs[0]['authors']
      and '洛阳伽蓝' not in gs[0]['title'] and '北魏洛阳城' in gs[0]['title'],
      json.dumps(gs[0], ensure_ascii=False))
check('gbt 专著型[M]', gs[1]['doctype'] == 'M' and gs[1]['title'].startswith('洛阳伽蓝'),
      json.dumps(gs[1], ensure_ascii=False))
check('gbt 年份提取', gs[2]['year'] == '2016', gs[2]['year'])

# ── 3. 简繁归一与建图 ────────────────────────────────────
seed_id, nodes, edges = litp.build_graph(
    '北魏洛阳城的形制研究',
    refs=litp.parse_gbt(GBT) + [{'title': '北魏洛阳城的形制研究', 'authors': [], 'source': '', 'year': ''}],
    citedby=litp.parse_refworks(RW))
check('种子自引剔除', all(nd['kind'] != 'seed' or nd['id'] == seed_id for nd in nodes)
      and len([n for n in nodes if n['kind'] == 'seed']) == 1, str(len(nodes)))
check('ref 方向 seed→t', all(e['s'] == seed_id for e in edges
      if any(n['id'] == e['t'] and n['kind'] == 'ref' for n in nodes)), json.dumps(edges, ensure_ascii=False))
check('citedby 方向 s→seed', any(e['t'] == seed_id and e['s'] != seed_id for e in edges),
      json.dumps(edges, ensure_ascii=False))

# R110: related(相关文献, 虚线, 非引用关系)
REL = [{'title': '相关研究甲', 'authors': ['R A'], 'source': 'X 学刊', 'year': '2005'},
       {'title': '北魏洛阳城和北邙陵墓——鲜卑遗迹辑录之三', 'authors': [], 'source': '', 'year': ''}]
sid2, nodes2, edges2 = litp.build_graph('测试种子', refs=litp.parse_gbt(GBT), related=REL)
rel_nd = [n for n in nodes2 if n.get('kind') == 'related']
check('related 节点成虚线边', len(rel_nd) == 1 and rel_nd[0]['title'] == '相关研究甲'
      and any(e.get('dash') and e['t'] == rel_nd[0]['id'] for e in edges2),
      json.dumps({'rel': rel_nd, 'edges': edges2}, ensure_ascii=False))
dup = [n for n in nodes2 if '北邙陵墓' in n['title']]
check('related 与 ref 重合→实线优先', len(dup) == 1 and dup[0]['kind'] == 'ref'
      and not any(e.get('dash') and (e['s'], e['t']) == (sid2, dup[0]['id']) for e in edges2)
      and any(not e.get('dash') and e['t'] == dup[0]['id'] for e in edges2),
      json.dumps(dup, ensure_ascii=False))
norm = litp.norm_title('洛阳伽蓝记')
check('简繁归一(洛阳=洛陽)', norm == litp.norm_title('洛陽伽藍記') and norm == litp.norm_title('洛阳伽蓝记'),
      norm)

# ── 4. API: 导入/列表/读取 ───────────────────────────────
import app  # noqa: E402
c = app.app.test_client()
payload = {
    'seed_title': '北魏洛阳城的形制研究',
    'refs': GBT,
    'citedby': RW,
}
r = c.post('/api/litgraph/import', data=json.dumps(payload), content_type='application/json')
d = json.loads(r.get_data(as_text=True))
check('API import ok', r.status_code == 200 and d.get('ok'), d.get('error', ''))
g = d.get('graph') or {}
check('API stats 一致', (g.get('stats') or {}).get('n_ref') == 3
      and (g.get('stats') or {}).get('n_citedby') == 2, json.dumps(g.get('stats'), ensure_ascii=False))
gid = g.get('gid')

r2 = c.get('/api/litgraph/list')
items = (json.loads(r2.get_data(as_text=True)) or {}).get('items') or []
check('API list 含新图', any(it.get('gid') == gid for it in items), str(len(items)))

r3 = c.get('/api/litgraph/graph/%s' % gid)
d3 = json.loads(r3.get_data(as_text=True))
check('API graph 回读', d3.get('ok') and (d3.get('graph') or {}).get('seed_id') == g.get('seed_id'))

r4 = c.post('/api/litgraph/delete/%s' % gid)
r5 = c.get('/api/litgraph/graph/%s' % gid)
check('API delete 生效', r4.status_code == 200 and r5.status_code == 404)

# ── 5. OpenAlex fetcher 本体 ─────────────────────────────
spec_f = _iu.spec_from_file_location('litf', os.path.join(ROOT, 'plugins', 'litgraph', 'fetcher.py'))
litf = _iu.module_from_spec(spec_f)
spec_f.loader.exec_module(litf)

check('is_doi 识别', litf.is_doi('10.1086/663830') and litf.is_doi(' 10.2307/j.ctt1b3b969 ')
      and not litf.is_doi('北魏洛阳城') and not litf.is_doi('10.x'), '')
check('short_id 截取', litf._short_id('https://openalex.org/W123456') == 'W123456', '')

FAKE_W = {
    'id': 'https://openalex.org/W111', 'display_name': 'Reform in Medieval China',
    'authorships': [{'author': {'display_name': 'John Smith'}},
                    {'author': {'display_name': 'Mary Doe'}},
                    {'author': {'display_name': 'Third Author'}},
                    {'author': {'display_name': 'Fourth'}}],
    'primary_location': {'source': {'display_name': "T'oung Pao"}},
    'publication_year': 1997, 'doi': 'https://doi.org/10.1/abc',
    'cited_by_count': 42, 'referenced_works': ['https://openalex.org/W201', 'https://openalex.org/W202'],
    'type': 'article',
}
nw = litf.norm_work(FAKE_W)
check('norm_work 字段映射', nw['oa_id'] == 'W111' and nw['year'] == '1997'
      and nw['doi'] == '10.1/abc' and len(nw['authors']) == 3
      and nw['source'] == "T'oung Pao" and nw['n_refs_total'] == 2
      and nw['type'] == 'article',
      json.dumps(nw, ensure_ascii=False))
check('norm_work 空输入', litf.norm_work(None) is None, '')

# ── 6. OpenAlex 扩展 API(mock fetcher) ───────────────────
fetcher_mod = sys.modules.get('jx_plugin_litgraph_fetcher')
check('fetcher 已注册', fetcher_mod is not None, str(list(sys.modules.keys())))


def _mk(title, year, cb):
    return {'title': title, 'authors': ['A One'], 'source': 'Journal X',
            'year': str(year), 'oa_id': 'W' + title.replace(' ', '')[:6],
            'doi': '', 'cited_by_count': cb, 'n_refs_total': 0}


_orig = (fetcher_mod.search_works, fetcher_mod.get_work,
         fetcher_mod.get_works_batch, fetcher_mod.get_cited_by, fetcher_mod.get_related)
fetcher_mod.search_works = lambda q, limit=5: ([litf.norm_work(FAKE_W)], 1)
fetcher_mod.get_work = lambda oid: FAKE_W
fetcher_mod.get_works_batch = lambda ids: [_mk('Ref Work A', 1990, 5), _mk('Ref Work B', 1988, 3)]
fetcher_mod.get_cited_by = lambda oid, limit=50: (300, [_mk('Cited Work Y', 2010, 20),
                                                        _mk('Cited Work Z', 2015, 10)])
fetcher_mod.get_related = lambda oid, limit=20: [_mk('Related Work R', 2001, 7)]
try:
    r = c.post('/api/litgraph/oa_search', data=json.dumps({'query': '10.1/abc'}),
               content_type='application/json')
    dd = json.loads(r.get_data(as_text=True))
    check('oa_search 候选', r.status_code == 200 and len(dd.get('candidates') or []) == 1
          and dd['candidates'][0]['oa_id'] == 'W111', dd.get('error', ''))

    r = c.post('/api/litgraph/oa_expand', data=json.dumps({'openalex_id': 'W111'}),
               content_type='application/json')
    dd = json.loads(r.get_data(as_text=True))
    check('oa_expand 建图', r.status_code == 200 and dd.get('ok'), dd.get('error', ''))
    gg = dd.get('graph') or {}
    st = gg.get('stats') or {}
    check('oa stats', st.get('n_ref') == 2 and st.get('n_citedby') == 2
          and st.get('n_citedby_total') == 300 and st.get('n_ref_total') == 2
          and st.get('n_related') == 1,
          json.dumps(st, ensure_ascii=False))
    rel_nd = [n for n in (gg.get('nodes') or []) if n.get('kind') == 'related']
    check('oa related 节点+虚线边', len(rel_nd) == 1
          and any(e.get('dash') for e in (gg.get('edges') or [])),
          json.dumps(rel_nd, ensure_ascii=False))
    seed_nd = [n for n in (gg.get('nodes') or []) if n.get('kind') == 'seed']
    check('oa 种子带元数据', len(seed_nd) == 1 and seed_nd[0].get('doi') == '10.1/abc'
          and seed_nd[0].get('oa_id') == 'W111' and seed_nd[0].get('cited_by_count') == 42,
          json.dumps(seed_nd, ensure_ascii=False))
    check('oa 截断标注', 'OpenAlex' in (gg.get('source_note') or '')
          and '300' in gg['source_note'], gg.get('source_note', ''))
    oa_gid = gg.get('gid')
    r = c.get('/api/litgraph/list')
    items = (json.loads(r.get_data(as_text=True)) or {}).get('items') or []
    check('oa 图谱已持久化', any(it.get('gid') == oa_gid for it in items), oa_gid or '')

    fetcher_mod.search_works = lambda q, limit=5: (_ for _ in ()).throw(RuntimeError('boom'))
    r = c.post('/api/litgraph/oa_search', data=json.dumps({'query': 'x'}),
               content_type='application/json')
    dd = json.loads(r.get_data(as_text=True))
    check('oa 失败诚实报错', r.status_code == 502 and 'boom' in (dd.get('error') or ''),
          str(r.status_code) + ' ' + (dd.get('error') or '')[:60])
finally:
    fetcher_mod.search_works, fetcher_mod.get_work, \
        fetcher_mod.get_works_batch, fetcher_mod.get_cited_by, \
        fetcher_mod.get_related = _orig

r6 = c.get('/plugin/litgraph/page')
check('页面伺服 HTML', r6.status_code == 200 and 'litGraph' in r6.get_data(as_text=True)
      and 'litOaSearch' in r6.get_data(as_text=True))

print('=== litgraph %d pass / %d fail ===' % (_pass, _fail))
sys.exit(1 if _fail else 0)
