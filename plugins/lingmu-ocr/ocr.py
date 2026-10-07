# -*- coding: utf-8 -*-
"""灵眸 OCR 引擎封装：新版 rapidocr（PP-OCRv6），惰性初始化，模型随包或首启自下载。
输出契约与历史管线一致: [{box:[8], text, conf}]
"""
import os
import threading

_engine = None
_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from rapidocr import RapidOCR
                _engine = RapidOCR()
    return _engine


def ocr_page(image_path):
    res = _get_engine()(image_path)
    boxes = res.boxes if res.boxes is not None else []
    txts = res.txts if res.txts is not None else []
    scores = res.scores if res.scores is not None else []
    lines = []
    for box, t, c in zip(boxes, txts, scores):
        try:
            flat = [round(float(x), 1) for x in box.flatten().tolist()]
        except Exception:
            flat = []
        lines.append({"box": flat, "text": str(t), "conf": round(float(c), 3)})
    if not lines:
        raise RuntimeError("empty ocr result")
    return lines
