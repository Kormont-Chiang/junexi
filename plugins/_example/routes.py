# -*- coding: utf-8 -*-
"""示例插件: 验证加载链路 + 页面注入。"""
from flask import Blueprint, jsonify

bp = Blueprint("_example", __name__, url_prefix="/plugin/_example")


@bp.route("/ping")
def ping():
    return jsonify({"ok": True, "plugin": "_example", "msg": "插件链路通"})


@bp.route("/page")
def page():
    return """<div style="padding:24px">
  <h3 style="margin:0 0 12px;color:var(--accent,#c9a96e)">🧩 插件示例页</h3>
  <p style="line-height:1.9;font-size:13px;opacity:.85">这个页面由 <code>plugins/_example/routes.py</code> 的 <code>/page</code> 端点提供,
  通过 nav「插件示例」注入加载——这就是未来每个插件向前端呈现自己的方式。</p>
  <p style="line-height:1.9;font-size:13px;opacity:.85">插件 = 一个文件夹(manifest + routes + 静态资源),
  装/卸 = 增删文件夹。开关在「插件管理」面板。</p>
</div>"""
