# -*- coding: utf-8 -*-
"""百度 OCR 插件：key 配置管理（存用户数据目录，永不入库）。
注意：插件文件由加载器以独立模块载入（非包），routes 不 import 同目录 ocr.py，
配置读写在此直操作同一 JSON 路径（与 ocr.py 的 _conf_path 保持一致）。
"""
import json
import os
from flask import Blueprint, request, jsonify

bp = Blueprint("baidu_ocr", __name__)

_CONF = os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "JuneXi", "baidu_ocr.json")


def _core(name, default=None):
    import sys
    m = sys.modules.get("app")
    return getattr(m, name, default) if m else default


def _read():
    try:
        with open(_CONF, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("api_key", ""), d.get("secret_key", "")
    except Exception:
        return "", ""


@bp.route("/api/plugins/baidu-ocr/config", methods=["GET"])
def get_config():
    ak, sk = _read()
    return jsonify({"ok": True, "configured": bool(ak and sk),
                    "api_key_tail": ak[-4:] if ak else ""})


@bp.route("/api/plugins/baidu-ocr/config", methods=["POST"])
def set_config():
    body = request.get_json(force=True) or {}
    ak = str(body.get("api_key", "")).strip()
    sk = str(body.get("secret_key", "")).strip()
    if not ak or not sk:
        return jsonify({"ok": False, "error": "api_key/secret_key required"}), 400
    os.makedirs(os.path.dirname(_CONF), exist_ok=True)
    with open(_CONF, "w", encoding="utf-8") as f:
        json.dump({"api_key": ak, "secret_key": sk}, f, ensure_ascii=False)
    log = _core("_log_activity")
    if log:
        log("plugin", "配置了百度 OCR")
    return jsonify({"ok": True})
