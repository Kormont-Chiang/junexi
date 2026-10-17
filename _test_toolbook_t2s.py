# -*- coding: utf-8 -*-
"""R118: 工具书简繁折叠守护测试
事故背景: t2s_map.json 手工表 312 条缺'貞'等字, 简体查'贞观'0 命中(R118 走查发现)。
修复: opencc 全量重建 3751 条。本测试防回归。"""
import json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(ROOT, 'data', 'toolbooks')
sys.stdout.reconfigure(encoding='utf-8')
fails = 0

def ck(name, cond, info=''):
    global fails
    ok = bool(cond)
    print(('[ok] ' if ok else '[FAIL] ') + name + ('' if ok else ' | ' + str(info)[:160]))
    if not ok:
        fails += 1

t2s = json.load(open(os.path.join(BASE, 't2s_map.json'), encoding='utf-8'))

def fold(s):
    return ''.join(t2s.get(c, c) for c in s)

# 1. 关键年号简繁同键
pairs = [('貞觀', '贞观'), ('開元', '开元'), ('康熙', '康熙'), ('洪武', '洪武'),
         ('建安', '建安'), ('元祐', '元祐'), ('大曆', '大历'), ('淳熙', '淳熙')]
for tr, sm in pairs:
    ck('折叠同键 %s=%s' % (tr, sm), fold(tr) == fold(sm),
       '%s -> %s / %s -> %s' % (tr, fold(tr), sm, fold(sm)))

# 2. 数据繁体字全覆盖(凡 opencc 定义域内的繁体字必须有映射)
from opencc import OpenCC
cc = OpenCC('t2s')
chars = set()
for fn in os.listdir(BASE):
    if not fn.endswith('.jsonl') or fn.startswith(('cbdb_', '.')):
        continue
    with open(os.path.join(BASE, fn), encoding='utf-8') as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            for ch in json.dumps(d, ensure_ascii=False):
                if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿':
                    chars.add(ch)
trad = [c for c in chars if cc.convert(c) != c]
no_map = [c for c in trad if c not in t2s]
ck('数据繁体字 %d 个全有映射' % len(trad), not no_map, ''.join(sorted(no_map))[:100])

# 3. 映射表规模防退化(低于 3000 说明被手工表覆盖回旧版)
ck('映射表规模 >= 3000', len(t2s) >= 3000, str(len(t2s)))

print('=== toolbook-t2s %s ===' % ('ALL PASS' if fails == 0 else '%d FAIL' % fails))
sys.exit(1 if fails else 0)
