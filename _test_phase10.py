# -*- coding: utf-8 -*-
"""十期测试：geojson addr_source=posted / all / with_offices"""
import os, sys
os.environ.setdefault("CBDB_DATA_PATH", r"C:\Users\Lenovo\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, CBDBConnection

# 预热（Access 冷开 79s）
print("warming up CBDB...")
assert CBDBConnection.is_available(), "CBDB 不可用"
print("ok\n")

client = app.test_client()
SU = 3767  # 苏轼
WANG = 1762  # 王安石

passed, failed = [], []
def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {extra}")

print("== posted 模式 ==")
r = client.post("/api/cbdb/persons/geojson", json={"ids": [SU], "addr_source": "posted"})
d = r.get_json()
feats = d["features"]
check("HTTP 200", r.status_code == 200)
check("苏轼任职地 feature ≥ 15", len(feats) >= 15, f"({len(feats)})")
check("全部带 office 字段", all(f["properties"].get("office") for f in feats))
check("全部带坐标", all(f["geometry"]["coordinates"][0] is not None for f in feats))
check("source=posted", all(f["properties"].get("source") == "posted" for f in feats))
hz = [f for f in feats if f["properties"].get("place") == "杭州"]
check("含杭州任职", len(hz) >= 1, f"({len(hz)})")
hz_offices = [f["properties"]["office"] for f in hz]
check("杭州任职含通判或知州", any(("通判" in o) or ("知" in o) for o in hz_offices), str(hz_offices))
hz_years = [(f["properties"].get("firstyear"), f["properties"].get("lastyear")) for f in hz]
check("杭州两段任期(1071/1089)", any(y[0] == 1071 for y in hz_years) and any(y[0] == 1089 for y in hz_years), str(hz_years))

print("\n== bio + with_offices ==")
r = client.post("/api/cbdb/persons/geojson", json={"ids": [SU], "with_offices": True})
d = r.get_json()
feats = d["features"]
check("bio feature 有 offices 字段", all("offices" in f["properties"] for f in feats), f"({len(feats)} feats)")
hz = [f for f in feats if f["properties"].get("place") == "杭州" and f["properties"].get("firstyear") == 1089]
check("杭州1089地址匹配到任职", len(hz) >= 1 and any("杭州" in (o.get("place") or "") for o in hz[0]["properties"]["offices"]),
      str(hz[0]["properties"]["offices"][:2]) if hz else "no 1089 addr")
wuchang = [f for f in feats if f["properties"].get("place") == "黃州"]
if wuchang:
    off = wuchang[0]["properties"]["offices"]
    check("黃州地址匹配團練副使", any("團練" in o.get("office", "") for o in off), str(off[:2]))
else:
    check("黃州地址匹配團練副使", False, "无黄州记录")

print("\n== all 模式 ==")
r = client.post("/api/cbdb/persons/geojson", json={"ids": [SU], "addr_source": "all"})
d = r.get_json()
feats = d["features"]
srcs = {f["properties"]["source"] for f in feats}
check("含 bio+posted 两种 source", srcs == {"bio", "posted"}, str(srcs))
posted = [f for f in feats if f["properties"]["source"] == "posted"]
check("posted 部分补全了姓名", all(f["properties"].get("name") == "蘇軾" for f in posted),
      posted[0]["properties"].get("name") if posted else "none")

print("\n== 多人群体 + posted ==")
r = client.post("/api/cbdb/persons/geojson", json={"ids": [SU, WANG], "addr_source": "posted"})
d = r.get_json()
pids = {f["properties"]["person_id"] for f in d["features"]}
check("含两人任职地", pids == {SU, WANG}, str(pids))

print("\n== 参数健壮性 ==")
r = client.post("/api/cbdb/persons/geojson", json={"ids": [SU], "addr_source": "bogus"})
check("非法 addr_source 回退 bio", r.status_code == 200 and all(
    f["properties"].get("source", "bio") == "bio" for f in r.get_json()["features"]))
r = client.post("/api/cbdb/persons/geojson", json={"ids": [SU], "addr_source": "posted", "addr_types": [1]})
check("posted 模式忽略 addr_types", r.status_code == 200 and len(r.get_json()["features"]) >= 15)

print(f"\n结果: {len(passed)} 通过, {len(failed)} 失败")
if failed:
    print("失败:", failed)
    sys.exit(1)
