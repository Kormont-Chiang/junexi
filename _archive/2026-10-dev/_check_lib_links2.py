# -*- coding: utf-8 -*-
"""验证史料库丰容候选链接"""
import urllib.request, ssl, sys

sys.stdout.reconfigure(encoding='utf-8')

CANDIDATES = [
    ("中研院漢籍全文", "https://hanchi.ihp.sinica.edu.tw/"),
    ("中华古籍资源库", "https://read.nlc.cn/"),
    ("殆知阁", "https://www.daizhige.org/"),
    ("汉典", "https://www.zdic.net/"),
    ("小学堂", "https://xiaoxue.iis.sinica.edu.tw/"),
    ("汉语大字典智慧平台", "https://hydzd.scu.edu.cn/"),
    ("JSTOR", "https://www.jstor.org/"),
    ("Project MUSE", "https://muse.jhu.edu/"),
    ("清华出土文献中心", "http://www.ctwx.tsinghua.edu.cn/"),
    ("西北师大简牍", "https://jdyz.nwnu.edu.cn/"),
    ("殷周金文资料库", "https://bronzeeasy.ihp.sinica.edu.tw/"),
    ("长沙简牍博物馆", "http://www.changshajiandu.com/"),
    ("数字敦煌", "https://www.e-dunhuang.com/"),
    ("台北故宫", "https://www.npm.gov.tw/"),
    ("一史馆", "https://www.fhac.com.cn/"),
    ("搜韵", "https://sou-yun.cn/"),
    ("MARKUS", "https://markus.ku.nl/"),
    ("中研院数位人文", "https://dportal.sinica.edu.tw/"),
    ("OldMapsOnline", "https://www.oldmapsonline.org/"),
    ("全国报刊索引", "https://www.cnbksy.com/"),
    ("大成老旧期刊", "https://www.dachengdata.com/"),
    ("Kanripo", "https://www.kanripo.org/"),
    ("IDP敦煌", "https://idp.bl.uk/"),
    ("古籍馆", "https://www.gujiguan.com/"),
    ("社科文库", "http://www.sklib.cn/"),
    ("CASHL", "https://www.cashl.edu.cn/"),
    ("读秀", "https://www.duxiu.com/"),
    ("CBDB官网", "https://cbdb.fas.harvard.edu/"),
    ("CHGIS官网", "https://chgis.fas.harvard.edu/"),
    ("爱如生典海", "http://dh.ersjk.com/"),
    ("殷契文渊", "http://jgw.aynu.edu.cn/"),
    ("院馆远程新版", "https://dl.ra.cass.cn/"),
    ("国学网", "https://www.guoxue.com/"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

ok, bad = 0, []
for name, url in CANDIDATES:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            code = r.status
        if 200 <= code < 400:
            print(f"OK   {name}: {code}")
            ok += 1
        else:
            print(f"??   {name}: {code}")
            bad.append((name, url, code))
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__} {str(e)[:70]}")
        bad.append((name, url, str(e)[:70]))

print(f"\n=== {ok}/{len(CANDIDATES)} OK ===")
for n, u, e in bad:
    print(f"  {n} | {u} | {e}")
