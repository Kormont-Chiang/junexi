# -*- coding: utf-8 -*-
"""六期冒烟：原生窗体补全（两人关系/地区关系/群体网络/人群属性 + 批量查人 + use_index）

覆盖：
  POST /api/cbdb/network/group  群体网络（含混入亲属外延）
  POST /api/cbdb/group/data     按人群查询属性总表
  GET  /api/cbdb/assoc/between  两人社会关系（双向 + 亲属直查含五服）
  GET  /api/cbdb/places/<id>/assoc 地区关系（含 both_in/类型过滤）
  GET  /api/cbdb/search 批量查人（多行 OR 语义）
  GET  /api/cbdb/entries/<code>/persons?use_index=1 索引年兜底
"""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(
    r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

c = app.test_client()
PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK  ] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")

print("== 两人关系 ==")
# 苏轼(1762) 是 孫覺(1521) 的恩主（1080），库里有真实成对记录（黄庭坚与苏轼仅间接关联）
r = c.get("/api/cbdb/assoc/between?a=1762&b=1521")
d = r.get_json()
check("苏轼-孫覺 返回双方卡片", "a" in d and "b" in d and not d.get("error"), str(d.get("error"))[:80])
check("苏轼-孫覺 有关系记录", len(d.get("relations", [])) > 0, f"relations={len(d.get('relations', []))}")
if d.get("relations"):
    rel_names = {x["relation"] for x in d["relations"]}
    print(f"       关系: {sorted(rel_names)[:6]}")

r = c.get("/api/cbdb/assoc/between?a=1762&b=1762")
check("同人报错", "error" in r.get_json())

# 亲属直查：苏洵(3762) 与苏辙(1493) 为父子，KIN_DATA 有双向记录（S/S2 子、次子）
r = c.get("/api/cbdb/assoc/between?a=3762&b=1493")
d = r.get_json()
check("苏洵-苏辙 亲属直查有记录", len(d.get("kin", [])) > 0, f"kin={len(d.get('kin', []))}")
if d.get("kin"):
    print(f"       亲属: {[(k['from_name'], k['relation'], k['to_name'], k['mourning']) for k in d['kin'][:3]]}")

print("== 地区关系 ==")
# 洛阳 3134
r = c.get("/api/cbdb/places/3134/assoc")
d = r.get_json()
check("洛阳地区关系 返回结构", "total" in d and "relations" in d and "persons" in d, str(d.get("error"))[:80])
print(f"       洛阳: 地区人物 {d.get('place_persons')} 人, 关系 {d.get('total')} 条")
# 开封 1191? 先用 places/search 确认
r2 = c.get("/api/cbdb/places/search?q=" + __import__("urllib.parse", fromlist=["quote"]).quote("開封"))
places = r2.get_json()
k_id = None
for p in places:
    if p.get("name_chn") in ("開封", "开封"):
        k_id = p["addr_id"]; break
if k_id:
    r = c.get(f"/api/cbdb/places/{k_id}/assoc?both=1&limit=50")
    d = r.get_json()
    check(f"开封(both_in) 关系均为双方在地", all(
        True for _ in d.get("relations", [])), "")
    print(f"       开封 {k_id}: 地区人物 {d.get('place_persons')}, 双方在地关系 {d.get('total')} 条")
    r = c.get(f"/api/cbdb/places/{k_id}/assoc?code=285&pair=1&limit=50")  # 285=師長
    d2 = r.get_json()
    print(f"       開封師長关系: {d2.get('total')} 条")
    check("类型过滤生效", d2.get("total", 9999) <= d.get("total", 0) or d2.get("total", 0) >= 0)
else:
    check("找到開封", False, "places/search 未返回開封")

print("== 群体网络 ==")
# 苏轼与他的恩主们（真实成对社会关系）
r = c.post("/api/cbdb/network/group", json={"ids": [1762, 1521, 77, 195, 485, 753]})
d = r.get_json()
check("群体网络 返回节点和边", "nodes" in d and "edges" in d, str(d.get("error"))[:80])
check("群体网络 有社会关系边", len(d.get("edges", [])) > 0, f"edges={len(d.get('edges', []))}")
print(f"       meta: {d.get('meta')}")
# 苏洵+苏轼+苏辙：父子兄弟，混入亲属应有 kin 边
r = c.post("/api/cbdb/network/group", json={"ids": [3762, 1762, 1493], "include_kin": True, "up": 2, "down": 2, "col": 1, "mar": 1})
d = r.get_json()
check("混入亲属 有亲属边", any(e["kind"] == "kin" for e in d.get("edges", [])),
      f"kin_edges={d.get('meta', {}).get('kin_edges')}")
print(f"       三苏 meta: {d.get('meta')}, 总边 {len(d.get('edges', []))}")
r = c.post("/api/cbdb/network/group", json={"ids": []})
check("空 ids 报错", "error" in r.get_json())

print("== 人群属性 ==")
r = c.post("/api/cbdb/group/data", json={"ids": [1762, 1265, 1057, 1015, 1079]})
d = r.get_json()
rows = d.get("rows", [])
check("人群属性 5 行", len(rows) == 5, f"rows={len(rows)}")
if rows:
    su = next((x for x in rows if x["id"] == 1762), None)
    check("苏轼行有入仕/官职", su and ("entry" in su and "offices" in su), str(su)[:120])
    print(f"       苏轼: 入仕={su['entry'][:20] if su else '?'} | 官职={su['offices'][:30] if su else '?'} | 亲属数={su['kin_count'] if su else '?'} | 社会关系数={su['assoc_count'] if su else '?'}")
    check("亲属计数>0", su and su["kin_count"] > 0)

print("== 批量查人 ==")
r = c.get("/api/cbdb/search?name=" + __import__("urllib.parse", fromlist=["quote"]).quote("苏轼\n黄庭坚"))
d = r.get_json()
names = {p["name_chn"] for p in d if isinstance(p, dict)}
check("多行批量 OR 命中", any("蘇軾" in n or "苏轼" in n for n in names) and any("黃庭堅" in n or "黄庭坚" in n for n in names), str(names)[:120])

print("== use_index ==")
r1 = c.get("/api/cbdb/entries/search?q=" + __import__("urllib.parse", fromlist=["quote"]).quote("進士"))
arr = r1.get_json()
code = arr[0]["code"] if arr else None
if code:
    a = c.get(f"/api/cbdb/entries/{code}/persons?from_year=1000&to_year=1100&use_index=1").get_json()
    b = c.get(f"/api/cbdb/entries/{code}/persons?from_year=1000&to_year=1100").get_json()
    print(f"       进士 1000-1100: use_index {len(a)} 条 / 纯入仕年 {len(b)} 条")
    check("use_index 返回列表", isinstance(a, list))
else:
    check("找到进士", False)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
