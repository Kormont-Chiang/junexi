# -*- coding: utf-8 -*-
"""guji 真模型面板级 E2E + 性能计时"""
import sys, os, time, json, subprocess
sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("PASS" if ok else "FAIL"), label, extra)
    fails += 0 if ok else 1

import guji_punct
guji_punct.reset_for_test()
t0 = time.time()
st = guji_punct.status()
load_s = time.time() - t0
check("真模型 state=ready", st["state"] == "ready", st["state"] + " " + str(st["error"]))
check("模型加载 <30s", load_s < 30, "%.1fs" % load_s)

# 标点速度：800 字（一页体量）
page_text = u"天下大乱贤圣不明道德不一天下多得一察焉以自好譬如耳目皆有所明不能相通犹百家众技也皆有所长时有所用虽然不该不遍一之士也判天地之美析万物之理察古人之全寡能备于天地之美称神之容是故内圣外王之道暗而不明郁而不发天下之人各为其所欲焉以自为方悲夫百家往而不反必不合矣后世之学者不幸不见天地之纯古之大体道术将为天下裂" * 3
t0 = time.time()
out, trad = guji_punct.punctuate_text(page_text)
dt = time.time() - t0
check("240字标点 <10s", dt < 10, "%.2fs" % dt)
check("输出有标点", any(p in out for p in u"，。！？；"))

# 端点计时
from app import app
c = app.test_client()
t0 = time.time()
r = c.post("/api/guji/punctuate", data=json.dumps({"text": page_text[:200]}), content_type="application/json")
dt = time.time() - t0
d = r.get_json()
check("端点 200 + ok", r.status_code == 200 and d.get("ok"), str(r.status_code))
print("  端点 200 字耗时 %.2fs" % dt)
print("  样例输出:", d.get("punctuated", "")[:60])

sys.exit(1 if fails else 0)
