# -*- coding: utf-8 -*-
"""地名典前端联调回归：fixture 数据 → 端点 → 清理（不污染 data/toolbooks）"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "toolbooks", "diming_clean.jsonl")
FIXTURE = [
    {"head": u"二江", "note": u"古代郸、捡二江的总称。战国秦李冰任蜀守时所开。", "page": 306},
    {"head": u"测试坞", "note": u"在今测试县西五里。清光绪《测试县志》有载。", "page": 999},
    {"head": u"二陕", "note": u"陕东、陕西的总称。", "page": 306},
]

os.makedirs(os.path.dirname(DATA), exist_ok=True)
existed = os.path.isfile(DATA)
if existed:
    backup = open(DATA, encoding="utf-8").read()
with open(DATA, "w", encoding="utf-8") as f:
    for e in FIXTURE:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

from app import app
import app as appmod
# 端点模块级缓存重置（书稿缺席时 _DIMING_BOOK_LOADED=True 会永久空）
if hasattr(appmod, "_DIMING_BOOK"):
    appmod._DIMING_BOOK = []
if hasattr(appmod, "_DIMING_BOOK_LOADED"):
    appmod._DIMING_BOOK_LOADED = False

c = app.test_client()
fails = 0

r = c.get("/api/tools/diming/book?q=" + u"二江")
d = r.get_json()
ok = r.status_code == 200 and d.get("ok") and any(it["head"] == u"二江" for it in d["items"])
print("PASS" if ok else "FAIL", "query hit", d.get("total"))
fails += 0 if ok else 1

r = c.get("/api/tools/diming/book?q=" + u"测试")
d = r.get_json()
ok = d.get("ok") and u"测试坞" in [it["head"] for it in d["items"]]
print("PASS" if ok else "FAIL", "note search")
fails += 0 if ok else 1

r = c.get("/api/tools/diming/book?q=" + u"不存在xyz")
d = r.get_json()
ok = d.get("ok") and d.get("total") == 0
print("PASS" if ok else "FAIL", "empty result")
fails += 0 if ok else 1

# 清理
if existed:
    open(DATA, "w", encoding="utf-8").write(backup)
else:
    os.remove(DATA)
print("fixture cleaned")
sys.exit(1 if fails else 0)
