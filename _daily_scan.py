# -*- coding: utf-8 -*-
import io, os, glob
d = r"C:\Users\Lenovo\.kimi_openclaw\workspace\memory"
out = io.open(r"C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\_daily_report.txt", "w", encoding="utf-8")
files = sorted(glob.glob(os.path.join(d, "2026-09-*.md")))
for f in files:
    txt = io.open(f, encoding="utf-8").read()
    name = os.path.basename(f)
    has_evening = ("晚" in txt and ("聊" in txt or "口述" in txt or "反馈" in txt or "Korm" in txt))
    # count lines mentioning Korm speaking / sections
    secs = [ln.strip() for ln in txt.split("\n") if ln.strip().startswith("## ")]
    out.write(f"== {name} ==\n")
    for s in secs:
        out.write("   " + s + "\n")
out.close()
print("done")
