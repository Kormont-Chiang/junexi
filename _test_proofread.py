# -*- coding: utf-8 -*-
"""校对回归：单错建议/未收录串/端点/超长"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("PASS" if ok else "FAIL"), label, extra)
    fails += 0 if ok else 1

import error_check
r = error_check.proofread(u"建安四年春，王芝石拜参知政事。")
sugs = r["suggestions"]
check("王安石建议在位", any(s["pos"] == 7 and s["orig"] == u"芝" and s["char"] == u"安" and s["word"] == u"王安石" for s in sugs))
check("建议带书名片段", all("book" in s and s["book"] for s in sugs))

r2 = error_check.proofread(u"至洛阝一带。")
check("洛阳建议", any(s["orig"] == u"阝" and s["char"] == u"阳" for s in r2["suggestions"]))

r3 = error_check.proofread(u"王安石。")
check("干净文本少误报", len(r3["suggestions"]) <= 2, str(len(r3["suggestions"])))

r4 = error_check.proofread("")
check("空文本 ok=False", r4.get("ok") is False)

r5 = error_check.proofread(u"字" * 4000)
check("超长 400", r5.get("ok") is False)

from app import app
c = app.test_client()
resp = c.post("/api/guji/proofread", data=json.dumps({"text": u"王芝石拜参知政事"}), content_type="application/json")
d = resp.get_json()
check("端点 200 + 王安石", resp.status_code == 200 and any(s["word"] == u"王安石" for s in d.get("suggestions", [])))
resp = c.post("/api/guji/proofread", data=json.dumps({"text": ""}), content_type="application/json")
check("端点空 400", resp.status_code == 400)

sys.exit(1 if fails else 0)
