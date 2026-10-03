# -*- coding: utf-8 -*-
"""史料库外链体检：HTTP 状态探测"""
import re, io, sys, os, urllib.request, ssl, socket
out = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
h = r'C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server'
t = open(os.path.join(h, 'templates', 'index.html'), encoding='utf-8').read()
a = t.find('<div id="library"'); b = t.find('<div id="map"', a)
seg = t[a:b]
cards = re.findall(r'<a href="([^"]+)"[^>]*class="db-card"[^>]*>.*?<div class="db-name">([^<]+)</div>', seg, re.S)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
socket.setdefaulttimeout(10)
results = []
for url, name in cards:
    url = url.strip(); name = name.strip()
    if url == '#':
        results.append((name, url, '内置', '')); continue
    status = None; final = ''; err = ''
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, method=method, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            r = urllib.request.urlopen(req, timeout=10, context=ctx)
            status = r.status; final = r.geturl()[:80]; break
        except urllib.error.HTTPError as e:
            status = e.code
            if method == 'HEAD' and e.code in (403, 405, 501):
                continue
            break
        except Exception as e:
            err = type(e).__name__ + ':' + str(e)[:60]
            if method == 'HEAD':
                continue
            break
    results.append((name, url, str(status) if status else 'FAIL', err or final))
ok = warn = bad = 0
for name, url, st, info in results:
    tag = ''
    if st in ('200', '301', '302', '403'): tag = 'OK' if st == '200' else 'CHECK'
    elif st == '内置': tag = 'SKIP'
    else: tag = 'BAD'
    if tag == 'OK': ok += 1
    elif tag in ('CHECK',): warn += 1
    elif tag == 'BAD': bad += 1
    out.write(f'[{tag}] {st:<5} {name} | {url} {(" | " + info) if info else ""}\n')
out.write(f'\n=== OK={ok} CHECK={warn} BAD={bad} 内置={sum(1 for r in results if r[2]=="内置")} ===\n')
