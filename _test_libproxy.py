# -*- coding: utf-8 -*-
"""lib-proxy 白名单真实覆盖测试：必须测白名单内站（不止 fallback 里的 ctext）"""
import requests, urllib.parse, sys
sys.stdout.reconfigure(encoding="utf-8")
b = "http://127.0.0.1:5188"
targets = [
    ("https://lib.ucass.edu.cn/", "in-whitelist"),
    ("https://www.guoxuedashi.net/", "in-whitelist"),
    ("https://ctext.org/zh", "fallback-set"),
    ("https://www.example.com/", "must-403"),
]
ok = True
for u, expect in targets:
    try:
        r = requests.get(b + "/api/lib-proxy?url=" + urllib.parse.quote(u, safe=""), timeout=45)
        line = "%s -> %s" % (u, r.status_code)
        if r.status_code == 200:
            line += " bytes=%d base=%s" % (len(r.content), b"<base href" in r.content)
        else:
            line += " " + r.text[:50].replace("\n", " ")
        print(line)
        if expect == "in-whitelist" and r.status_code != 200:
            ok = False
        if expect == "must-403" and r.status_code != 403:
            ok = False
    except Exception as e:
        print(u, "EXC", type(e).__name__, str(e)[:60])
        if expect == "in-whitelist":
            ok = False
print("PASS" if ok else "FAIL")
