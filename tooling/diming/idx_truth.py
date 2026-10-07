# -*- coding: utf-8 -*-
"""索引 ground truth v2：词头独占一行 + 页码下一行（真索引格式，p28-278）
→ (head, printed_page) 配对 + 偏移锚定 + 覆盖率折算召回
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_diming import load_pages, is_index_page

DATA = os.environ.get(u"DIMING_DATA", os.path.dirname(os.path.abspath(__file__)))
HEAD = re.compile(u"^[㐀-䶿一-鿿·]{1,12}$")
NUM = re.compile(u"^[0-9]{1,4}$")

pages = load_pages(DATA + r"\diming_ocr.jsonl")
pairs = []
for pno in sorted(pages):
    lines = [l for l in pages[pno] if "text" in l and l.get("box")]
    if not is_index_page(lines):
        continue
    txts = [l.get("text", "").strip() for l in lines]
    for i, t in enumerate(txts[:-1]):
        if HEAD.match(t) and NUM.match(txts[i + 1] or ""):
            pp = int(txts[i + 1])
            if 1 <= pp <= 3300:
                pairs.append((t, pp))
# 去重保最小页
idx = {}
for h, pp in pairs:
    if h not in idx or pp < idx[h]:
        idx[h] = pp
print("paired:", len(pairs), "unique heads:", len(idx))

anchors = {h: idx[h] for h in (u"二股河", u"天台山", u"弓长岭", u"四平街") if h in idx}
print("anchors(printed):", anchors)

# pdf 已 OCR 上限
with open(DATA + r"\diming_ocr.jsonl", "rb") as f:
    tail = f.read()[-200000:].decode("utf-8", "ignore").strip().splitlines()
max_pdf = max(json.loads(ln)["page"] for ln in tail if ln.strip().startswith("{")) + 1

# 偏移：二股河 pdf295 已知
off = None
if u"二股河" in anchors:
    off = 295 - anchors[u"二股河"]
    print("offset(二股河):", off, "→ max printed reached:", max_pdf - off)

json.dump(idx, open(DATA + r"\_idx_truth.json", "w", encoding="utf-8"), ensure_ascii=False)

# 覆盖率折算召回
if off:
    maxp = max_pdf - off
    should = {h for h, pp in idx.items() if pp <= maxp}
    parsed = set()
    with open(DATA + r"\diming_entries.jsonl", encoding="utf-8") as f:
        for ln in f:
            parsed.add(json.loads(ln)["head"])
    hit = should & parsed
    print("should-have(printed<=%d): %d  hit: %d  true_recall: %.1f%%" % (maxp, len(should), len(hit), 100.0 * len(hit) / max(1, len(should))))
    miss = sorted(should - parsed)
    print("miss sample:", miss[:20])
    json.dump({"offset": off, "maxp": maxp, "should": len(should), "hit": len(hit)},
              open(ROOT + r"\_recall_v2.json", "w", encoding="utf-8"), ensure_ascii=False)
