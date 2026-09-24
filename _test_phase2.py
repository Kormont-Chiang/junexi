# -*- coding: utf-8 -*-
"""二期实测：亲属递归四参数 + 五服"""
import os, sys, json, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CBDB_DATA_PATH", os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
c = app.test_client()

def show(label, url, sample=6):
    t0 = time.time()
    d = c.get(url).get_json()
    t1 = time.time()
    if isinstance(d, dict) and d.get("error"):
        print(f"[ERR] {label}: {d['error']}")
        return d
    persons = d.get("persons", [])
    print(f"\n=== {label}: {d.get('count')} 人, truncated={d.get('truncated')}, {t1-t0:.2f}s ===")
    for p in persons[:sample]:
        mo = p.get("mourning") or "—"
        kt = p.get("kintype") or ""
        print(f"  {p['name_chn']:<10} {p['relation']:<14} 服:{mo:<12} {kt}  步(u{d['limits']['up'] if False else ''}"
              f"↑{p['up']}↓{p['down']}旁{p['col']}姻{p['mar']}) {p['dynasty']}")
    return d

# 首次调用会触发索引加载，计时
t0 = time.time()
d = c.get("/api/cbdb/person/1762/kin/recursive?up=2&down=2&col=1&mar=1").get_json()
t1 = time.time()
print(f"首次（含索引加载）: {t1-t0:.1f}s")

d2 = show("王安石 up2/down2/col1/mar1", "/api/cbdb/person/1762/kin/recursive?up=2&down=2&col=1&mar=1")
d3 = show("王安石五服 up4/down4/col3/mar1", "/api/cbdb/person/1762/kin/recursive?up=4&down=4&col=3&mar=1")

# 服制分布统计
from collections import Counter
mo = Counter((p.get("mourning") or "无记录") for p in d3.get("persons", []))
print("\n五服分布:", dict(mo.most_common()))

# 检索式性能（检查有没有意外慢的情况）
show("另一人 韩琦(1883) up3/down3/col2/mar1", "/api/cbdb/person/1883/kin/recursive?up=3&down=3&col=2&mar=1")
print("\nDONE")
