# -*- coding: utf-8 -*-
"""OCR 插件化回归：providers 发现 / 灵眸实跑（真渲染页）/ 路径白名单 / 内置回落"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from app import app
import ocr_service

c = app.test_client()
fails = 0

# 1) providers：灵眸已注册 + builtin 可用
d = c.get("/api/ocr/providers").get_json()
ids = [p["id"] for p in d["providers"]]
ok = "lingmu-ocr" in ids and d.get("builtin") is True
print("PASS" if ok else "FAIL", "providers:", ids, "builtin:", d.get("builtin"))
fails += 0 if ok else 1

# 2) 真页面实跑（page 297 渲染到 %TEMP%，词头 丁义堡 应命中）
tmp = os.path.expandvars(r"%TEMP%\_ocr_api_test.png")
doc = fitz.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "toolbooks", u"中国历史地名大辞典_史为乐_中国社科2005.pdf"))
doc[297].get_pixmap(dpi=150).save(tmp)
r = c.post("/api/ocr/run", json={"path": tmp})
d = r.get_json()
joined = "".join(l["text"] for l in d.get("lines", [])).replace(" ", "")
ok = r.status_code == 200 and d.get("ok") and u"丁义堡" in joined and d.get("provider") == "lingmu-ocr"
print("PASS" if ok else "FAIL", "run:", d.get("provider"), "lines:", len(d.get("lines", [])), "hit:", u"丁义堡" in joined)
fails += 0 if ok else 1
os.remove(tmp)

# 3) 路径白名单：仓库内文件应 403
r = c.post("/api/ocr/run", json={"path": os.path.abspath("app.py")})
ok = r.status_code == 403
print("PASS" if ok else "FAIL", "越权拦截", r.status_code)
fails += 0 if ok else 1

# 4) 禁灵眸 → 回落 builtin（同为 v6 引擎，provider 应为 __builtin__）
import plugin_loader
ov = plugin_loader.load_overrides()
ov["lingmu-ocr"] = {"enabled": False}
plugin_loader.save_overrides(ov)
ocr_service.reset_for_test()
try:
    tmp = os.path.expandvars(r"%TEMP%\_ocr_api_test2.png")
    doc[297].get_pixmap(dpi=120).save(tmp)
    provider, lines = ocr_service.run_ocr(tmp)
    ok = provider == "__builtin__" and len(lines) > 0
    print("PASS" if ok else "FAIL", "回落 builtin:", provider, "lines:", len(lines))
    fails += 0 if ok else 1
    os.remove(tmp)
finally:
    ov = plugin_loader.load_overrides()
    ov.pop("lingmu-ocr", None)
    plugin_loader.save_overrides(ov)
    ocr_service.reset_for_test()

sys.exit(1 if fails else 0)
