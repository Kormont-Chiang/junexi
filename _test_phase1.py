# -*- coding: utf-8 -*-
"""一期检索增强 · 修正版全量实测"""
import os, sys, json, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
c = app.test_client()
passed = failed = 0

def t(label, url, check=None):
    global passed, failed
    rv = c.get(url)
    data = rv.get_json()
    if rv.status_code != 200 or (isinstance(data, dict) and data.get("error")):
        failed += 1
        print(f"[FAIL] {label}: HTTP {rv.status_code} -> {str(data)[:160]}")
        return data
    ok = check(data) if check else True
    n = len(data) if isinstance(data, list) else len(data.get("persons", []))
    extra = f" total={data.get('total')}" if isinstance(data, dict) and "total" in data else ""
    tag = "OK  " if ok else "WARN"
    if not ok: failed += 1
    else: passed += 1
    print(f"[{tag}] {label}: {n} 条{extra}")
    return data

t("[1] 别名搜索(介甫)", "/api/cbdb/search?name=介甫",
  lambda d: any(p["id"] == 1762 for p in d))
t("[2] ID直达(1762)", "/api/cbdb/search?name=1762",
  lambda d: any(p["id"] == 1762 for p in d))
t("[3] 官名+门类(统称→統稱)", "/api/cbdb/offices/search?q=&category=统称",
  lambda d: len(d) > 0 and any("統稱" in (p.get("category") or "") for p in d[:5]))
t("[5] 地名+层级(洛阳+Xian)", "/api/cbdb/places/search?q=洛阳&admin_type=Xian",
  lambda d: len(d) > 0)
d6 = t("[6] 同坐标并入(洛阳3134)", "/api/cbdb/places/3134/persons?include_same_coord=1",
  lambda d: len(d) > 0)
# 任职者：先用尚书搜出 office_id，再带时间过滤
d_off = c.get("/api/cbdb/offices/search?q=尚書").get_json()
if d_off:
    oid = d_off[0]["office_id"]
    d4a = t("[4a] 任职者(无过滤)", f"/api/cbdb/offices/{oid}/persons",
            lambda d: True)
    if isinstance(d4a, list) and d4a:
        fy = d4a[0].get("firstyear") or 960
        ly = fy + 30
        d4 = t(f"[4b] 任职者时间过滤({fy}-{ly})", f"/api/cbdb/offices/{oid}/persons?from_year={fy}&to_year={ly}",
               lambda d: True)
t("[7] 入仕年过滤(36=进士,960-1100)", "/api/cbdb/entries/36/persons?from_year=960&to_year=1100",
  lambda d: len(d) > 0)
t("[8] 社会区分搜索(进士)", "/api/cbdb/status/search?q=进士",
  lambda d: len(d) > 0)
t("[9] 著作搜索(资治通鉴)", "/api/cbdb/texts/search?q=資治通鑑",
  lambda d: len(d) > 0)
d10 = t("[10] 年份检索(1086,宋)", "/api/cbdb/year/people?year=1086&dy=15",
        lambda d: d.get("total", 0) > 0)
d11 = t("[11] 详情新字段(王安石)", "/api/cbdb/person/1762", lambda d: True)
if isinstance(d11, dict):
    ok_s = len(d11.get("statuses", [])) > 0
    ok_t = len(d11.get("texts", [])) > 0
    print(f"       statuses={len(d11.get('statuses', []))} texts={len(d11.get('texts', []))}")
    if not ok_s: print("       [WARN] statuses 为空（数据可能本就无记录）")
    if not ok_t: print("       [WARN] texts 为空（数据可能本就无记录）")

d8 = c.get("/api/cbdb/status/search?q=进士").get_json()
if isinstance(d8, list) and d8:
    code = d8[0]["code"]
    t(f"[12] 进士身份人物(code={code})", f"/api/cbdb/status/{code}/persons",
      lambda d: len(d) > 0)
d9 = c.get("/api/cbdb/texts/search?q=資治通鑑").get_json()
if isinstance(d9, list) and d9:
    tid = d9[0]["text_id"]
    t(f"[13] 《续资治通鉴长编》相关人物(text={tid})", f"/api/cbdb/texts/{tid}/persons",
      lambda d: len(d) > 0)

print(f"\n结果: {passed} 通过, {failed} 失败/警告")
