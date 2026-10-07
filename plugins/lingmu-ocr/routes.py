# -*- coding: utf-8 -*-
"""灵眸 OCR 插件路由：状态查询（引擎包可用性），供管理页与排障。
注意：不做引擎实初始化（惰性——首次 ocr_page 调用时才建引擎）。
"""
from flask import Blueprint, jsonify

bp = Blueprint("lingmu_ocr", __name__)


@bp.route("/api/plugins/lingmu-ocr/status", methods=["GET"])
def status():
    pkg_ok = False
    pkg_err = None
    try:
        import rapidocr  # noqa: F401
        pkg_ok = True
    except Exception as e:
        pkg_err = "%s: %s" % (type(e).__name__, str(e)[:160])
    return jsonify({
        "ok": True,
        "engine": "RapidOCR PP-OCRv6",
        "pkg_available": pkg_ok,
        "error": pkg_err,
        "lazy": True,
    })
