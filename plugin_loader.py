# -*- coding: utf-8 -*-
"""六月息插件加载器: 扫描 plugins/ 目录, 按 manifest 注册蓝图+收集 nav 注入
- frozen(PyInstaller) 下 plugins/ 随包分发在 _MEIPASS(只读)
- 开关等用户覆盖写到 %LOCALAPPDATA%\\JuneXi\\plugin-overrides.json
- 不改现有任何路由; 加载失败的插件跳过并记录, 绝不拖垮主程序。
"""
import os
import sys
import json
import importlib.util
import traceback


def _plugins_dir():
    """frozen(PyInstaller) 下数据在 _MEIPASS; 开发态用源码根。"""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "plugins")


PLUGINS_DIR = _plugins_dir()

# 插件静态资源 {pid: {css:[url], js:[url]}}
_plugin_assets = {}


def plugin_assets():
    return dict(_plugin_assets)


def _user_data_dir():
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JuneXi")
    os.makedirs(d, exist_ok=True)
    return d


def _overrides_path():
    return os.path.join(_user_data_dir(), "plugin-overrides.json")


def load_overrides():
    try:
        return json.load(open(_overrides_path(), encoding="utf-8"))
    except Exception:
        return {}


def save_overrides(ov):
    json.dump(ov, open(_overrides_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def effective_enabled(manifest, plugin_id, overrides):
    """用户覆盖优先于 manifest 默认。"""
    if plugin_id in overrides and "enabled" in overrides[plugin_id]:
        return bool(overrides[plugin_id]["enabled"])
    return manifest.get("enabled", True) is not False


def load_plugins(app):
    """扫描 PLUGINS_DIR, 注册各插件 Blueprint。返回 nav 注入清单 [{tab,label,icon}]。"""
    nav_injects = []
    loaded = []
    skipped = []
    overrides = load_overrides()
    if not os.path.isdir(PLUGINS_DIR):
        return nav_injects, loaded, skipped
    for pid in sorted(os.listdir(PLUGINS_DIR)):
        pdir = os.path.join(PLUGINS_DIR, pid)
        mf = os.path.join(pdir, "manifest.json")
        if not os.path.isfile(mf):
            continue
        try:
            manifest = json.load(open(mf, encoding="utf-8"))
            if not effective_enabled(manifest, pid, overrides):
                skipped.append((pid, "disabled"))
                continue
            routes_ref = manifest.get("routes")
            if not routes_ref:
                skipped.append((pid, "no routes"))
                continue
            fname, var = routes_ref.split(":")
            fpath = os.path.join(pdir, fname)
            spec = importlib.util.spec_from_file_location("jx_plugin_%s" % pid, fpath)
            mod = importlib.util.module_from_spec(spec)
            # 插件内模块互引(如 warmup.py 的 from routes import X): 先注册到 sys.modules
            import sys as _sys
            _sys.modules["jx_plugin_%s" % pid] = mod
            spec.loader.exec_module(mod)
            bp = getattr(mod, var)
            app.register_blueprint(bp)
            # manifest warmup 钩子(可选): "warmup.py:run", 加载后立即调用
            warm_ref = manifest.get("warmup")
            if warm_ref:
                try:
                    wf, wv = warm_ref.split(":")
                    wpath = os.path.join(pdir, wf)
                    wspec = importlib.util.spec_from_file_location("jx_plugin_%s_warmup" % pid, wpath)
                    wmod = importlib.util.module_from_spec(wspec)
                    _sys.modules["jx_plugin_%s_warmup" % pid] = wmod
                    wspec.loader.exec_module(wmod)
                    getattr(wmod, wv)(app)
                except Exception:
                    traceback.print_exc()
            nav = manifest.get("nav")
            if nav:
                nav_injects.append({
                    "tab": nav.get("tab", pid),
                    "label": nav.get("label", pid),
                    "icon": nav.get("icon", "🧩"),
                    "plugin": pid,
                })
            # 插件静态资源: manifest assets {css:[], js:[]} + /plugin/<id>/static/<path> 伺服
            sdir = os.path.join(pdir, "static")
            assets = manifest.get("assets") or {}
            css = [c for c in (assets.get("css") or []) if isinstance(c, str)]
            js = [j for j in (assets.get("js") or []) if isinstance(j, str)]
            if os.path.isdir(sdir) and (css or js):
                import flask as _fl
                bp_s = _fl.Blueprint("jx_pstatic_%s" % pid, __name__,
                                     static_folder=sdir, static_url_path="/plugin/%s/static" % pid)
                app.register_blueprint(bp_s)
                _plugin_assets[pid] = {
                    "css": ["/plugin/%s/static/%s" % (pid, c) for c in css],
                    "js": ["/plugin/%s/static/%s" % (pid, j) for j in js],
                }
            loaded.append(pid)
        except Exception as e:
            skipped.append((pid, "%s: %s" % (type(e).__name__, str(e)[:120])))
            traceback.print_exc()
    return nav_injects, loaded, skipped
