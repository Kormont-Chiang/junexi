# -*- coding: utf-8 -*-
"""地名原书检索端点回归：数据缺席 404 / 注入数据后命中 / 折叠生效 / 负例"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A

c = A.app.test_client()

# 1) 数据缺席 → 404
A._DIMING_BOOK = []
A._DIMING_BOOK_LOADED = True
r = c.get(u"/api/tools/diming/book?q=" + u"测试")
d = r.get_json()
ok1 = (r.status_code == 404 and d.get("ok") is False)
print(u"PASS" if ok1 else u"FAIL", u"数据缺席 404", r.status_code, d.get("error", ""))

# 2) 注入数据 → 命中 + 折叠
A._DIMING_BOOK = [
    {"head": u"丁义堡", "note": u"明置，属宁夏前卫。即今宁夏贺兰县西北", "page": 297},
    {"head": u"一堵墙堡", "note": u"明置，在今辽宁本溪", "page": 292},
    {"head": u"丁山镇", "note": u"即鼎山镇。在今江苏宜兴市", "page": 297},
]
CASES = [
    (u"丁义堡", 1), (u"丁義堡", 1),   # 繁简
    (u"一堵墙堡", 1), (u"丁山镇", 1),
    (u"宁夏", 1),                       # note 命中
    (u"不存在xyz", 0),                  # 负例
]
fails = 0
for q, want in CASES:
    d = c.get(u"/api/tools/diming/book?q=" + q).get_json()
    got = d.get("total", 0)
    ok = (got >= 1) if want else (got == 0)
    if not ok:
        fails += 1
    print((u"PASS" if ok else u"FAIL"), u"q=%s total=%d" % (q, got))

# 3) 结构字段
d = c.get(u"/api/tools/diming/book?q=" + u"丁义堡").get_json()
it = d["items"][0]
ok3 = set(["head", "note", "page", "score"]).issubset(it.keys()) and u"史为乐" in d.get("source", "")
print(u"PASS" if ok3 else u"FAIL", u"字段+溯源", it.get("head"), it.get("page"))
fails += 0 if ok3 else 1

sys.exit(1 if fails else 0)
