# -*- coding: utf-8 -*-
"""一次性：从年号考数据抽取字符清单 → opencc 生成繁简映射表 → 落盘 data/toolbooks/t2s_map.json"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from opencc import OpenCC

ROOT = os.path.dirname(os.path.abspath(__file__))  # historia-server
DATA = os.path.join(ROOT, 'data', 'toolbooks', 'nianhao_clean.jsonl')
OUT = os.path.join(ROOT, 'data', 'toolbooks', 't2s_map.json')

chars = set()
with open(DATA, encoding='utf-8') as f:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        e = json.loads(ln)
        for v in e.values():
            if isinstance(v, str):
                chars.update(v)
            elif isinstance(v, list):
                for x in v:
                    chars.update(str(x))

cc = OpenCC('t2s')
m = {}
for c in sorted(chars):
    s = cc.convert(c)
    if s != c:
        m[c] = s

# 覆盖常见年号查询用字（用户可能输入但数据未出现的简繁对照）
extra = '号总历汉凤龟龙麟德圣神文明武景元贞观乾隆嘉道咸同光绪总章凤曌歷号'
for c in extra:
    s = cc.convert(c)
    if s != c:
        m.setdefault(c, s)

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(m, f, ensure_ascii=False, indent=0, sort_keys=True)
print('chars', len(chars), 'mapped', len(m), '->', OUT)
