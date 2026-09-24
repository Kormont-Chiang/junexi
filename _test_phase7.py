# -*- coding: utf-8 -*-
"""七期冒烟：两人最短亲属路径（KIN_DATA 无向 BFS + 链式称谓 + 五服）

覆盖：
  GET /api/cbdb/kin/path  兄弟直连 / 父直连 / 子直连 / 多跳姻亲链 / 无路径 / 参数校验 / max_depth

数据冷知识锚点（前六期实测 + 本期双重勘误）：
  苏轼 3767、苏辙 1493、苏洵 3762、黄庭坚 1265、王安石 1762
  ⚠ 勘误①：前六期笔记里的"苏轼(1762)"实为王安石；苏轼正确 ID=3767
  ⚠ 勘误②："苏洵 KIN_DATA 无苏轼"系勘误①的副产品（拿王安石查苏洵的边当然没有）；
     苏洵两个儿子都有：苏轼(3767, 子)、苏辙(1493, 子)
  多跳锚点：王安石(1762)→苏辙(1493) 有 depth=5 姻亲链
  （D-H-W-M-B-B--S-W-F：女之夫之妻之母之兄弟之弟之子之妻之父，含复合 kincode 边）
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

print("== 兄弟直连 ==")
# 苏轼(3767)→苏辙(1493)：苏轼为兄，称苏辙 B-（弟），depth=1，五服期年
r = c.get("/api/cbdb/kin/path?a=3767&b=1493")
d = r.get_json()
check("苏轼→苏辙 found", d.get("found") is True, str(d)[:120])
check("苏轼→苏辙 depth=1", d.get("depth") == 1, f"depth={d.get('depth')}")
check("苏轼→苏辙 称谓含弟", "弟" in (d.get("rel_chain") or ""), f"chain={d.get('rel_chain')}")
mo = d.get("mourning") or {}
check("苏轼→苏辙 五服期年", "期" in (mo.get("mourning") or ""), f"mourning={mo}")
print(f"       chain={d.get('rel_chain')} symbols={d.get('rel_symbols')} "
      f"path={'→'.join(p['name_chn'] for p in d.get('persons', []))}")

print("== 父直连（逆向） ==")
# 苏轼→苏洵：苏轼称苏洵 F（父），depth=1，五服斬衰三年
r = c.get("/api/cbdb/kin/path?a=3767&b=3762")
d = r.get_json()
check("苏轼→苏洵 found depth=1", d.get("found") is True and d.get("depth") == 1, str(d)[:120])
mo = d.get("mourning") or {}
check("苏轼→苏洵 五服斬衰", "斬" in (mo.get("mourning") or ""), f"mourning={mo}")
print(f"       chain={d.get('rel_chain')}")

print("== 父子直连（苏洵→苏轼，正向） ==")
# 苏洵(3762)→苏轼(3767)：苏洵称苏轼 S（子），depth=1
# 前六期"苏洵 KIN_DATA 无苏轼"是勘误①的副产品，实际两个儿子都有
r = c.get("/api/cbdb/kin/path?a=3762&b=3767")
d = r.get_json()
check("苏洵→苏轼 found depth=1", d.get("found") is True and d.get("depth") == 1,
      f"depth={d.get('depth')} reason={d.get('reason')}")
check("苏洵→苏轼 称谓含子", "子" in (d.get("rel_chain") or ""), f"chain={d.get('rel_chain')}")
names = [p["name_chn"] for p in d.get("persons", [])]
check("苏洵→苏轼 两人直连", len(names) == 2, f"names={names}")
print(f"       path={'→'.join(names)} chain={d.get('rel_chain')} "
      f"mourning={(d.get('mourning') or {}).get('mourning')}")

print("== 多跳姻亲链（王安石→苏辙） ==")
# 王安石(1762)→苏辙(1493)：真实 depth=5 姻亲链，含复合 kincode 边
r = c.get("/api/cbdb/kin/path?a=1762&b=1493")
d = r.get_json()
check("王安石→苏辙 found", d.get("found") is True, f"reason={d.get('reason')}")
check("王安石→苏辙 depth>=3", (d.get("depth") or 0) >= 3, f"depth={d.get('depth')}")
check("王安石→苏辙 链式称谓非空", bool(d.get("rel_chain")), f"chain={d.get('rel_chain')}")
print(f"       depth={d.get('depth')} symbols={d.get('rel_symbols')}")
print(f"       chain={d.get('rel_chain')}")

print("== 无亲属路径 ==")
# 黄庭坚(1265)→苏轼(3767)：无亲属记录
r = c.get("/api/cbdb/kin/path?a=1265&b=3767")
d = r.get_json()
check("黄庭坚→苏轼 found=False", d.get("found") is False, str(d)[:120])
print(f"       reason={d.get('reason')}")

print("== 参数校验 ==")
check("同人报错", "error" in c.get("/api/cbdb/kin/path?a=1&b=1").get_json())
check("非数字报错", "error" in c.get("/api/cbdb/kin/path?a=x&b=2").get_json())
check("缺参报错", "error" in c.get("/api/cbdb/kin/path").get_json())

print("== max_depth 行为 ==")
# 王安石→苏辙需 5 步：max_depth=4 应找不到，max_depth=6 应找到
r = c.get("/api/cbdb/kin/path?a=1762&b=1493&max_depth=4")
check("max_depth=4 王安石→苏辙 not found", r.get_json().get("found") is False,
      f"found={r.get_json().get('found')}")
r = c.get("/api/cbdb/kin/path?a=1762&b=1493&max_depth=6")
check("max_depth=6 王安石→苏辙 found", r.get_json().get("found") is True)
# max_depth=99 钳制到 10：仍应正常返回（不会跑飞）
r = c.get("/api/cbdb/kin/path?a=3767&b=1493&max_depth=99")
check("max_depth=99 钳制后仍可用", r.get_json().get("found") is True, str(r.get_json())[:100])

print()
print(f"结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
