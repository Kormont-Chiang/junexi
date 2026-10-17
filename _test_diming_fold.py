# -*- coding: utf-8 -*-
"""R126 diming 地名辞典折叠预计算守卫"""
import io, sys, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import app as A

c = A.app.test_client()

# 1. 加载后每条带预计算折叠键
A._load_diming_book()
assert len(A._DIMING_BOOK) > 60000, f"entries {len(A._DIMING_BOOK)}"
sample = A._DIMING_BOOK[0]
assert 'head_f' in sample and 'note_f' in sample, "precomputed keys missing"

# 2. 功能回归：简繁/简体都命中，total 一致
r1 = c.get('/api/tools/diming/book?q=' + '开封')
r2 = c.get('/api/tools/diming/book?q=' + '開封')
d1, d2 = json.loads(r1.data), json.loads(r2.data)
assert d1['ok'] and d2['ok']
assert d1['total'] == d2['total'] > 0, (d1['total'], d2['total'])
assert d1['items'][0]['head'] == d2['items'][0]['head']

# 3. 响应不泄漏内部字段
for it in d1['items']:
    assert 'head_f' not in it and 'note_f' not in it, "internal key leaked"

# 4. 空查询安全
r0 = c.get('/api/tools/diming/book?q=')
assert r0.status_code == 200
assert json.loads(r0.data)['total'] == 0

# 5. 性能冒烟：热查询 < 0.5s（预计算后应为几十毫秒级）
import time
t0 = time.time()
c.get('/api/tools/diming/book?q=' + '洛阳')
dt = time.time() - t0
assert dt < 0.5, f"warm query {dt:.2f}s too slow"

print(f"diming-fold-precompute ALL PASS (warm {dt*1000:.0f}ms, entries {len(A._DIMING_BOOK)})")
