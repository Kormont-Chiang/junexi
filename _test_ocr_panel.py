# -*- coding: utf-8 -*-
"""灵眸前端面板回归：页面通道/assets注入事件/上传端点/拒绝非法类型"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from app import app
import io

c = app.test_client()
fails = 0

# 1) 插件页面通道
r = c.get("/plugin/lingmu-ocr/page")
ok = r.status_code == 200 and "lmDrop" in r.get_data(as_text=True)
print("PASS" if ok else "FAIL", "page route", r.status_code)
fails += 0 if ok else 1

# 2) 上传端点（渲染真页作 multipart）
tmp = os.path.expandvars(r"%TEMP%\_panel_up_test.png")
doc = fitz.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "toolbooks", u"中国历史地名大辞典_史为乐_中国社科2005.pdf"))
doc[297].get_pixmap(dpi=120).save(tmp)
with open(tmp, "rb") as f:
    r = c.post("/api/ocr/upload", data={"file": (io.BytesIO(f.read()), "page.png", "image/png")}, content_type="multipart/form-data")
d = r.get_json()
joined = "".join(l["text"] for l in d.get("lines", [])).replace(" ", "")
ok = r.status_code == 200 and d.get("ok") and u"丁义堡" in joined
print("PASS" if ok else "FAIL", "upload", d.get("provider"), "hit:", u"丁义堡" in joined)
fails += 0 if ok else 1

# 3) 临时文件已清理
import glob
leftover = glob.glob(os.path.expandvars(r"%TEMP%\jx_upload_*"))
ok = not leftover
print("PASS" if ok else "FAIL", "temp cleaned", len(leftover))
fails += 0 if ok else 1

# 4) 非法类型拒绝
r = c.post("/api/ocr/upload", data={"file": (io.BytesIO(b"MZ"), "x.exe", "application/octet-stream")}, content_type="multipart/form-data")
ok = r.status_code == 400
print("PASS" if ok else "FAIL", "type reject", r.status_code)
fails += 0 if ok else 1

os.remove(tmp)
sys.exit(1 if fails else 0)
