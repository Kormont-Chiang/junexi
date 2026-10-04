# -*- coding: utf-8 -*-
"""从 CBDB 导出年号/职官数据，合并进六月息前端数据文件。
用法: venv python _export_cbdb_data.py
输出: static/js/data/era-names.js  officials.js (手工条目保留, CBDB 增量合并, 繁转简)
"""
import io, sys, os, re, json
out = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'static', 'js', 'data')
import pyodbc
import opencc
_TS = opencc.OpenCC('t2s')

MDB = os.path.expanduser(r'~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb')

def to_simp(s):
    if not s:
        return s or ''
    return _TS.convert(s)

def parse_js_db(path, varname):
    t = open(path, encoding='utf-8').read()
    m = re.search(re.escape(varname) + r'\s*=\s*\[(.*?)\];', t, re.S)
    if not m:
        raise RuntimeError('var not found: ' + varname)
    body = m.group(1)
    head = t[:m.start()].rstrip()
    if head.endswith('const'):
        head = head[:-5].rstrip()
    items = []
    for em in re.finditer(r'\{([^{}]*)\}', body):
        chunk = em.group(1)
        obj = {}
        for km in re.finditer(r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+)', chunk):
            v = km.group(2)
            if v.startswith('"'):
                obj[km.group(1)] = json.loads(v)
            else:
                obj[km.group(1)] = int(v)
        if obj:
            items.append(obj)
    return items, head

def fmt_js(obj):
    parts = []
    for k, v in obj.items():
        if isinstance(v, (int, float)):
            parts.append('%s: %d' % (k, v))
        else:
            parts.append('%s: %s' % (k, json.dumps(v, ensure_ascii=False)))
    return '  { %s }' % ', '.join(parts)

def main():
    conn = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=%s' % MDB, timeout=30)
    cur = conn.cursor()

    # ── 年号 ──
    eras_manual, era_head = parse_js_db(os.path.join(DATA, 'era-names.js'), 'ERA_NAMES_DB')
    seen = set((e.get('dynasty',''), e.get('era','')) for e in eras_manual)
    cur.execute("select c_dynasty_chn, c_nianhao_chn, c_firstyear, c_lastyear from NIAN_HAO where c_nianhao_chn <> '未詳' and c_firstyear is not null order by c_firstyear")
    cbdb_eras, dup, resid = [], 0, set()
    for dy, era, fy, ly in cur.fetchall():
        dy, era = to_simp(dy), to_simp(era)
        key = (dy, era)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        cbdb_eras.append({'dynasty': dy, 'era': era, 'startYear': int(fy), 'endYear': int(ly) if ly is not None else int(fy), 'emperor': '', 'notes': 'CBDB'})
    all_eras = eras_manual + cbdb_eras
    lines = [era_head.rstrip(), 'const ERA_NAMES_DB = [']
    for e in eras_manual:
        lines.append(fmt_js(e) + ',')
    lines.append('  // ── CBDB 增补（宋史研究中心·中国历代人物传记资料库）──')
    for e in cbdb_eras:
        lines.append(fmt_js(e) + ',')
    lines.append('];')
    tmp = os.path.join(DATA, 'era-names.js.tmp')
    open(tmp, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    os.replace(tmp, os.path.join(DATA, 'era-names.js'))
    out.write('era-names.js: manual=%d cbdb=%d dup_skipped=%d total=%d\n' % (len(eras_manual), len(cbdb_eras), dup, len(all_eras)))

    # ── 职官 ──
    offs_manual, off_head = parse_js_db(os.path.join(DATA, 'officials.js'), 'OFFICIALS_DB')
    seen = set((o.get('dynasty',''), o.get('name','')) for o in offs_manual)
    cur.execute("select c_dy, c_office_chn, c_office_trans, c_category_1 from OFFICE_CODES where c_office_chn is not null and c_office_trans is not null and c_office_trans <> 'Not Yet Translated' and len(c_office_trans) > 1")
    rows = cur.fetchall()
    cur.execute('select c_dy, c_dynasty_chn from DYNASTIES')
    dy_map = {dy: to_simp(chn) for dy, chn in cur.fetchall()}
    conn.close()
    cat2s = {u'統稱': '统称', u'機構': '机构', u'內命婦': '内命妇', u'北面屬國官': '北面属国官',
             u'諸王國官': '诸王国官', u'使府官': '使府官', u'宮官': '宫官', u'天官類': '天官类',
             u'地官類': '地官类', u'春官類': '春官类', u'夏官類': '夏官类', u'秋官類': '秋官类',
             u'冬官類': '冬官类'}
    cbdb_offs, dup, resid = [], 0, set()
    for cdy, chn, trans, cat in rows:
        chn_s, trans = to_simp(chn), (trans or '').strip()
        if len(trans) > 140:
            trans = trans[:140].rsplit(' ', 1)[0] + '…'
        if not chn_s or not trans:
            continue
        if re.search(r'[\u4e00-\u9fff]', trans):
            continue  # 译名里夹中文的脏数据(全库仅3条)
        dyn = dy_map.get(cdy, '')
        key = (dyn, chn_s)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        cbdb_offs.append({'dynasty': dyn, 'name': chn_s, 'rank': cat2s.get(cat or '', to_simp(cat or '')), 'duties': trans, 'notes': 'CBDB'})
    lines = [off_head.rstrip(), 'const OFFICIALS_DB = [']
    for o in offs_manual:
        lines.append(fmt_js(o) + ',')
    lines.append('  // ── CBDB 增补（官名·英译；检索时中文英文均可匹配）──')
    for o in cbdb_offs:
        lines.append(fmt_js(o) + ',')
    lines.append('];')
    tmp = os.path.join(DATA, 'officials.js.tmp')
    open(tmp, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    os.replace(tmp, os.path.join(DATA, 'officials.js'))
    out.write('officials.js: manual=%d cbdb=%d dup_skipped=%d total=%d\n' % (len(offs_manual), len(cbdb_offs), dup, len(offs_manual) + len(cbdb_offs)))
    out.write('done\n')

main()
