# -*- coding: utf-8 -*-
"""R115: 插件参数配置 API 测试（Obsidian 式声明设置）"""
import json, os, sys, tempfile, shutil
os.environ.setdefault('JX_LITGRAPH_DIR', tempfile.mkdtemp(prefix='jx_cfgtest_lit_'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plugin_loader as pl

_tmp = tempfile.mkdtemp(prefix='jx_cfgtest_')
pl._user_data_dir = lambda: _tmp  # 测试隔离: 配置写入临时目录

import app
app.app.config['TESTING'] = True
c = app.app.test_client()
fails = 0

def ck(name, cond, info=''):
    global fails
    ok = bool(cond)
    print(('[ok] ' if ok else '[FAIL] ') + name + ('' if ok else ' | ' + str(info)[:180]))
    if not ok:
        fails += 1

mf = pl.plugin_manifest('litgraph')
ck('litgraph manifest 带 settings', bool(((mf.get('settings') or {}).get('fields') or [])))
ck('ai-agent manifest 带 settings',
   bool(((pl.plugin_manifest('ai-agent').get('settings') or {}).get('fields') or [])))

r = c.get('/api/plugins/litgraph/config')
d = r.get_json() or {}
ck('GET config 返回 fields+values',
   r.status_code == 200 and d.get('ok') and len(d.get('fields') or []) == 3,
   json.dumps(d, ensure_ascii=False)[:200])
ck('默认值正确',
   (d.get('values') or {}).get('n_refs') == 100 and (d.get('values') or {}).get('n_related') == 20,
   str(d.get('values')))

r = c.put('/api/plugins/litgraph/config',
          data=json.dumps({'updates': {'n_refs': 200, 'n_citedby': 60, 'n_related': 7}}),
          content_type='application/json')
ck('PUT 保存', r.status_code == 200 and (r.get_json() or {}).get('ok'), str(r.status_code))
r = c.get('/api/plugins/litgraph/config')
ck('持久化读取', (r.get_json() or {}).get('values', {}).get('n_refs') == 200,
   str((r.get_json() or {}).get('values')))

r = c.put('/api/plugins/litgraph/config',
          data=json.dumps({'updates': {'n_refs': 99999}}), content_type='application/json')
ck('int 越界裁剪到 max=200', (r.get_json() or {}).get('values', {}).get('n_refs') == 200,
   str((r.get_json() or {}).get('values')))

r = c.put('/api/plugins/litgraph/config',
          data=json.dumps({'updates': {'no_such': 1}}), content_type='application/json')
ck('未声明字段拒绝 400', r.status_code == 400, str(r.status_code))
r = c.put('/api/plugins/litgraph/config',
          data=json.dumps({'updates': {'n_refs': 'abc'}}), content_type='application/json')
ck('类型不符拒绝 400', r.status_code == 400, str(r.status_code))
r = c.put('/api/plugins/ghost-plugin/config',
          data=json.dumps({'updates': {'x': 1}}), content_type='application/json')
ck('不存在插件 404', r.status_code == 404, str(r.status_code))

# oa_expand 读配置默认值: mock fetcher（routes 运行时模块名是 jx_plugin_litgraph_fetcher）
lit_f = sys.modules.get('jx_plugin_litgraph_fetcher')
ck('routes 的 fetcher 模块已注册', lit_f is not None, str([k for k in sys.modules if 'fetcher' in k]))
FAKE = {'id': 'https://openalex.org/W111', 'display_name': 'Cfg Test Work',
        'authorships': [{'author': {'display_name': 'A'}}],
        'primary_location': {'source': {'display_name': 'J'}},
        'publication_year': 2001, 'doi': '', 'cited_by_count': 5,
        'referenced_works': ['https://openalex.org/W201', 'https://openalex.org/W202'],
        'type': 'article'}
_orig = (lit_f.search_works, lit_f.get_work, lit_f.get_works_batch,
         lit_f.get_cited_by, lit_f.get_related)
lit_f.search_works = lambda q, limit=5: ([lit_f.norm_work(FAKE)], 1)
lit_f.get_work = lambda oid: FAKE
lit_f.get_works_batch = lambda ids: [
    {'title': 'Cfg Ref %03d' % i, 'authors': [], 'source': '', 'year': '1990',
     'oa_id': 'Wc%d' % i, 'doi': '', 'cited_by_count': i, 'type': 'article'}
    for i in range(250)]
lit_f.get_cited_by = lambda oid, limit=50: (300, [
    {'title': 'Cfg Cited %03d' % i, 'authors': [], 'source': '', 'year': '2010',
     'oa_id': 'Wk%d' % i, 'doi': '', 'cited_by_count': i, 'type': 'article'}
    for i in range(120)][:limit])
lit_f.get_related = lambda oid, limit=20: [
    {'title': 'Cfg Rel %03d' % i, 'authors': [], 'source': '', 'year': '2005',
     'oa_id': 'Wr%d' % i, 'doi': '', 'cited_by_count': i, 'type': 'article'}
    for i in range(30)][:limit]
try:
    r = c.post('/api/litgraph/oa_expand',
               data=json.dumps({'seed_title': 'cfg test'}), content_type='application/json')
    st = ((r.get_json() or {}).get('graph') or {}).get('stats') or {}
    ck('oa_expand 用配置默认 n_refs=200', st.get('n_ref') == 200, str(st.get('n_ref')))
    ck('oa_expand 用配置默认 n_citedby=60', st.get('n_citedby') == 60, str(st.get('n_citedby')))
    ck('oa_expand 用配置默认 n_related=7', st.get('n_related') == 7, str(st.get('n_related')))
    # 显式传参优先于配置
    r = c.post('/api/litgraph/oa_expand',
               data=json.dumps({'seed_title': 'cfg test', 'n_related': 3}),
               content_type='application/json')
    st = ((r.get_json() or {}).get('graph') or {}).get('stats') or {}
    ck('显式传参优先于配置', st.get('n_related') == 3, str(st.get('n_related')))
finally:
    lit_f.search_works, lit_f.get_work, lit_f.get_works_batch, \
        lit_f.get_cited_by, lit_f.get_related = _orig

# bool/select/password 类型校验（真实插件只试点 int, 类型边界并进来）
_F = [
    {'key': 'dry_run', 'type': 'bool', 'label': '试运行', 'default': False},
    {'key': 'mode', 'type': 'select', 'label': '模式', 'default': 'std',
     'options': [{'value': 'std', 'label': '标准'}, {'value': 'fast', 'label': '快速'}]},
    {'key': 'api_key', 'type': 'password', 'label': 'Key', 'default': ''},
    {'key': 'limit2', 'type': 'int', 'label': '条数', 'default': 20, 'min': 5, 'max': 100},
]
_mfd = {'id': 'demo', 'settings': {'fields': _F}}
pl._MANIFESTS['demo'] = _mfd
_cases = [
    ('bool 收 True', {'dry_run': True}, True, True),
    ('bool 收 0/1 转布尔', {'dry_run': 1}, True, True),
    ('select 收合法值', {'mode': 'fast'}, True, 'fast'),
    ('select 拒非法值', {'mode': 'evil'}, False, None),
    ('select 拒大小写变体', {'mode': 'STD'}, False, None),
    ('password 收字符串', {'api_key': 'sk-abc'}, True, 'sk-abc'),
    ('int 裁剪到下限', {'limit2': 1}, True, 5),
]
for _name, _upd, _eo, _ev in _cases:
    _clean, _err = pl.validate_plugin_config('demo', _upd, manifest=_mfd)
    _ok = (not _err) == _eo
    if _ok and _eo and _ev is not None and len(_upd) == 1:
        _ok = _clean.get(list(_upd.keys())[0]) == _ev
    ck('types/' + _name, _ok, '%r %r' % (_clean, _err))
ck('types/合并 manifest 默认值',
   pl.get_plugin_config('demo') == {'dry_run': False, 'mode': 'std', 'api_key': '', 'limit2': 20},
   str(pl.get_plugin_config('demo')))

shutil.rmtree(_tmp, ignore_errors=True)
print('=== plugin-config %s ===' % ('ALL PASS' if fails == 0 else '%d FAIL' % fails))
sys.exit(1 if fails else 0)
