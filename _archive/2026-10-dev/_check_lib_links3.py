# -*- coding: utf-8 -*-
"""终验：史料库最终候选链接"""
import urllib.request, ssl, sys
sys.stdout.reconfigure(encoding='utf-8')

CANDIDATES = [
    ("史语所数位典藏", "https://ihparchive.ihp.sinica.edu.tw/ihpkmc/ihpkm"),
    ("复旦出土文献中心", "http://www.gwz.fudan.edu.cn/"),
    ("中研院数位人文", "https://dportal.as.sinica.edu.tw/"),
    ("MARKUS-old", "https://dh.chinese-empires.eu/markus/beta/index.html"),
    ("汉字构形数据库", "http://cdp.sinica.edu.tw/cdphanzi/"),
    ("汉语多功能字库", "https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/"),
    ("殷周金文资料库w9", "https://w9.ihp.sinica.edu.tw/bronze/"),
    ("简牍平台jdsjk", "https://jdsjk.nwnu.edu.cn/"),
]

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
ok, bad = 0, []
for name, url in CANDIDATES:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            code = r.status
        if 200 <= code < 400:
            print(f"OK   {name}: {code}"); ok += 1
        else:
            print(f"??   {name}: {code}"); bad.append((name, url, code))
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__} {str(e)[:60]}"); bad.append((name, url, str(e)[:60]))
print(f"\n=== {ok}/{len(CANDIDATES)} OK ===")
