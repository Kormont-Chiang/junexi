# -*- coding: utf-8 -*-
"""召回测量 v3：书眉锚定（每页印刷页码从页眉行解析，无全局偏移）
书眉格式: "4二画二" / "162三画万"（印刷页码+画数+部首字）
should-have = 索引真值中 印刷页 <= 已OCR正文页的最大连续印刷页
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_diming import load_pages, is_index_page

DATA = os.environ.get(u"DIMING_DATA", os.path.dirname(os.path.abspath(__file__)))
HDR = re.compile(u"^([0-9]{1,4})[一二三四五六七八九十]{1,3}画")  # 右页眉: 4二画二
HDR_TAIL = re.compile(u"^[一二三四五六七八九十]{1,3}画.*?([0-9]{1,4})\s*$")  # 左页眉: 二画二丁7
JUNK_HEAD = re.compile(u"^[一二三四五六七八九十百]+画$")  # 画数节标题污染

idx = json.load(open(DATA + r"\_idx_truth.json", encoding="utf-8"))
# 真值去污染
idx = {h: p for h, p in idx.items() if not JUNK_HEAD.match(h) and len(h) >= 1}
pages = load_pages(DATA + r"\diming_ocr.jsonl")

printed_map = {}  # pdf pno(0-based) -> printed page
for pno in sorted(pages):
    lines = [l for l in pages[pno] if "text" in l and l.get("box")]
    if is_index_page(lines):
        continue
    for l in lines[:6] + lines[-4:]:  # 书眉页首或页尾
        t = l.get("text", "").strip()
        m = HDR.match(t) or HDR_TAIL.match(t)
        if m:
            printed_map[pno] = int(m.group(1))
            break

reached = sorted(printed_map.values())
max_printed = reached[-1] if reached else 0
print("body pages with header:", len(printed_map), "max printed reached:", max_printed)

should = {h for h, p in idx.items() if p <= max_printed}
parsed = set()
with open(DATA + r"\diming_entries.jsonl", encoding="utf-8") as f:
    for ln in f:
        parsed.add(json.loads(ln)["head"])
hit = should & parsed
print("truth heads:", len(idx), "should-have:", len(should), "hit:", len(hit),
      "true_recall: %.1f%%" % (100.0 * len(hit) / max(1, len(should))))
miss = sorted(should - parsed)
print("miss n=%d sample:" % len(miss), miss[:16])
json.dump({"max_printed": max_printed, "should": len(should), "hit": len(hit),
           "recall": round(100.0 * len(hit) / max(1, len(should)), 1),
           "header_pages": len(printed_map)},
          open(DATA + r"\_recall_v3.json", "w", encoding="utf-8"), ensure_ascii=False)
