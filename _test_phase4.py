# -*- coding: utf-8 -*-
"""四期实测：社会关系检索模块（对标原生十大模块之五）"""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app
from urllib.parse import quote
c = app.test_client()
passed = failed = 0

def t(label, fn, check=None):
    global passed, failed
    try:
        data = fn()
        ok = check(data) if check else not (isinstance(data, dict) and data.get("error"))
        if ok:
            passed += 1
            print(f"[OK  ] {label}")
        else:
            failed += 1
            msg = data.get("error") if isinstance(data, dict) else ""
            print(f"[FAIL] {label}" + (f": {msg}" if msg else ""))
        return data
    except Exception as e:
        failed += 1
        print(f"[FAIL] {label}: {type(e).__name__} {e}")
        return None

# 1. 类型字典
d1 = t("类型字典全量", lambda: c.get("/api/cbdb/assoc/types").get_json(),
       lambda d: len(d) > 400 and all("category" in x and "pair" in x for x in d))
print(f"       共 {len(d1 or [])} 条")

# 2. 同义词：搜「師」应命中門人/弟子
d2 = t("搜「師」命中門人/弟子(同義詞擴展)",
       lambda: c.get(f"/api/cbdb/assoc/types?q={quote('師')}").get_json(),
       lambda d: {"19", "20", "36", "37"}.issubset({str(x["code"]) for x in d}))

# 3. 同义词：搜「門生」（库内无此词）
d3 = t("搜「門生」命中門人(同義詞擴展)",
       lambda: c.get(f"/api/cbdb/assoc/types?q={quote('門生')}").get_json(),
       lambda d: "19" in {str(x["code"]) for x in d} and len(d) >= 3)

# 4. 英文搜索
d4 = t("英文搜索 student",
       lambda: c.get(f"/api/cbdb/assoc/types?q=student").get_json(),
       lambda d: len(d) >= 1)

# 5. 大类过滤
d5 = t("category=学术教育",
       lambda: c.get(f"/api/cbdb/assoc/types?category={quote('学术教育')}").get_json(),
       lambda d: len(d) >= 10 and all(x["category"] == "学术教育" for x in d))

# 6. 人物对：单类型（為Y之門人 code=19）
d6 = t("人物对(為Y之門人,单类型)",
       lambda: c.get("/api/cbdb/assoc/persons?code=19&limit=50").get_json(),
       lambda d: d["total"] > 0 and all(r["relation"] for r in d["relations"]))
print(f"       門人 total={d6['total'] if d6 else '?'}, 本页 {len(d6['relations']) if d6 else '?'} 条")

# 7. pair 并入后出现双向描述
d7 = t("pair=1 并入配对(門人為Y)",
       lambda: c.get("/api/cbdb/assoc/persons?code=19&pair=1&limit=200").get_json(),
       lambda d: len({r["relation"] for r in d["relations"]}) >= 2)
if d7:
    rels = {r["relation"] for r in d7["relations"]}
    print(f"       描述集合: {sorted(rels)}")

# 8. 年份过滤（未来年份 → 0 条）
d8 = t("年份过滤(from_year=9999 → 0)",
       lambda: c.get("/api/cbdb/assoc/persons?code=19&from_year=9999").get_json(),
       lambda d: d["total"] == 0)

# 9. 朝代过滤 dy=15（宋）
d9 = t("朝代过滤(dy=15 全宋)",
       lambda: c.get("/api/cbdb/assoc/persons?code=19&pair=1&dy=15&limit=100").get_json(),
       lambda d: d["total"] > 0)
if d9:
    print(f"       宋代門人 total={d9['total']}")

# 10. 去重人物
t("persons 去重(无重复ID)",
  lambda: c.get("/api/cbdb/assoc/persons?code=19&pair=1&limit=200").get_json(),
  lambda d: len([p["id"] for p in d["persons"]]) == len({p["id"] for p in d["persons"]}))

# 11. 空 code → error
t("空 code → error",
  lambda: c.get("/api/cbdb/assoc/persons").get_json(),
  lambda d: "error" in d)

# 12. limit 上限
t("limit=5000 被压到1000",
  lambda: c.get("/api/cbdb/assoc/persons?code=19&limit=5000").get_json(),
  lambda d: len(d["relations"]) <= 1000)

# 性能
t0 = time.time()
c.get("/api/cbdb/assoc/persons?code=19&pair=1&limit=500")
print(f"\npair+limit500 性能: {time.time()-t0:.2f}s")

print(f"\n结果: {passed} 通过, {failed} 失败")
sys.exit(1 if failed else 0)
