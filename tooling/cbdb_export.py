# -*- coding: utf-8 -*-
"""CBDB 人名/官名导出 → data/toolbooks/cbdb_persons.jsonl + cbdb_offices.jsonl
供 entity_tag（实体标注）消费。一次性/增量皆可跑（覆盖写）。
用法：venv\\python tooling\\cbdb_export.py
"""
import io, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "toolbooks")
MDB = os.environ.get("CBDB_DATA_PATH") or os.path.expanduser(
    r"~/Documents/historia-data/cbdb/CBDB_20240208_DATA1.mdb")

import pyodbc
t0 = time.time()
conn = pyodbc.connect(
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=%s" % MDB, timeout=60)
cur = conn.cursor()
os.makedirs(OUT, exist_ok=True)

# 人名（≥2 字；附生卒+朝代）——SQL 必须单行：Access ODBC 对多行字符串会报参数错误
cur.execute(u"SELECT b.c_personid, b.c_name_chn, b.c_birthyear, b.c_deathyear, d.c_dynasty_chn FROM BIOG_MAIN b LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy WHERE b.c_name_chn IS NOT NULL AND Len(b.c_name_chn) >= 2")
n = 0
with io.open(os.path.join(OUT, "cbdb_persons.jsonl"), "w", encoding="utf-8") as f:
    for pid, name, by, dy_, dyn in cur:
        name = (name or "").strip()
        if len(name) < 2:
            continue
        gloss = u" ".join(x for x in [(dyn or "").strip(),
                                      (u"%s-%s" % (by, dy_)) if by and dy_ else u""]
                          if x)
        f.write(json.dumps({"head": name, "pid": pid, "gloss": gloss},
                           ensure_ascii=False) + u"\n")
        n += 1
print(u"persons: %d (%.1fs)" % (n, time.time() - t0))

# 官名（≥2 字）
cur.execute(u"SELECT c_office_id, c_office_chn FROM OFFICE_CODES WHERE c_office_chn IS NOT NULL AND Len(c_office_chn) >= 2")
n2 = 0
with io.open(os.path.join(OUT, "cbdb_offices.jsonl"), "w", encoding="utf-8") as f:
    for oid, name in cur:
        name = (name or "").strip()
        if len(name) < 2:
            continue
        f.write(json.dumps({"head": name, "oid": oid, "gloss": u""},
                           ensure_ascii=False) + u"\n")
        n2 += 1
print(u"offices: %d" % n2)

# 地名（CBDB ADDR_CODES，限人物实际使用过的——补工具书词头缺口如「洛阳」）
cur.execute(u"SELECT DISTINCT a.c_addr_id, a.c_name_chn FROM ADDR_CODES a INNER JOIN (SELECT c_addr_id FROM BIOG_ADDR_DATA UNION SELECT c_addr_id FROM POSTED_TO_ADDR_DATA) u ON a.c_addr_id = u.c_addr_id WHERE a.c_name_chn IS NOT NULL AND Len(a.c_name_chn) >= 2")
n3 = 0
with io.open(os.path.join(OUT, "cbdb_places.jsonl"), "w", encoding="utf-8") as f:
    for aid, name in cur:
        name = (name or "").strip()
        if len(name) < 2 or len(name) > 12:
            continue
        f.write(json.dumps({"head": name, "aid": aid, "gloss": u""},
                           ensure_ascii=False) + u"\n")
        n3 += 1
print(u"places: %d" % n3)
conn.close()
print(u"-> %s" % OUT)
