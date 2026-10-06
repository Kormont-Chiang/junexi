# -*- coding: utf-8 -*-
"""学术动态插件: arXiv + PubMed 认知科学源, 30min 缓存+磁盘兜底。
从 app.py 整体搬迁(第一刀插件化试点); URL 无 prefix 保持兼容。
"""
import os
import json
from flask import Blueprint, request, jsonify

bp = Blueprint("acad_feed", __name__)

_ACAD_FEED_CACHE = {"ts": 0.0, "items": [], "err": ""}
_ACAD_FEED_TTL = 1800  # 30 分钟
_ACAD_FEED_DISK = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "JuneXi", "acad_feed.json")


def _feed_disk_load():
    try:
        if os.path.isfile(_ACAD_FEED_DISK):
            d = json.loads(open(_ACAD_FEED_DISK, encoding="utf-8").read())
            if d.get("items"):
                _ACAD_FEED_CACHE.update({"ts": float(d.get("ts", 0)), "items": d["items"]})
    except Exception:
        pass


def _feed_disk_save():
    try:
        os.makedirs(os.path.dirname(_ACAD_FEED_DISK), exist_ok=True)
        open(_ACAD_FEED_DISK, "w", encoding="utf-8").write(json.dumps(
            {"ts": _ACAD_FEED_CACHE["ts"], "items": _ACAD_FEED_CACHE["items"]}, ensure_ascii=False))
    except Exception:
        pass


_feed_disk_load()

_CUSTOM_SRC_FILE = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "JuneXi", "acad_feed_sources.json")

def _custom_load():
    try:
        if os.path.isfile(_CUSTOM_SRC_FILE):
            d = json.loads(open(_CUSTOM_SRC_FILE, encoding="utf-8").read())
            if isinstance(d, list):
                return [s for s in d if isinstance(s, dict) and (s.get("url") or "").startswith("https://")]
    except Exception:
        pass
    return []

def _custom_save(lst):
    try:
        os.makedirs(os.path.dirname(_CUSTOM_SRC_FILE), exist_ok=True)
        open(_CUSTOM_SRC_FILE, "w", encoding="utf-8").write(json.dumps(lst, ensure_ascii=False))
    except Exception:
        pass


def _ts():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _arxiv_fetch(query, max_n):
    import urllib.request as _ur
    import xml.etree.ElementTree as _ET
    url = ("http://export.arxiv.org/api/query?search_query=%s"
           "&sortBy=submittedDate&sortOrder=descending&max_results=%d" % (query, max_n))
    req = _ur.Request(url, headers={"User-Agent": "JuneXi-AcademicFeed/1.0"})
    with _ur.urlopen(req, timeout=15) as r:
        root = _ET.fromstring(r.read())
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    for e in root.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        summ = " ".join((e.findtext("a:summary", "", ns) or "").split())
        pub = (e.findtext("a:published", "", ns) or "")[:10]
        link = e.findtext("a:id", "", ns) or ""
        authors = [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)]
        if title:
            items.append({"title": title, "source": "arXiv", "date": pub,
                          "abstract": summ, "url": link,
                          "authors": ", ".join([x for x in authors if x][:3])})
    return items


def _pubmed_fetch(term, max_n):
    import urllib.request as _ur
    import urllib.parse as _up
    import xml.etree.ElementTree as _ET
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    q = _up.urlencode({"db": "pubmed", "term": term, "sort": "date",
                       "retmax": max_n, "retmode": "json"})
    req = _ur.Request(base + "esearch.fcgi?" + q, headers={"User-Agent": "JuneXi-AcademicFeed/1.0"})
    with _ur.urlopen(req, timeout=15) as r:
        ids = (json.loads(r.read().decode("utf-8", "ignore")).get("esearchresult", {}) or {}).get("idlist", [])
    if not ids:
        return []
    req2 = _ur.Request(base + "efetch.fcgi?" + _up.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}),
                       headers={"User-Agent": "JuneXi-AcademicFeed/1.0"})
    with _ur.urlopen(req2, timeout=20) as r:
        root = _ET.fromstring(r.read())
    items = []
    for art in root.iter("PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
        title = " ".join(title.split())
        parts = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            txt = " ".join("".join(ab.itertext()).split())
            if txt:
                parts.append((label + ": " + txt) if label else txt)
        abstract = " ".join(parts)
        _MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
                "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
        y = art.findtext(".//PubDate/Year") or art.findtext(".//PubDate/MedlineDate") or ""
        mraw = (art.findtext(".//PubDate/Month") or "").strip().lower()
        m = _MON.get(mraw[:3], mraw if mraw.isdigit() else "")
        d = art.findtext(".//PubDate/Day") or ""
        date = (y[:4] + "-" + m.zfill(2) + "-" + d.zfill(2)).strip("-") if y else ""
        authors = []
        for au in art.findall(".//AuthorList/Author")[:3]:
            ln = au.findtext("LastName") or ""
            ini = au.findtext("Initials") or ""
            if ln:
                authors.append(ln + (" " + ini if ini else ""))
        if title:
            items.append({"title": title, "source": "PubMed", "date": date[:10],
                          "abstract": abstract, "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
                          "authors": ", ".join(authors)})
    return items


def _rss_fetch(url, source, max_n):
    """通用 RSS2.0/Atom 抓取: title/link/pubDate|published/description 截断"""
    import re as _re
    import urllib.request as _ur
    import xml.etree.ElementTree as _ET
    req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JuneXi/1.0"})
    with _ur.urlopen(req, timeout=15) as r:
        root = _ET.fromstring(r.read())
    def _strip(tag):
        return _re.sub(r"<[^>]+>", "", tag or "").strip()
    def _short(t, n=280):
        t = " ".join((t or "").split())
        return t[:n] + ("……" if len(t) > n else "")
    items = []
    # RSS 2.0
    for it in root.iter("item"):
        title = _strip(it.findtext("title"))
        link = _strip(it.findtext("link"))
        date = (_strip(it.findtext("pubDate")) or _strip(it.findtext("date")))[:16]
        desc = _short(_strip(it.findtext("description")))
        if title:
            items.append({"title": title, "source": source, "date": date,
                          "abstract": desc, "url": link, "authors": ""})
        if len(items) >= max_n:
            return items
    if items:
        return items
    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in root.findall("a:entry", ns):
        title = _strip(e.findtext("a:title", "", ns))
        link = ""
        for lk in e.findall("a:link", ns):
            if lk.get("rel", "alternate") == "alternate":
                link = lk.get("href", "")
                break
        date = (_strip(e.findtext("a:published", "", ns)) or _strip(e.findtext("a:updated", "", ns)))[:16]
        desc = _short(_strip(e.findtext("a:summary", "", ns) or e.findtext("a:content", "", ns)))
        if title:
            items.append({"title": title, "source": source, "date": date,
                          "abstract": desc, "url": link, "authors": ""})
        if len(items) >= max_n:
            break
    return items


@bp.route("/api/academic-feed", methods=["GET"])
def academic_feed():
    """学术动态: 数字人文(arXiv)+世界史/学术写作(RSS) 多源, 30min 缓存, 过期缓存兜底"""
    import time as _time
    force = request.args.get("refresh") == "1"
    now = _time.time()
    if not force and now - _ACAD_FEED_CACHE["ts"] < _ACAD_FEED_TTL and _ACAD_FEED_CACHE["items"]:
        return jsonify({"ok": True, "items": _ACAD_FEED_CACHE["items"], "cached": True,
                        "fetched_at": _ts()})
    items, errs = [], []
    from concurrent.futures import ThreadPoolExecutor
    _jobs = [
        ("arXiv(数字人文)", lambda: _arxiv_fetch("all:%22digital+humanities%22+AND+cat:cs.DL", 3)),
        ("arXiv(历史时空)", lambda: _arxiv_fetch("all:%22digital+history%22", 3)),
        ("Medievalists.net", lambda: _rss_fetch("https://www.medievalists.net/feed/", "Medievalists", 3)),
        ("JSTOR Daily", lambda: _rss_fetch("https://daily.jstor.org/feed/", "JSTOR Daily", 3)),
    ]
    for _cs in _custom_load():
        _cu = (_cs.get("url") or "").strip()
        _cn = (_cs.get("name") or "").strip() or _cu
        _jobs.append((_cn, (lambda u=_cu, n=_cn: _rss_fetch(u, n, 3))))
    with ThreadPoolExecutor(max_workers=3) as _ex:
        _futs = {_ex.submit(fn): name for name, fn in _jobs}
        for fut, name in [(f, _futs[f]) for f in _futs]:
            try:
                items += fut.result(timeout=40)
            except Exception as ex:
                errs.append("%s: %s" % (name, ex))
    seen, merged = set(), []
    for it in sorted(items, key=lambda x: x.get("date", ""), reverse=True):
        key = it["title"][:60].lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(it)
    merged = merged[:10]
    if merged:
        _ACAD_FEED_CACHE.update({"ts": now, "items": merged, "err": "; ".join(errs)})
        _feed_disk_save()
        return jsonify({"ok": True, "items": merged, "cached": False, "partial": bool(errs),
                        "fetched_at": _ts()})
    if _ACAD_FEED_CACHE["items"]:
        return jsonify({"ok": True, "items": _ACAD_FEED_CACHE["items"], "stale": True,
                        "error": "; ".join(errs)[:200]})
    return jsonify({"ok": False, "items": [], "error": "; ".join(errs)[:200] or "网络抓取失败"})


@bp.route("/api/academic-feed/sources", methods=["GET", "POST"])
def custom_sources():
    """自定义 RSS 源: GET 列表 / POST 添加 {name,url}"""
    if request.method == "GET":
        return jsonify({"ok": True, "sources": _custom_load()})
    d = request.get_json(force=True) or {}
    url = (d.get("url") or "").strip()
    name = (d.get("name") or "").strip() or url
    if not url.startswith("https://"):
        return jsonify({"ok": False, "error": "仅支持 https:// 的 RSS 地址"}), 400
    lst = _custom_load()
    if any(s.get("url") == url for s in lst):
        return jsonify({"ok": False, "error": "该源已在列表中"}), 400
    lst.append({"name": name, "url": url})
    _custom_save(lst)
    return jsonify({"ok": True, "sources": lst})

@bp.route("/api/academic-feed/sources/<int:idx>", methods=["DELETE"])
def custom_source_del(idx):
    lst = _custom_load()
    if 0 <= idx < len(lst):
        lst.pop(idx)
        _custom_save(lst)
    return jsonify({"ok": True, "sources": lst})
