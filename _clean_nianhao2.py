# -*- coding: utf-8 -*-
"""年号考数据二次清洗：
1) 高置信 OCR 误字定向修正（corrections 表，逐条人工确认过）
2) 漏网干支剔除（fold+T2S 后命中 60 干支的 era 项删除——原清洗只滤 exact 干支，OCR 变体漏过）
写回 nianhao_clean.jsonl（git 留有旧版），打印修正统计。
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data', 'toolbooks', 'nianhao_clean.jsonl')

# ── 高置信修正（仅收录确定项；存疑的一律不动，交给查询侧模糊）──
CORRECTIONS = {
    u'缚章': u'總章',   # 總章 OCR 误
    u'已卵': u'己卯',
    u'葵丑': u'癸丑',
    u'癸已': u'癸巳',
    u'已未': u'己未',
    u'天漠': u'天漢',   # 武帝天漢
    u'五属': u'五鳳',   # 宣帝五鳳
    u'元源': u'元鼎',   # 武帝元鼎（位次确认）
    u'鸿亮': u'鴻嘉',   # 成帝鴻嘉
    u'武垦': u'武曌',   # 7 处全部为武曌
}

# ── 60 干支（简体；fold 后比对）──
GAN = u'甲乙丙丁戊己庚辛壬癸'
ZHI = u'子丑寅卯辰巳午未申酉戌亥'
GANZHI = set(GAN[i % 10] + ZHI[i % 12] for i in range(60))

# ── 查询折叠表（confusable 小表 + T2S 映射）──
FOLD = {u'已': u'己', u'葵': u'癸', u'卵': u'卯'}

_t2s = None
def _load_t2s():
    global _t2s
    if _t2s is None:
        with open(os.path.join(ROOT, 'data', 'toolbooks', 't2s_map.json'), encoding='utf-8') as f:
            _t2s = json.load(f)
    return _t2s

def fold(s):
    """T2S + confusable 折叠 → 检索键"""
    t2s = _load_t2s()
    return ''.join(FOLD.get(t2s.get(c, c), t2s.get(c, c)) for c in s)

rows, fix_cnt, drop_cnt = [], {}, 0
with open(DATA, encoding='utf-8') as f:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        e = json.loads(ln)
        # 1) 修正（全字段）
        blob = json.dumps(e, ensure_ascii=False)
        for bad, good in CORRECTIONS.items():
            if bad in blob:
                fix_cnt[bad] = fix_cnt.get(bad, 0) + blob.count(bad)
                blob = blob.replace(bad, good)
        e = json.loads(blob)
        # 2) 漏网干支剔除
        eras = e.get('eras', [])
        kept = [x for x in eras if fold(x) not in GANZHI]
        drop_cnt += len(eras) - len(kept)
        if len(kept) != len(eras):
            e['eras'] = kept
        rows.append(e)

with open(DATA, 'w', encoding='utf-8') as f:
    for e in rows:
        f.write(json.dumps(e, ensure_ascii=False) + '\n')

print('rows', len(rows))
print('corrections', json.dumps(fix_cnt, ensure_ascii=False))
print('ganzhi dropped', drop_cnt)
