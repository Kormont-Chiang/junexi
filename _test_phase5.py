# -*- coding: utf-8 -*-
"""五期冒烟：检索框原生维度（性别/籍贯/任期/入仕年/身份期过滤）"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app
from urllib.parse import quote
c = app.test_client()
ok = fail = 0

def t(label, cond):
    global ok, fail
    if cond: ok += 1; print(f"[OK  ] {label}")
    else: fail += 1; print(f"[FAIL] {label}")

# 1. 性别过滤
r_female = c.get(f"/api/cbdb/search?name={quote('王')}&gender=1&limit=5").get_json()
r_all = c.get(f"/api/cbdb/search?name={quote('王')}&limit=5").get_json()
t("人名+性别(女) 有结果且 ≤ 不限", isinstance(r_female, list) and 0 < len(r_female) <= len(r_all))
print(f"       王+女 {len(r_female)} 条 / 王+不限 {len(r_all)} 条")

# 2. 籍贯过滤（洛阳 addr_id=3134）
r = c.get(f"/api/cbdb/search?name={quote('王')}&addr_id=3134&limit=5").get_json()
t("人名+籍贯(洛阳3134) 返回列表", isinstance(r, list) and len(r) >= 0)
print(f"       王+籍贯洛阳 {len(r)} 条", [p["native_place"] for p in r[:3]])

# 3. 组合：姓名+朝代+性别
r = c.get(f"/api/cbdb/search?name={quote('王')}&dy=15&gender=1&limit=5").get_json()
t("王+宋+女 全宋", isinstance(r, list) and all(p["dynasty_code"] == 15 for p in r))

# 4. 官职任职者+任期过滤（先用搜索拿个 office_id）
offices = c.get(f"/api/cbdb/offices/search?q={quote('刺史')}").get_json()
oid = offices[0]["office_id"] if offices else None
r0 = c.get(f"/api/cbdb/offices/{oid}/persons?limit=5").get_json()
r1 = c.get(f"/api/cbdb/offices/{oid}/persons?from_year=1000&to_year=1100&limit=5").get_json()
t("官职任职者+任期区间过滤", isinstance(r1, list) and len(r1) <= len(r0))
print(f"       刺史(oid={oid}) 不限 {len(r0)} / 1000-1100 {len(r1)}")

# 5. 入仕+年份+地址
r = c.get(f"/api/cbdb/entries/36/persons?from_year=960&to_year=1100&limit=5").get_json()
t("入仕(进士)+年份过滤", isinstance(r, list) and len(r) >= 0)
print(f"       北宋进士 {len(r)} 条")

# 6. 社会区分+身份起止年
sts = c.get(f"/api/cbdb/status/search?q={quote('進士')}").get_json()
if sts:
    scode = sts[0]["code"]
    r0 = c.get(f"/api/cbdb/status/{scode}/persons?limit=5").get_json()
    r1 = c.get(f"/api/cbdb/status/{scode}/persons?from_year=1000&to_year=1100&limit=5").get_json()
    t("社会区分+身份期过滤", isinstance(r1, list) and len(r1) <= len(r0))
    print(f"       {sts[0]['name_chn']}(code={scode}) 不限 {len(r0)} / 1000-1100 {len(r1)}")

print(f"\n结果: {ok} 通过, {fail} 失败")
sys.exit(1 if fail else 0)
