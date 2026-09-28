# -*- coding: utf-8 -*-
"""群体上地图 addr_types 筛选（WIP 收尾验证）：POST /api/cbdb/persons/geojson 带 addr_types"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))

from app import app

c = app.test_client()

# 苏轼(3767)/苏辙(1493)/王安石(1762)
IDS = [3767, 1493, 1762]

def geojson(addr_types):
    body = {"ids": IDS}
    if addr_types is not None:
        body["addr_types"] = addr_types
    r = c.post("/api/cbdb/persons/geojson", json=body)
    assert r.status_code == 200, r.status_code
    return r.get_json()

all_feats = geojson(None)
typed_feats = geojson([1])  # 仅籍贯
print(f"全类型: {len(all_feats['features'])} 条; 仅籍贯: {len(typed_feats['features'])} 条")
assert len(all_feats["features"]) > 0, "全类型不应为空"

types_in_all = {f["properties"]["addr_type"] for f in all_feats["features"]}
types_in_typed = {f["properties"]["addr_type"] for f in typed_feats["features"]}
print("全类型含:", types_in_all)
print("筛选后含:", types_in_typed)
assert types_in_typed, "籍贯筛选不应为空"
for t in types_in_typed:
    assert "籍" in t, f"筛选后不应出现非籍贯类型: {t}"

# 非法 addr_types 不炸
r = c.post("/api/cbdb/persons/geojson", json={"ids": IDS, "addr_types": ["abc"]})
assert r.status_code == 200
print("非法 addr_types 容错 OK")

# 坐标合法性
for f in all_feats["features"]:
    x, y = f["geometry"]["coordinates"]
    assert 73 < x < 135 and 18 < y < 54, (x, y)
print("坐标范围 OK（WGS84 中国境内）")
print("\n结果: addr_types 筛选 4/4 通过")
