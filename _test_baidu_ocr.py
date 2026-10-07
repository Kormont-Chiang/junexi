# -*- coding: utf-8 -*-
"""百度 OCR 插件回归：配置往返/未配置回落链/providers 排序"""
import sys, os, json, tempfile
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 隔离真实用户目录：整个测试用假 LOCALAPPDATA
_fake = tempfile.mkdtemp(prefix="jx_baidu_test_")
os.environ["LOCALAPPDATA"] = _fake

from app import app
import ocr_service
ocr_service.reset_for_test()

c = app.test_client()
fails = 0

# 1) providers 发现：灵眸(100) 在 百度(50) 前
r = c.get("/api/ocr/providers").get_json()
ids = [p["id"] for p in r["providers"]]
ok = ids == ["lingmu-ocr", "baidu-ocr"]
print("PASS" if ok else "FAIL", "discovery order", ids)
fails += 0 if ok else 1

# 2) 未配置 key → 回落链到灵眸（真页）
import fitz
tmp = os.path.join(_fake, "pg.png")
doc = fitz.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "toolbooks", u"中国历史地名大辞典_史为乐_中国社科2005.pdf"))
doc[297].get_pixmap(dpi=100).save(tmp)
provider, lines = ocr_service.run_ocr(tmp)
ok = provider in ("lingmu-ocr", "__builtin__")
print("PASS" if ok else "FAIL", "fallback when unconfigured ->", provider)
fails += 0 if ok else 1

# 3) 配置端点往返（不落真实盘）
r = c.post("/api/plugins/baidu-ocr/config", json={"api_key": "abcd1234EFGH", "secret_key": "s3cret"})
ok = r.get_json().get("ok")
print("PASS" if ok else "FAIL", "config set", r.status_code)
fails += 0 if ok else 1
r = c.get("/api/plugins/baidu-ocr/config").get_json()
ok = r["configured"] and r["api_key_tail"] == "EFGH"
print("PASS" if ok else "FAIL", "config get tail", r.get("api_key_tail"))
fails += 0 if ok else 1
ok = os.path.isfile(os.path.join(_fake, "JuneXi", "baidu_ocr.json"))
print("PASS" if ok else "FAIL", "file in fake userdir")
fails += 0 if ok else 1

# 4) 缺字段 400
r = c.post("/api/plugins/baidu-ocr/config", json={"api_key": "x"})
ok = r.status_code == 400
print("PASS" if ok else "FAIL", "missing key 400", r.status_code)
fails += 0 if ok else 1

import shutil
shutil.rmtree(_fake, ignore_errors=True)
sys.exit(1 if fails else 0)
