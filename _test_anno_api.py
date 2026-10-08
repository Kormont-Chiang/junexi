# -*- coding: utf-8 -*-
"""实体标注回归：年号命中/最长匹配/端点/空文本"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("PASS" if ok else "FAIL"), label, extra)
    fails += 0 if ok else 1

import entity_tag
r = entity_tag.annotate(u"建安四年春事")
check("建安命中", any(e["text"] == u"建安" and e["type"] == u"年号" for e in r["entities"]))
check("带书名片段", r["entities"][0].get("gloss") != "")

r2 = entity_tag.annotate(u"元光元年")
check("元光命中", any(e["text"] == u"元光" for e in r2["entities"]))

r3 = entity_tag.annotate(u"这里没有年号也没有地名xyz")
check("无命中空表", r3["entities"] == [])

r4 = entity_tag.annotate("")
check("空文本 ok=False", r4.get("ok") is False)

r5 = entity_tag.annotate(u"建安")
check("单年号+偏移正确", r5["entities"][0]["start"] == 0 and r5["entities"][0]["end"] == 2)

# 端点
from app import app
c = app.test_client()
resp = c.post("/api/guji/annotate", data=json.dumps({"text": u"建安四年"}), content_type="application/json")
d = resp.get_json()
check("端点 200 + entities", resp.status_code == 200 and d.get("ok") and len(d["entities"]) >= 1, str(resp.status_code))
resp = c.post("/api/guji/annotate", data=json.dumps({"text": ""}), content_type="application/json")
check("端点空 400", resp.status_code == 400)

sys.exit(1 if fails else 0)
