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


@bp.route("/api/academic-feed", methods=["GET"])
def academic_feed():
    """认知科学学术动态: arXiv + PubMed 双源, 30min 缓存, 过期缓存兜底"""
    import time as _time
    force = request.args.get("refresh") == "1"
    now = _time.time()
    if not force and now - _ACAD_FEED_CACHE["ts"] < _ACAD_FEED_TTL and _ACAD_FEED_CACHE["items"]:
        return jsonify({"ok": True, "items": _ACAD_FEED_CACHE["items"], "cached": True,
                        "fetched_at": _ts()})
    items, errs = [], []
    from concurrent.futures import ThreadPoolExecutor
    _jobs = [
        ("arXiv(cogsci)", lambda: _arxiv_fetch("all:%22cognitive+science%22", 4)),
        ("arXiv(q-bio.NC)", lambda: _arxiv_fetch("cat:q-bio.NC", 3)),
        ("PubMed", lambda: _pubmed_fetch('("cognitive science"[Title/Abstract] OR "cognitive neuroscience"[Title/Abstract])', 5)),
    ]
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
