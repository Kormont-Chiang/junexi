# -*- coding: utf-8 -*-
"""示例插件: 验证加载链路。URL 前缀 /<plugin_id>/ 防冲突。"""
from flask import Blueprint, jsonify

bp = Blueprint("_example", __name__, url_prefix="/plugin/_example")


@bp.route("/ping")
def ping():
    return jsonify({"ok": True, "plugin": "_example", "msg": "插件链路通"})
