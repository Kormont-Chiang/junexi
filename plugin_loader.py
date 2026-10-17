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

# R101c: 插件加载异常记录 {pid: 简短异常}, 供 /api/plugins skip_reason 透出(frozen stderr 不可见)
_LOAD_ERRORS = {}


def load_errors():
    return dict(_LOAD_ERRORS)


def user_plugins_dir():
    """用户插件目录(可写, 插件市场安装目标)。"""
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JuneXi", "plugins")
    os.makedirs(d, exist_ok=True)
    return d


def all_plugin_dirs():
    """[用户目录(优先), 内置目录]; 同名插件用户目录覆盖内置。"""
    return [user_plugins_dir(), PLUGINS_DIR]

# 插件静态资源 {pid: {css:[url], js:[url]}}
_plugin_assets = {}
# R40c: 插件皮肤包 {pid: [css_url]}——manifest.theme.css 声明的额外 CSS
_plugin_themes = {}


def plugin_assets():
    return dict(_plugin_assets)


def plugin_themes():
    return dict(_plugin_themes)


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
    """原子写入：先写临时文件再重命名，防止写入中断损坏 JSON。"""
    tmp = _overrides_path() + ".tmp"
    json.dump(ov, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, _overrides_path())


def effective_enabled(manifest, plugin_id, overrides):
    """用户覆盖优先于 manifest 默认。"""
    if plugin_id in overrides and "enabled" in overrides[plugin_id]:
        return bool(overrides[plugin_id]["enabled"])
    return manifest.get("enabled", True) is not False


# ── R115: 插件参数配置(Obsidian 式声明设置) ──
# manifest.settings.fields 声明字段, 用户值存 %LOCALAPPDATA%\JuneXi\plugin-config.json
_MANIFESTS = {}


def _config_path():
    return os.path.join(_user_data_dir(), "plugin-config.json")


def load_config():
    try:
        return json.load(open(_config_path(), encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg):
    tmp = _config_path() + ".tmp"
    json.dump(cfg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, _config_path())


def plugin_manifest(pid):
    return _MANIFESTS.get(pid) or {}


def get_plugin_config(pid, manifest=None):
    """合并 manifest 声明的 default 与用户已存值 → {key: value}。只收声明过的字段。"""
    mf = manifest if manifest is not None else plugin_manifest(pid)
    fields = ((mf or {}).get("settings") or {}).get("fields") or []
    stored = (load_config().get(pid) or {})
    out = {}
    for f in fields:
        k = f.get("key")
        if not k:
            continue
        out[k] = stored[k] if k in stored else f.get("default")
    return out


def validate_plugin_config(pid, updates, manifest=None):
    """按声明校验+清洗 updates → (clean_dict, error)。error 非空即拒绝。"""
    mf = manifest if manifest is not None else plugin_manifest(pid)
    fields = {f.get("key"): f for f in (((mf or {}).get("settings") or {}).get("fields") or []) if f.get("key")}
    clean = {}
    for k, v in (updates or {}).items():
        f = fields.get(k)
        if not f:
            return {}, u"未声明的字段: %s" % k
        t = f.get("type", "text")
        try:
            if t == "bool":
                clean[k] = bool(v)
            elif t == "int":
                iv = int(v)
                lo, hi = f.get("min"), f.get("max")
                if lo is not None:
                    iv = max(int(lo), iv)
                if hi is not None:
                    iv = min(int(hi), iv)
                clean[k] = iv
            elif t == "select":
                opts = [o.get("value") if isinstance(o, dict) else o for o in (f.get("options") or [])]
                if v not in opts:
                    return {}, u"%s 的可选值: %s" % (k, "/".join(map(str, opts)))
                clean[k] = v
            elif t == "password":
                clean[k] = str(v)[:500]
            else:  # text
                clean[k] = str(v)[:int(f.get("max_len") or 2000)]
        except Exception:
            return {}, u"字段 %s 类型不符(%s)" % (k, t)
    return clean, ""


def load_plugins(app):
    """扫描 PLUGINS_DIR, 注册各插件 Blueprint。返回 nav 注入清单 [{tab,label,icon}]。"""
    nav_injects = []
    loaded = []
    skipped = []
    overrides = load_overrides()
    seen = set()
    for base_dir in all_plugin_dirs():
        if not os.path.isdir(base_dir):
            continue
        for pid in sorted(os.listdir(base_dir)):
            if pid in seen:
                continue
            seen.add(pid)
            pdir = os.path.join(base_dir, pid)
            mf = os.path.join(pdir, "manifest.json")
            if not os.path.isfile(mf):
                continue
            try:
                manifest = json.load(open(mf, encoding="utf-8"))
                _MANIFESTS[pid] = manifest
                if not effective_enabled(manifest, pid, overrides):
                    skipped.append((pid, "disabled"))
                    continue
                routes_ref = manifest.get("routes")
                if not routes_ref:
                    skipped.append((pid, "no routes"))
                    continue
                fname, var = routes_ref.split(":")
                # R66: 防路径穿越——fname 必须在插件目录内
                fpath = os.path.realpath(os.path.join(pdir, fname))
                pdir_real = os.path.realpath(pdir)
                if not fpath.startswith(pdir_real + os.sep):
                    print(f"[plugins] {pid}: routes 文件路径越界,跳过")
                    skipped.append((pid, "path traversal"))
                    continue
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
                        # R66: warmup 同样防路径穿越
                        wpath = os.path.realpath(os.path.join(pdir, wf))
                        if not wpath.startswith(pdir_real + os.sep):
                            print(f"[plugins] {pid}: warmup 文件路径越界,跳过")
                            continue
                        wspec = importlib.util.spec_from_file_location("jx_plugin_%s_warmup" % pid, wpath)
                        wmod = importlib.util.module_from_spec(wspec)
                        _sys.modules["jx_plugin_%s_warmup" % pid] = wmod
                        wspec.loader.exec_module(wmod)
                        getattr(wmod, wv)(app)
                    except Exception:
                        import logging
                        logging.getLogger("jx.plugins").error(f"warmup failed: {pid}: {traceback.format_exc()}")
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
                # R40c: 插件皮肤包——manifest.theme 声明 {css:[文件名]}，写入 _plugin_themes 供前端注入
                theme = manifest.get("theme") or {}
                theme_css = [t for t in (theme.get("css") or []) if isinstance(t, str)]
                if os.path.isdir(sdir) and (css or js or theme_css):
                    import flask as _fl
                    bp_s = _fl.Blueprint("jx_pstatic_%s" % pid, __name__,
                                         static_folder=sdir, static_url_path="/plugin/%s/static" % pid)
                    app.register_blueprint(bp_s)

                    def _v(fname, _sd=sdir):
                        # R108c: assets URL 带 mtime 防缓存——插件 js 更新后浏览器自动失效旧缓存
                        try:
                            return int(os.path.getmtime(os.path.join(_sd, fname)))
                        except OSError:
                            return 0

                    _plugin_assets[pid] = {
                        "css": ["/plugin/%s/static/%s?v=%d" % (pid, c, _v(c)) for c in css],
                        "js": ["/plugin/%s/static/%s?v=%d" % (pid, j, _v(j)) for j in js],
                    }
                    if theme_css:
                        _plugin_themes[pid] = ["/plugin/%s/static/%s" % (pid, t) for t in theme_css]
                loaded.append(pid)
            except Exception as e:
                _LOAD_ERRORS[pid] = "%s: %s" % (type(e).__name__, str(e)[:160])
                skipped.append((pid, "%s: %s" % (type(e).__name__, str(e)[:120])))
                traceback.print_exc()
    return nav_injects, loaded, skipped
