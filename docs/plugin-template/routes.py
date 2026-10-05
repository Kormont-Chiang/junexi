# -*- coding: utf-8 -*-
"""最小插件示例: 一个路由 + 一个页面 + 足迹记录。
复制本文件夹到 plugins/<你的插件id>/ 即可被加载。
"""
import os
import json
import urllib.request
from flask import Blueprint, request, jsonify

bp = Blueprint("myplugin", __name__)


def _core(name, default=None):
    """从核心 app 取全局名(足迹/配置)。插件不 import app, 用惰性取保持解耦。"""
    import sys
    m = sys.modules.get("app")
    return getattr(m, name, default) if m else default


@bp.route("/api/myplugin/hello")
def hello():
    # 记录到"我的足迹"（复用核心日志）
    log = _core("_log_activity")
    if log:
        log("tool", "用了我的插件")
    return jsonify({"ok": True, "msg": "hello from myplugin"})


@bp.route("/api/myplugin/fetch-remote")
def fetch_remote():
    """permissions 声明 network 的插件可以访问网络——未声明就别做外链请求。"""
    url = request.args.get("url", "").strip()
    if not url.startswith("https://"):
        return jsonify({"ok": False, "error": "仅允许 https URL"}), 400
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JuneXi-myplugin/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return jsonify({"ok": True, "status": r.status, "head": r.read(300).decode("utf-8", "ignore")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]}), 500
