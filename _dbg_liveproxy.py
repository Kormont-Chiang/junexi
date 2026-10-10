# -*- coding: utf-8 -*-
import requests, urllib.parse, sys
sys.stdout.reconfigure(encoding="utf-8")
b = "http://127.0.0.1:61097"
for u in ["https://lib.ucass.edu.cn/", "https://ctext.org/zh", "https://www.guoxuedashi.net/"]:
    try:
        r = requests.get(b + "/api/lib-proxy?url=" + urllib.parse.quote(u, safe=""), timeout=45)
        if r.status_code == 200:
            print(u, "-> 200 bytes=", len(r.content), "base=", b"<base href" in r.content)
        else:
            print(u, "->", r.status_code, r.text[:70].replace("\n", " "))
    except Exception as e:
        print(u, "EXC", type(e).__name__, str(e)[:80])
