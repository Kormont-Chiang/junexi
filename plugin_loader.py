# -*- coding: utf-8 -*-
"""六月息插件加载器: 扫描 plugins/ 目录, 按 manifest 注册蓝图+收集 nav 注入
不改现有任何路由; 加载失败的插件跳过并记录, 绝不拖垮主程序。
"""
import os
import json
import importlib.util
import traceback

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")


def load_plugins(app):
    """扫描 PLUGINS_DIR, 注册各插件 Blueprint。返回 nav 注入清单 [{tab,label,icon}]。"""
    nav_injects = []
    loaded = []
    skipped = []
    if not os.path.isdir(PLUGINS_DIR):
        return nav_injects, loaded, skipped
    for pid in sorted(os.listdir(PLUGINS_DIR)):
        pdir = os.path.join(PLUGINS_DIR, pid)
        mf = os.path.join(pdir, "manifest.json")
        if not os.path.isfile(mf):
            continue
        try:
            manifest = json.load(open(mf, encoding="utf-8"))
            if manifest.get("enabled", True) is False:
                skipped.append((pid, "disabled"))
                continue
            routes_ref = manifest.get("routes")
            if not routes_ref:
                skipped.append((pid, "no routes"))
                continue
            # routes_ref = "routes.py:bp"
            fname, var = routes_ref.split(":")
            fpath = os.path.join(pdir, fname)
            spec = importlib.util.spec_from_file_location("jx_plugin_%s" % pid, fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            bp = getattr(mod, var)
            app.register_blueprint(bp)
            nav = manifest.get("nav")
            if nav:
                nav_injects.append({
                    "tab": nav.get("tab", pid),
                    "label": nav.get("label", pid),
                    "icon": nav.get("icon", "🧩"),
                    "plugin": pid,
                })
            loaded.append(pid)
        except Exception as e:
            skipped.append((pid, "%s: %s" % (type(e).__name__, str(e)[:120])))
            traceback.print_exc()
    return nav_injects, loaded, skipped
