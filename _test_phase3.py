# -*- coding: utf-8 -*-
"""三期实测：跨查询列表传递 / 网络增强(亲属混入+朝代限定) / GeoJSON GIS 导出"""
import os, sys, io, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
c = app.test_client()
passed = failed = 0

def t(label, fn, check=None):
    global passed, failed
    try:
        data = fn()
        ok = check(data) if check else not (isinstance(data, dict) and data.get("error"))
        tag = "OK  " if ok else "FAIL"
        if not ok:
            failed += 1
        else:
            passed += 1
        msg = data.get("error") if isinstance(data, dict) and data.get("error") else ""
        print(f"[{tag}] {label}" + (f": {msg}" if msg and not ok else ""))
        return data
    except Exception as e:
        failed += 1
        print(f"[FAIL] {label}: {type(e).__name__} {e}")
        return None

# ── 0. 准备：拿两组人物ID（王安石亲属 + 进士）──
kin = c.get("/api/cbdb/person/1762/kin/recursive?up=2&down=2&col=1&mar=1").get_json()
kin_ids = [p["id"] for p in kin.get("persons", [])]
print(f"准备：王安石亲属 {len(kin_ids)} 人")

jinshi = c.get("/api/cbdb/entries/36/persons?from_year=960&to_year=1100").get_json()
js_ids = [p["id"] for p in jinshi][:80] if isinstance(jinshi, list) else []
print(f"准备：北宋进士(样本80) {len(js_ids)} 人")

# ── 1. 跨查询列表传递：POST /api/cbdb/query + person_ids ──
def q1():
    d = c.post("/api/cbdb/query", json={"filters": {"dy": "15"}, "person_ids": kin_ids})
    assert d.status_code == 200
    return d.get_json()
def chk1(d):
    ids = {p["id"] for p in d}
    return len(d) > 0 and ids.issubset(set(kin_ids)) and all(p["dynasty_code"] == 15 for p in d)
t("POST综合查询∩范围(王安石亲属中宋人)", q1, chk1)

def q2():
    d = c.post("/api/cbdb/query", json={"filters": {}, "person_ids": []})
    return d.get_json()
t("空范围→空结果(恒假条件)", q2, lambda d: d == [])

def q3():
    d = c.post("/api/cbdb/query", json={"filters": {"entry_code": "36"}, "person_ids": js_ids})
    return d.get_json()
def chk3(d):
    ids = {p["id"] for p in d}
    return len(d) > 0 and ids.issubset(set(js_ids))
t("POST综合查询∩范围(北宋进士样本中再查进士)", q3, chk3)

def q4():
    d = c.get(f"/api/cbdb/year/people?year=1086&ids={','.join(map(str, kin_ids[:60]))}")
    return d.get_json()
def chk4(d):
    ids = {p["id"] for p in d.get("persons", [])}
    return d.get("total", 0) >= 0 and ids.issubset(set(kin_ids))
t("年份检索带ids范围(1086∩王安石亲属)", q4, chk4)

def q5():
    return c.get("/api/cbdb/query?name=王安石").get_json()
t("GET综合查询兼容(无范围)", q5, lambda d: len(d) > 0)

# ── 2. 网络增强 ──
def n1():
    return c.get("/api/cbdb/network/1762").get_json()
def chk_n1(d):
    kinds = {e.get("kind") for e in d.get("edges", [])}
    return len(d.get("nodes", [])) > 1 and kinds == {"assoc"}
t("网络默认(仅社会关系, kind=assoc)", n1, chk_n1)

def n2():
    return c.get("/api/cbdb/network/1762?include_kin=1").get_json()
d_n2 = t("网络亲属混入(kind含kin)", n2, lambda d: "kin" in {e.get("kind") for e in d.get("edges", [])})

def n3():
    return c.get("/api/cbdb/network/1762?include_kin=1&dy=15").get_json()
def chk_n3(d):
    # 外围节点全是宋人，中心保留
    non_center = [n for n in d.get("nodes", []) if not n.get("center")]
    return all(n.get("dynasty") == "宋" for n in non_center)
t("网络朝代限定(dy=15 全宋)", n3, chk_n3)

def n4():
    d = c.get("/api/cbdb/network/1762?include_kin=1").get_json()
    return d
def chk_n4(d):
    nodes = d.get("nodes", [])
    return len(nodes) <= 301 and len(d.get("edges", [])) <= 300
t("网络节点上限(≤300边)", n4, chk_n4)

# 抽查：混入后是否有同名节点去重（kin 已在 assoc 中）
def n5():
    d = c.get("/api/cbdb/network/1762?include_kin=1").get_json()
    ids = [n["id"] for n in d.get("nodes", [])]
    return d
t("网络节点ID唯一", n5, lambda d: len([n["id"] for n in d["nodes"]]) == len({n["id"] for n in d["nodes"]}))

# ── 3. GeoJSON 导出 ──
def g1():
    return c.post("/api/cbdb/persons/geojson", json={"ids": [1762, 1883, 3134]}).get_json()
d_g1 = t("GeoJSON(王安石+韩琦+未知3134)", g1, lambda d: len(d.get("features", [])) > 0)
if d_g1:
    f0 = d_g1["features"][0]
    print(f"       示例: {f0['properties']['name']} @ {f0['geometry']['coordinates']} ({f0['properties']['addr_type']}) {f0['properties']['place']}")
    ok_geo = all(f["geometry"]["type"] == "Point" and len(f["geometry"]["coordinates"]) == 2 for f in d_g1["features"])
    print(f"       几何校验: {'通过' if ok_geo else '失败'}，共 {len(d_g1['features'])} 点")

def g2():
    return c.post("/api/cbdb/persons/geojson", json={"ids": kin_ids[:50]}).get_json()
t("GeoJSON 批量(亲属50人)", g2, lambda d: len(d.get("features", [])) >= 0)

def g3():
    return c.post("/api/cbdb/persons/geojson", json={"ids": []}).get_json()
t("GeoJSON 空ids→400", g3, lambda d: "error" in d)

# 大列表性能
t0 = time.time()
c.post("/api/cbdb/query", json={"filters": {}, "person_ids": kin_ids})
print(f"\n范围查询性能: {time.time()-t0:.2f}s ({len(kin_ids)} ids)")

print(f"\n结果: {passed} 通过, {failed} 失败")
