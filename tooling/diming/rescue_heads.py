# -*- coding: utf-8 -*-
"""diming_clean 二次清洗：前言垃圾过滤 + 词头粘连修复（P+R 切分）
独立运行（读现成 diming_clean.jsonl → 重写），不入 clean_diming.py 保持管线可复现。
"""
import io, json, os, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(BASE, "data", "toolbooks")

# 单字功能词（绝不入地名）：避免误杀 成都/会稽/北平/和平 等
GARBAGE_CHARS = u"的了吗呢吧啊嘛是在或也就及其这那又把被让向从但而且"
# 散文短语（子串级）：前言渗漏专用，不误伤单字地名
GARBAGE_PHRASES = tuple([u"先生", u"我们", u"研究", u"资料", u"困难", u"水平", u"决定",
                         u"希望", u"部分", u"问题", u"内容", u"方面", u"作为", u"对于",
                         u"其中", u"以及", u"所谓", u"当然", u"其他", u"特别", u"认真",
                         u"进行", u"辞典", u"学术", u"实用", u"流传", u"主编", u"都邑",
                         u"实际上", u"确实", u"希望", u"认为", u"指出", u"应该"])

NOTE_STARTERS = tuple([u"在今", u"即今", u"旧治", u"一作", u"又名", u"亦名", u"后改", u"故城",
                       u"市", u"县", u"州", u"郡", u"府", u"军", u"路", u"镇", u"堡", u"站",
                       u"营", u"村", u"里", u"治", u"本", u"旧", u"故", u"即", u"先"])

# 已知词干：CBDB 地名（简繁）+ 年号
known = set()
for line in io.open(os.path.join(DATA, "cbdb_places.jsonl"), encoding="utf-8"):
    h = json.loads(line)["head"].strip()
    known.add(h)
try:
    from opencc import OpenCC
    _t2s = OpenCC("t2s").convert
except Exception:
    _t2s = lambda s: s
known |= set(_t2s(x) for x in list(known))
for line in io.open(os.path.join(DATA, "nianhao_clean.jsonl"), encoding="utf-8"):
    e = json.loads(line)
    for era in (e.get("eras") or []):
        if era and len(era) >= 2:
            known.add(era.strip())
known = sorted((x for x in known if 2 <= len(x) <= 7), key=lambda x: -len(x))
print(u"known stems:", len(known))

src = os.path.join(DATA, "diming_clean.jsonl")
bak = src + ".bak"
# 从 .bak 重跑（上次误杀版结果作废）
if os.path.isfile(bak):
    entries = [json.loads(l) for l in io.open(bak, encoding="utf-8") if l.strip()]
    print(u"from backup:", len(entries))
else:
    entries = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
print(u"in:", len(entries))

n_garbage = n_split = n_drop = 0
out = []
seen = set()
for e in entries:
    h, note = e["head"].strip(), (e.get("note") or "").strip()
    # 1) 前言垃圾：词头含单字功能词或散文短语
    if any(c in h for c in GARBAGE_CHARS) or any(p in h for p in GARBAGE_PHRASES):
        n_garbage += 1
        continue
    # 2) 粘连修复：H = P + R，P 已知，R 以注文起始词开头
    # 单字后缀 R ∈ {府,州,县,郡,军,路} 要求 len(P)>=3——保护 江宁府/开封府 这类全称；
    # R=市/镇/堡/站/营/村/里 P>=2 即可（后缀基本非全称）；多字 R 一律安全
    GUARD3 = u"府州郡县军路"
    fixed = False
    if 3 <= len(h) <= 10:
        for p in known:
            if h.startswith(p):
                r = h[len(p):]
                if not (1 <= len(r) <= 6) or not r.startswith(NOTE_STARTERS):
                    continue
                if len(r) == 1 and r in GUARD3 and len(p) < 3:
                    continue
                note = (r + note) if note else r
                h = p
                n_split += 1
                fixed = True
                break
    if len(h) < 2 or len(note) < 2 or h in seen:
        n_drop += 1
        continue
    seen.add(h)
    out.append({"head": h, "note": note, "page": e.get("page")})

print(u"garbage filtered: %d, split fixed: %d, dedup/short dropped: %d" % (n_garbage, n_split, n_drop))
print(u"out:", len(out))
# 抽查修复结果 + 黄金名单存活检查
for e in out:
    if e["head"] == u"洛阳":
        print(u"洛阳 entry:", e["note"][:50])
        break
gold = [u"会稽", u"北平", u"平阳", u"成都", u"中牟", u"中山", u"和平", u"和顺", u"大都", u"上都", u"洛阳", u"江宁府"]
heads = set(e["head"] for e in out)
for g in gold:
    if g not in heads:
        print(u"MISSING gold:", g)
print(u"gold check done")
if not os.path.isfile(bak):
    os.rename(src, bak)
    print(u"backup ->", bak)
with io.open(src, "w", encoding="utf-8") as f:
    for e in out:
        f.write(json.dumps(e, ensure_ascii=False) + u"\n")
print(u"rewritten:", src)
