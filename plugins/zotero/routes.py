# -*- coding: utf-8 -*-
"""Zotero 联动插件: 本地 Zotero API 代理 + 最近阅读 + PDF 直读 + 笔记落盘。从 app.py 原样迁入。"""
import os
import re
import json
import glob as _glob
import datetime as _dt
import urllib.request
import urllib.parse as _up
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, jsonify, send_file

bp = Blueprint("zotero", __name__)


def _core(name, default=None):
    """惰性取核心 app 模块的全局名(足迹/常量)。插件加载时 app 已在 sys.modules。"""
    import sys as _sys
    m = _sys.modules.get("app")
    return getattr(m, name, default) if m else default


def _log_activity(act, label):
    """足迹代理到核心实现（保持单一日志路径）。"""
    f = _core("_log_activity")
    if f:
        f(act, label)


# ── Zotero 本地联动 ─────────────────────────────────────
ZOTERO_LOCAL = "http://localhost:23119"

def _zotero_get(path, params=None, timeout=4):
    import urllib.request, urllib.parse
    url = ZOTERO_LOCAL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

@bp.route("/api/zotero/status", methods=["GET"])
def zotero_status():
    import urllib.request
    try:
        req = urllib.request.Request(ZOTERO_LOCAL + "/connector/ping", headers={"Zotero-API-Version": "3"})
        with urllib.request.urlopen(req, timeout=2) as r:
            return jsonify({"ok": r.status == 200})
    except Exception as e:
        return jsonify({"ok": False, "detail": str(e)[:120]})

def _zotero_map_items(data):
    items = []
    for it in data:
        d = it.get("data", {})
        if d.get("itemType") == "attachment":
            continue
        names = []
        for c in d.get("creators", [])[:3]:
            nm = (c.get("lastName", "") or "") + (c.get("firstName", "") or "")
            if nm:
                names.append(nm)
        import re as _re
        _ym = _re.search(r"(\d{4})", d.get("date") or "")
        items.append({
            "key": it.get("key"),
            "title": d.get("title") or "(无题)",
            "itemType": d.get("itemType", ""),
            "year": _ym.group(1) if _ym else "",
            "creators": "、".join(names),
            "select": "zotero://select/library/items/%s" % it.get("key"),
            "url": d.get("url", "") or "",
        })
    return items

@bp.route("/api/zotero/recent", methods=["GET"])
def zotero_recent():
    limit = min(int(request.args.get("limit", 8)), 20)
    try:
        s, data = _zotero_get("/api/users/0/items", {
            "itemType": "-attachment", "limit": limit,
            "sort": "dateAdded", "direction": "desc",
        })
        return jsonify({"ok": True, "total": len(data), "items": _zotero_map_items(data)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]})

REAL_TYPES = {"book", "journalArticle", "bookSection", "thesis", "report",
              "conferencePaper", "encyclopediaArticle", "document", "manuscript", "newspaperArticle"}

@bp.route("/api/zotero/library", methods=["GET"])
def zotero_library():
    """全库真文献(过滤 attachment/annotation/note), 分页拉全"""
    q = request.args.get("q", "").strip()
    try:
        all_items = []
        start = 0
        for _ in range(10):  # 最多 1000 条防护
            params = {"itemType": "-attachment", "limit": 100, "start": start,
                      "sort": "dateAdded", "direction": "desc"}
            if q:
                params["q"] = q
            s, data = _zotero_get("/api/users/0/items", params)
            if not isinstance(data, list) or not data:
                break
            for it in data:
                d = it.get("data", {})
                if d.get("itemType") in REAL_TYPES:
                    all_items.append(it)
            if len(data) < 100:
                break
            start += 100
        items = _zotero_map_items(all_items)
        # 客户端再过滤一遍(标题/作者/年份含关键词), 弥补 local API q 覆盖面
        if q:
            ql = q.lower()
            items = [x for x in items if ql in (x["title"] or "").lower()
                     or ql in (x["creators"] or "").lower()
                     or ql in (x["year"] or "")]
        return jsonify({"ok": True, "total": len(items), "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]})

@bp.route("/api/zotero/search", methods=["GET"])
def zotero_search():
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 12)), 25)
    if not q:
        return jsonify({"ok": False, "error": "empty q"}), 400
    try:
        s, data = _zotero_get("/api/users/0/items", {
            "q": q, "itemType": "-attachment", "limit": limit,
            "sort": "dateModified", "direction": "desc",
        })
        return jsonify({"ok": True, "total": len(data), "items": _zotero_map_items(data)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]})

# ── Obsidian 文件直写（读文献页笔记落盘用；不依赖 Local REST API 插件）──
def _vault_path():
    import json as _json
    cfg = os.path.expanduser(r"~\AppData\Roaming\obsidian\obsidian.json")
    try:
        d = _json.load(open(cfg, encoding="utf-8"))
        best = None
        for v in d.get("vaults", {}).values():
            if v.get("path", "").endswith(_core("OBSIDIAN_VAULT", "")):
                return v["path"]
            if best is None or v.get("ts", 0) > best.get("ts", 0):
                best = v
        return best["path"] if best else None
    except Exception:
        return None

def _safe_filename(s):
    import re as _re
    s = _re.sub(r'[\\/:*?"<>|\r\n]+', "_", s or "").strip(" .")
    return s[:80] or "untitled"

@bp.route("/api/zotero/item/<key>/attachments", methods=["GET"])
def zotero_item_attachments(key):
    try:
        s, data = _zotero_get("/api/users/0/items/%s/children" % key)
        atts = []
        for it in data:
            d = it.get("data", {})
            if d.get("itemType") == "attachment":
                atts.append({
                    "key": it.get("key"),
                    "title": d.get("title", ""),
                    "contentType": d.get("contentType", ""),
                    "isPdf": d.get("contentType") == "application/pdf",
                    "open": "zotero://open-pdf/library/items/%s" % it.get("key"),
                    "select": "zotero://select/library/items/%s" % key,
                })
        return jsonify({"ok": True, "attachments": atts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]})

@bp.route("/api/obsidian/zotero-note", methods=["POST"])
def obsidian_zotero_note():
    payload = request.get_json(force=True, silent=True) or {}
    title = (payload.get("title") or "").strip()
    content = payload.get("content") or ""
    meta = payload.get("meta") or {}
    if not content.strip():
        return jsonify({"ok": False, "error": "empty content"}), 400
    vault = _vault_path()
    if not vault or not os.path.isdir(vault):
        return jsonify({"ok": False, "error": "vault not found"}), 500
    folder = os.path.join(vault, "文献笔记")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return jsonify({"ok": False, "error": "mkdir: %s" % e}), 500
    fname = _safe_filename(title) + ".md"
    path = os.path.join(folder, fname)
    import datetime as _dt
    fm = [
        "---",
        "title: \"%s\"" % (title.replace('"', "'")),
    ]
    if meta.get("creators"):
        fm.append("authors: \"%s\"" % meta["creators"].replace('"', "'"))
    if meta.get("year"):
        fm.append("year: %s" % meta["year"])
    if meta.get("itemType"):
        fm.append("type: %s" % meta["itemType"])
    if meta.get("zoteroKey"):
        fm.append("zotero_key: %s" % meta["zoteroKey"])
        fm.append("zotero: \"zotero://select/library/items/%s\"" % meta["zoteroKey"])
    fm.append("created: %s" % _dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    fm.append("tags: [文献笔记]")
    fm.append("---")
    fm.append("")
    body = "\n".join(fm) + "# " + title + "\n\n"
    if meta.get("creators") or meta.get("year"):
        body += "> "
        if meta.get("creators"):
            body += meta["creators"]
        if meta.get("year"):
            body += (" · " if meta.get("creators") else "") + str(meta["year"])
        body += "\n\n"
    body += content.strip() + "\n"
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    except Exception as e:
        return jsonify({"ok": False, "error": "write: %s" % e}), 500
    import urllib.parse as _up
    obs_uri = "obsidian://open?vault=%s&file=%s" % (
        _up.quote(os.path.basename(vault)),
        _up.quote("文献笔记/" + fname))
    return jsonify({"ok": True, "path": path, "file": fname, "obsidian": obs_uri})

_RECENTLY_READ_CACHE = {"t": 0, "items": []}

@bp.route("/api/zotero/recently-read", methods=["GET"])
def zotero_recently_read():
    """最近阅读: 扫描 storage/*/.zotero-reader-state 的 mtime, 映射回 parent 题录。
    Zotero 本地 API 串行慢(每个~2.7s), 并发查 + 60s 缓存"""
    limit = min(int(request.args.get("limit", 5)), 10)
    now = __import__("time").time()
    if now - _RECENTLY_READ_CACHE["t"] < 60 and _RECENTLY_READ_CACHE["items"]:
        return jsonify({"ok": True, "items": _RECENTLY_READ_CACHE["items"][:limit], "cached": True})
    datadir = _zotero_datadir()
    if not datadir:
        return jsonify({"ok": False, "error": "no datadir", "items": []})
    import glob as _glob
    import datetime as _dt
    import re as _re
    from concurrent.futures import ThreadPoolExecutor
    hits = []
    for f in _glob.glob(os.path.join(datadir, "storage", "*", ".zotero-reader-state")):
        try:
            hits.append((os.stat(f).st_mtime, os.path.basename(os.path.dirname(f))))
        except Exception:
            pass
    hits.sort(reverse=True)

    def _one(hit):
        mt, att_key = hit
        try:
            s, data = _zotero_get("/api/users/0/items/%s" % att_key, timeout=10)
            ad = data.get("data", {})
            parent = ad.get("parentItem")
            if parent:
                s2, pdata = _zotero_get("/api/users/0/items/%s" % parent, timeout=10)
                pd = pdata.get("data", {})
                if pd.get("itemType") == "attachment" or not pd.get("title"):
                    return None
                ym = _re.search(r"(1[0-9]{3}|20[0-9]{2})", pd.get("date") or "")
                names = []
                for c in pd.get("creators", [])[:2]:
                    nm = ((c.get("lastName", "") or "") + " " + (c.get("firstName", "") or "")).strip()
                    if nm:
                        names.append(nm)
                return {
                    "key": parent, "att_key": att_key,
                    "title": pd.get("title") or "(无题)",
                    "creators": "、".join(names),
                    "year": ym.group(1) if ym else "",
                    "read_at": _dt.datetime.fromtimestamp(mt).strftime("%m-%d %H:%M"),
                }
            # standalone attachment(无父条目): 用文件名当标题
            title = (ad.get("title") or "").strip()
            if not title:
                return None
            return {
                "key": "", "att_key": att_key,
                "title": title.replace(".pdf", ""),
                "creators": "", "year": "",
                "read_at": _dt.datetime.fromtimestamp(mt).strftime("%m-%d %H:%M"),
            }
        except Exception:
            return None

    pool = hits[:limit * 2]
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_one, pool))
    items, seen = [], set()
    for r in results:
        if r and r["key"] not in seen:
            seen.add(r["key"])
            items.append(r)
        if len(items) >= limit:
            break
    _RECENTLY_READ_CACHE["t"] = now
    _RECENTLY_READ_CACHE["items"] = items
    return jsonify({"ok": True, "items": items})

_ZOTERO_PREF_CACHE = {}
def _zotero_pref(name):
    if name in _ZOTERO_PREF_CACHE:
        return _ZOTERO_PREF_CACHE[name]
    import glob as _glob
    import re as _re
    val = None
    for f in _glob.glob(os.path.expanduser(r"~\AppData\Roaming\Zotero\Zotero\Profiles\*\prefs.js")):
        try:
            t = open(f, encoding="utf-8", errors="ignore").read()
            m = _re.search(_re.escape(name) + r'",\s*"([^"]+)"', t)
            if m:
                val = m.group(1).replace("\\\\", "\\")
                break
        except Exception:
            pass
    _ZOTERO_PREF_CACHE[name] = val
    return val

def _zotero_datadir():
    d = _zotero_pref("extensions.zotero.dataDir")
    if d and os.path.isdir(os.path.join(d, "storage")):
        return d
    for c in (os.path.expanduser(r"~\Zotero"), os.path.expanduser(r"~\Documents\Zotero")):
        if os.path.isdir(os.path.join(c, "storage")):
            return c
    return None

def _attachment_path(att_key, data):
    """Zotero path 字段三种形态: storage:xx(imported) / attachments:xx(linked, 基准目录下) / 绝对路径"""
    p = (data.get("path") or "").strip()
    if not p:
        # local API 不回传 path: imported_file 走 storage/<key>/<filename>
        if data.get("linkMode") == "imported_file" and data.get("filename"):
            datadir = _zotero_datadir()
            if datadir:
                fp = os.path.join(datadir, "storage", att_key, data["filename"])
                if os.path.isfile(fp):
                    return fp
        return None
    import re as _re
    if p.lower().startswith("storage:"):
        datadir = _zotero_datadir()
        rel = p.split(":", 1)[1]
        return os.path.join(datadir, "storage", att_key, rel) if datadir else None
    if _re.match(r"^[A-Za-z]:[\\/]|^\\\\", p):
        return p
    if p.lower().startswith("attachments:"):
        rel = p.split(":", 1)[1]
        cands = []
        base = _zotero_pref("extensions.zotero.baseAttachmentPath")
        if base:
            cands.append(os.path.join(base, rel))
        datadir = _zotero_datadir()
        if datadir:
            cands.append(os.path.join(datadir, rel))
            cands.append(os.path.join(datadir, "attachments", rel))
        return next((c for c in cands if os.path.isfile(c)), None)
    return None

@bp.route("/api/zotero/pdf/<att_key>", methods=["GET"])
def zotero_pdf(att_key):
    try:
        s, data = _zotero_get("/api/users/0/items/%s" % att_key)
        d = data.get("data", {})
        if d.get("itemType") != "attachment":
            return jsonify({"ok": False, "error": "not attachment"}), 404
        fp = _attachment_path(att_key, d)
        if not fp or not os.path.isfile(fp):
            return jsonify({"ok": False, "error": "file not found"}), 404
        _log_activity("read", (d.get("title") or "PDF").replace(".pdf", "")[:60])
        return send_file(fp, mimetype="application/pdf", conditional=True)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]}), 500
