# -*- coding: utf-8 -*-
"""年号原书检索折叠回归：简体/误字/繁体三向命中 + 既有行为不回归"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

c = app.test_client()

CASES = [
    # (q, 期望 top1 ruler 包含, 说明)
    (u"总章", u"太宗李世民", u"简体→繁体;總章在太宗条目(书版式,高宗沿用至改元)"),
    (u"總章", u"太宗李世民", u"繁体原字同条目"),
    (u"己卯", u"",        u"简体→繁体+已→己折叠,只验 total>0"),
    (u"已卯", u"",        u"误字查询→折叠命中己卯"),
    (u"天汉", u"武帝",    u"简体天汉→天漢"),
    (u"武曌", u"",        u"曌字 ruler 命中"),
    (u"五凤", u"",        u"简体五凤→五鳳"),
    (u"鸿嘉", u"",        u"简体鸿嘉→鴻嘉"),
    (u"建平", u"",        u"基线:原本就命中"),
    (u"618",  u"",        u"基线:纯数字年份区间查询"),
    (u"元鼎", u"武帝",    u"修正后元鼎回位"),
]

fails = 0
for q, want_ruler, desc in CASES:
    r = c.get(u"/api/tools/era/book?q=" + q)
    d = r.get_json()
    top = d["items"][0] if d.get("items") else {}
    ruler = top.get("ruler", "")
    ok = d.get("ok") and d.get("total", 0) > 0
    if want_ruler:
        ok = ok and want_ruler in ruler
    status = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    print(u"%s  q=%-6s total=%-3d top1=%s | %s" % (status, q, d.get("total", 0), ruler[:14], desc))

# 负例：乱查不应命中
r = c.get(u"/api/tools/era/book?q=" + u"zzzz不存在")
d = r.get_json()
neg = (d.get("total", 0) == 0)
print(u"%s  负例 total=%d" % ("PASS" if neg else "FAIL", d.get("total", 0)))
fails += 0 if neg else 1

sys.exit(1 if fails else 0)
