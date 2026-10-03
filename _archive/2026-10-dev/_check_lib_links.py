# -*- coding: utf-8 -*-
"""检查史料库所有外链的可达性"""
import urllib.request, ssl, sys

sys.stdout.reconfigure(encoding='utf-8')

LINKS = [
    # 校内资源
    ("社科大图书馆", "https://lib.ucass.edu.cn/"),
    ("社科大VPN", "https://vpn.ucass.edu.cn/"),
    ("社科院图书馆", "http://www.lib.cass.org.cn/"),
    ("院馆远程访问", "https://ra.nssd.org/"),
    ("中国社会科学文库", "http://www.sklib.cn/"),
    ("CASHL", "https://www.cashl.edu.cn/"),
    # 综合古籍
    ("爱如生", "https://www.erslib.com/"),
    ("中华经典古籍库", "https://gjqk.com/"),
    ("识典古籍", "https://www.shidianguji.com/"),
    ("ctext", "https://ctext.org/zh"),
    ("书格", "https://www.shuge.org/"),
    ("国学网", "https://www.guoxue.com/"),
    # 期刊
    ("知网", "https://www.cnki.net/"),
    ("国家哲社", "https://www.ncpssd.org/"),
    ("谷歌学术", "https://scholar.google.com/"),
    ("读秀", "https://www.duxiu.com/"),
    ("万方", "https://www.wanfangdata.com.cn/"),
    ("维普", "https://www.cqvip.com/"),
    # 简牍墓志
    ("简帛网", "http://www.bsm.org.cn/"),
    ("殷契文渊", "https://www.jgwz.org/"),
    ("简牍网", "http://www.jianbo.org/"),
    ("国家博物馆", "https://www.chinamuseum.org/"),
    ("故宫博物院", "https://www.dpm.org.cn/"),
    ("国家图书馆", "http://www.nlc.cn/"),
    # 数字人文
    ("CBDB官网", "https://cbdb.fas.harvard.edu/"),
    ("CHGIS官网", "https://chgis.fairbank.fas.harvard.edu/"),
    ("禹贡网", "https://yugong.fudan.edu.cn/"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

ok, bad, slow = 0, [], []
for name, url in LINKS:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
            code = r.status
        if 200 <= code < 400:
            print(f"OK   {name}: {code} {url}")
            ok += 1
        else:
            print(f"??   {name}: {code} {url}")
            bad.append((name, url, code))
    except Exception as e:
        msg = str(e)
        print(f"FAIL {name}: {type(e).__name__} {msg[:80]} {url}")
        bad.append((name, url, msg[:80]))

print(f"\n=== {ok}/{len(LINKS)} OK ===")
if bad:
    print("问题链接:")
    for n, u, e in bad:
        print(f"  {n} | {u} | {e}")
