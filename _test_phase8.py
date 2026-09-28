# -*- coding: utf-8 -*-
"""任务二后端：GET /api/cbdb/places/nearest 地图反查最近地名"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
c = app.test_client()
passed = failed = 0

def t(label, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[OK  ] {label} {extra}")
    else:
        failed += 1
        print(f"[FAIL] {label} {extra}")

# 1. 洛阳市区附近（112.45E, 34.62N）应命中洛阳，距离 <30km
r = c.get("/api/cbdb/places/nearest?x=112.45&y=34.62")
data = r.get_json()
t("洛阳附近 200", r.status_code == 200 and isinstance(data, list) and len(data) > 0)
if data:
    top = data[0]
    print("   首位:", top["name_chn"], top["dist_km"], "km", top["admin_type"], top["firstyear"], "-", top["lastyear"])
    t("距离<30km", top["dist_km"] < 30)
    t("前8含洛阳相关", any("洛" in (p["name_chn"] or "") for p in data[:8]))
    t("按距离升序", all(data[i]["dist_km"] <= data[i+1]["dist_km"] + 0.01 for i in range(len(data)-1)))
    t("字段齐全", all(k in top for k in ("addr_id","name_chn","firstyear","lastyear","admin_type","x_coord","y_coord","dist_km")))

# 2. max_km 过滤生效
r = c.get("/api/cbdb/places/nearest?x=112.45&y=34.62&max_km=5")
d5 = r.get_json()
t("max_km=5 全部<5km", isinstance(d5, list) and all(p["dist_km"] < 5 for p in d5) and len(d5) <= len(data))

# 3. 杭州附近（120.15, 30.27）
r = c.get("/api/cbdb/places/nearest?x=120.15&y=30.27")
hz = r.get_json()
t("杭州附近命中", isinstance(hz, list) and len(hz) > 0 and hz[0]["dist_km"] < 30)
if hz: print("   首位:", hz[0]["name_chn"], hz[0]["dist_km"], "km")

# 4. 参数无效 → 400
t("缺参 400", c.get("/api/cbdb/places/nearest").status_code == 400)
t("非数字 400", c.get("/api/cbdb/places/nearest?x=abc&y=1").status_code == 400)

# 5. 超出中国范围 → 400
t("莫斯科 400", c.get("/api/cbdb/places/nearest?x=37.6&y=55.7").status_code == 400)
t("南海 400", c.get("/api/cbdb/places/nearest?x=114&y=10").status_code == 400)

# 6. 沙漠/边疆无人区：200 但可能为空列表，不炸即可
r = c.get("/api/cbdb/places/nearest?x=90&y=40")  # 敦煌西戈壁
gobi = r.get_json()
t("戈壁 200", r.status_code == 200 and isinstance(gobi, list))

# 7. 与既有路由无冲突（places/search 仍正常）
r = c.get("/api/cbdb/places/search?q=洛阳")
t("places/search 回归", r.status_code == 200 and len(r.get_json()) > 0)

print(f"\n结果: {passed} 通过, {failed} 失败")
sys.exit(1 if failed else 0)
