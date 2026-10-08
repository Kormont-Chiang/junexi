# -*- coding: utf-8 -*-
"""灵眸面板 E2E 测试图：中文印刷体样张"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 900, 320
img = Image.new("RGB", (W, H), (250, 248, 242))
d = ImageDraw.Draw(img)
try:
    f_big = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 40)
    f_mid = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
except Exception:
    f_big = f_mid = ImageFont.load_default()

d.text((40, 30), u"中国历史地名大辞典", font=f_big, fill=(30, 28, 24))
d.text((40, 100), u"二江：古代郸、捡二江的总称。", font=f_mid, fill=(40, 38, 34))
d.text((40, 150), u"战国秦李冰任蜀守时所开。", font=f_mid, fill=(40, 38, 34))
d.text((40, 200), u"七里川：一名羌源河，在今陕西旬邑县。", font=f_mid, fill=(40, 38, 34))
d.text((40, 250), u"灵眸 OCR 面板端到端测试 2026-10-08", font=f_mid, fill=(90, 86, 78))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_panel_test.png")
img.save(out)
print("->", out)
