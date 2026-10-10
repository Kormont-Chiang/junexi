# -*- coding: utf-8 -*-
import io, re, sys
sys.stdout.reconfigure(encoding="utf-8")
from urllib.parse import urlparse
base = r"dist\JuneXi\_internal"
html = io.open(base + r"\templates\index.html", encoding="utf-8").read()
hosts = set()
pat = r'href="(https?://[^"]+)"[^>]*class="db-card"|class="db-card"[^>]*href="(https?://[^"]+)"'
for m in re.finditer(pat, html):
    u = m.group(1) or m.group(2)
    if u:
        hosts.add(urlparse(u).netloc.lower())
print("hosts:", len(hosts))
print(sorted(hosts)[:10])
print("lib.ucass in:", "lib.ucass.edu.cn" in hosts)
