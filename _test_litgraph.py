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

r6 = c.get('/plugin/litgraph/page')
check('页面伺服 HTML', r6.status_code == 200 and 'litGraph' in r6.get_data(as_text=True))

print('=== litgraph %d pass / %d fail ===' % (_pass, _fail))
sys.exit(1 if _fail else 0)
