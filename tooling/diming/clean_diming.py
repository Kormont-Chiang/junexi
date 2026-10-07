# -*- coding: utf-8 -*-
"""地名大辞典后处理清洗（OCR 完工后一键出 diming_clean.jsonl）
流程: 解析(_parse_diming) → 清洗(本脚本) → 落盘
清洗规则:
  1) CORRECTIONS 高置信词头修正（表空着，校对中逐条收录——存疑不动，交给查询侧折叠）
  2) 垃圾条目: note<4 字 / head<2 字 剔除
  3) 同词头去重（保首见——正文按笔画序，首见即正条）
  4) 词头尾点清理（OCR 噪声）
用法: python _clean_diming.py [--full]
  默认写 diming_clean.partial.jsonl（半成品，不激活端点）
  --full 写仓库 data/toolbooks/diming_clean.jsonl（OCR 100% 后才用）
"""
import importlib.util
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get(u"DIMING_DATA", os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ── 高置信修正（仅词头；逐条人工核对后收录）──
CORRECTIONS = {
    # 例: u'丁義渎': u'丁义渎',  # 繁体残留——待校对后填
}

HEAD_MIN, HEAD_MAX = 2, 12
NOTE_MIN = 4


def _load_parser():
    spec = importlib.util.spec_from_file_location("_diming_parser", os.path.join(HERE, "_parse_diming.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_diming_parser"] = mod
    spec.loader.exec_module(mod)
    return mod


def parse_all():
    P = _load_parser()
    pages = P.load_pages(P.IN)
    entries, carry = [], None
    stats = Counter()
    for pno in sorted(pages):
        lines = [l for l in pages[pno] if "text" in l and l.get("box")]
        if P.is_index_page(lines):
            stats["index_pages"] += 1
            continue
        stats["body_pages"] += 1
        carry = P.parse_body(P.col_split(lines), pno, entries, carry)
    stats["raw_entries"] = len(entries)
    return entries, stats


def clean(entries):
    fix_cnt, seen, out = Counter(), set(), []
    for e in entries:
        head = (e.get("head") or "").strip().strip(u"。，、·•")
        note = (e.get("note") or "").strip()
        for bad, good in CORRECTIONS.items():
            if bad in head:
                fix_cnt[bad] += 1
                head = head.replace(bad, good)
        if not (HEAD_MIN <= len(head) <= HEAD_MAX):
            continue
        if len(note) < NOTE_MIN:
            continue
        if head in seen:
            continue
        seen.add(head)
        out.append({"head": head, "note": note, "page": e.get("page")})
    return out, fix_cnt


def main():
    full = "--full" in sys.argv
    out_path = os.path.join(REPO, "data", "toolbooks", "diming_clean.jsonl") if full \
        else os.path.join(DATA, "diming_clean.partial.jsonl")
    entries, stats = parse_all()
    cleaned, fix_cnt = clean(entries)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for e in cleaned:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("pages: %(body_pages)s body / %(index_pages)s index" % stats)
    print("raw %s -> cleaned %s (dedup/garbage -%s)" % (stats["raw_entries"], len(cleaned), stats["raw_entries"] - len(cleaned)))
    if fix_cnt:
        print("corrections:", dict(fix_cnt))
    lens = sorted(len(e["note"]) for e in cleaned)
    if lens:
        print("note len p50/p90:", lens[len(lens) // 2], lens[int(len(lens) * 0.9)])
    print("->", out_path)


if __name__ == "__main__":
    main()
