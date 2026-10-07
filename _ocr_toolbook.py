# -*- coding: utf-8 -*-
"""通用工具书 OCR 管线（OCR插件化方案 落地件）
用法: python _ocr_toolbook.py <pdf路径> [--out X.jsonl] [--dpi 200] [--engine auto]
- engine: auto(默认)=ocr_service 调度（灵眸插件→内置v6）；builtin=强制内置
- 断点续跑：out 已存在的 page 跳过；逐页 flush；每 20 页写进度
- 落盘 schema 与历史管线一致: {page, lines:[{box, text, conf}]}
"""
import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz  # pymupdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default=None, help="输出 JSONL（默认 <pdf同名>_ocr.jsonl）")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--engine", default="auto", choices=["auto", "builtin"])
    args = ap.parse_args()

    pdf = os.path.abspath(args.pdf)
    if not os.path.isfile(pdf):
        print("PDF not found:", pdf)
        sys.exit(1)
    out = args.out or os.path.splitext(pdf)[0] + "_ocr.jsonl"
    log = os.path.splitext(out)[0] + "_progress.txt"

    import ocr_service
    if args.engine == "builtin":
        def run(img):
            return "__builtin__", ocr_service._run_builtin(img)
    else:
        def run(img):
            return ocr_service.run_ocr(img)

    done = set()
    if os.path.isfile(out):
        for ln in open(out, encoding="utf-8"):
            try:
                done.add(json.loads(ln)["page"])
            except Exception:
                pass
    print("resume: %d pages done" % len(done))

    doc = fitz.open(pdf)
    total = len(doc)
    f = open(out, "a", encoding="utf-8")
    tmp = os.path.expandvars(r"%TEMP%\_toolbook_ocr_page.png")
    t0 = time.time()
    n_new = 0
    for p in range(total):
        if p in done:
            continue
        doc[p].get_pixmap(dpi=args.dpi).save(tmp)
        try:
            provider, lines = run(tmp)
            if not any("text" in l for l in lines):
                lines = [{"error": "EMPTY_PAGE_NO_TEXT"}]
        except Exception as e:
            lines = [{"error": "%s: %s" % (type(e).__name__, str(e)[:100])}]
        f.write(json.dumps({"page": p, "lines": lines}, ensure_ascii=False) + "\n")
        f.flush()
        n_new += 1
        if n_new % 20 == 0:
            el = time.time() - t0
            eta = el / n_new * (total - p)
            msg = "page %d/%d  elapsed %.0fs  eta %.0fs" % (p, total, el, eta)
            open(log, "w", encoding="utf-8").write(msg + "\n")
            print(msg)
    open(log, "w", encoding="utf-8").write("DONE %d pages in %.0fs\n" % (total, time.time() - t0))
    print("complete: %d pages -> %s" % (total, out))


if __name__ == "__main__":
    main()
