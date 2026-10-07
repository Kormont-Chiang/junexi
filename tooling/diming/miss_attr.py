# -*- coding: utf-8 -*-
"""漏抽三级归因：OCR缺行(v4锅) / 解析漏(可修) / 页眉缺失(未知)
对 should-have 中每个未命中词头：
  在书眉锚定的正文页找词头字符串——出现而未解析=解析漏；未出现=OCR缺行
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_diming import load_pages, is_index_page

DATA = os.environ.get(u"DIMING_DATA", os.path.dirname(os.path.abspath(__file__)))
HDR = re.compile(u"^([0-9]{1,4})[一二三四五六七八九十]{1,3}画")
HDR_TAIL = re.compile(u"^[一二三四五六七八九十]{1,3}画.*?([0-9]{1,4})\s*$")
JUNK_HEAD = re.compile(u"^[一二三四五六七八九十百]+画$")

idx = json.load(open(DATA + r"\_idx_truth.json", encoding="utf-8"))
idx = {h: p for h, p in idx.items() if not JUNK_HEAD.match(h)}
pages = load_pages(DATA + r"\diming_ocr.jsonl")
parsed = set()
with open(DATA + r"\diming_entries.jsonl", encoding="utf-8") as f:
    for ln in f:
        parsed.add(json.loads(ln)["head"])

printed_page = {}
for pno in sorted(pages):
    lines = [l for l in pages[pno] if "text" in l and l.get("box")]
    if is_index_page(lines):
        continue
    for l in lines[:6] + lines[-4:]:
        m = HDR.match(l.get("text", "").strip()) or HDR_TAIL.match(l.get("text", "").strip())
        if m:
            printed_page[pno] = int(m.group(1))
            break
print_to_pdf = {}
for pno, pr in printed_page.items():
    print_to_pdf.setdefault(pr, pno)

maxp = max(printed_page.values())
should = {h: p for h, p in idx.items() if p <= maxp}
miss = {h: p for h, p in should.items() if h not in parsed}

ocr_absent, parse_miss, unknown = [], [], []
for h, pp in sorted(miss.items(), key=lambda x: x[1]):
    pno = print_to_pdf.get(pp)
    if pno is None:
        unknown.append(h)
        continue
    lines = [l for l in pages[pno] if "text" in l]
    blob = u"\n".join(l.get("text", "") for l in lines)
    # 短词头(<=2字)必须行首命中，防正文行内偶然包含
    if len(h) <= 2:
        hit = any(l.get("text", "").lstrip(u"·•　 ").startswith(h) for l in lines)
    else:
        hit = h in blob
    if hit:
        parse_miss.append((h, pp))
    else:
        ocr_absent.append((h, pp))

total = len(miss)
print("miss total: %d" % total)
print("OCR 缺行(v4锅, v6可望找回): %d (%.0f%%)" % (len(ocr_absent), 100.0 * len(ocr_absent) / total))
print("解析漏(本可治): %d (%.0f%%)" % (len(parse_miss), 100.0 * len(parse_miss) / total))
print("页眉缺失(未知): %d (%.0f%%)" % (len(unknown), 100.0 * len(unknown) / total))
print()
print("--- 解析漏前 25（可直接修）---")
for h, pp in parse_miss[:25]:
    print(u"  %s (printed %d)" % (h, pp))
json.dump({"ocr_absent": ocr_absent, "parse_miss": parse_miss,
           "unknown": unknown, "maxp": maxp, "should": len(should)},
          open(DATA + r"\_miss_attribution.json", "w", encoding="utf-8"), ensure_ascii=False)
