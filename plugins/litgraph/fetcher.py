# -*- coding: utf-8 -*-
"""OpenAlex 客户端: 种子检索 + 参考文献/被引/相关 自动扩展。
只用标准库(urllib), frozen 零新增依赖; 慢网络友好(timeout 60s x2 重试)。
API 文档: https://docs.openalex.org
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.openalex.org"
UA = "JuneXi litgraph/0.2 (mailto: junexi@example.org)"
TIMEOUT = 60
RETRIES = 2
BATCH = 25  # filter=openalex_id:...|... 单批上限(保守)

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)


def is_doi(q):
    return bool(_DOI_RE.match((q or "").strip()))


def _short_id(full_id):
    """'https://openalex.org/W123' -> 'W123'"""
    return (full_id or "").rstrip("/").rsplit("/", 1)[-1]


def _get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 4xx 确定性错误(除429限流)不重试; 5xx/429 走退避
            if e.code != 429 and 400 <= e.code < 500:
                raise
            last = e
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
        except Exception as e:
            last = e
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
    raise last


def norm_work(w):
    """OpenAlex work -> litgraph 题录结构(与 parser 输入对齐)。"""
    if not w:
        return None
    authors = []
    for a in (w.get("authorships") or [])[:3]:
        nm = (a.get("author") or {}).get("display_name")
        if nm:
            authors.append(nm)
    src = ""
    pl = w.get("primary_location") or {}
    if pl.get("source"):
        src = pl["source"].get("display_name") or ""
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    return {
        "title": w.get("display_name") or "",
        "authors": authors,
        "source": src,
        "year": str(w.get("publication_year") or ""),
        "oa_id": _short_id(w.get("id")),
        "doi": doi,
        "cited_by_count": w.get("cited_by_count") or 0,
        "n_refs_total": len(w.get("referenced_works") or []),
        "type": w.get("type") or "",
    }


def search_works(query, limit=5):
    """标题/DOI -> (候选题录列表, 命中总数)。DOI 精确直达。"""
    q = (query or "").strip()
    if not q:
        return [], 0
    if is_doi(q):
        try:
            w = _get("/works/doi:" + q)
            return [norm_work(w)], 1
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return [], 0  # DOI 不在库 ≠ 网络故障
            raise
    d = _get("/works", {
        "filter": "title.search:" + q,
        "per-page": str(min(limit, 25)),
        "select": "id,display_name,authorships,primary_location,publication_year,doi,cited_by_count,type",
    })
    out = [norm_work(w) for w in (d.get("results") or [])]
    return [o for o in out if o], d.get("meta", {}).get("count") or 0


def get_work(oa_id):
    """单篇完整 work(含 referenced_works 全文 ID 列表)。"""
    d = _get("/works/" + urllib.parse.quote(_short_id(oa_id)))
    return d


def get_works_batch(oa_ids):
    """按 ID 批量取元数据, 内部自动分批。返回 [题录]。"""
    ids = [_short_id(i) for i in (oa_ids or []) if i]
    out = []
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        d = _get("/works", {
            "filter": "openalex_id:" + "|".join(chunk),
            "per-page": str(len(chunk)),
            "select": "id,display_name,authorships,primary_location,publication_year,doi,cited_by_count,type",
        })
        out += [norm_work(w) for w in (d.get("results") or [])]
    return [o for o in out if o and o.get("title")]


def get_cited_by(oa_id, limit=50):
    """(被引总命中数, [题录])。按被引数降序取前 limit。"""
    sid = _short_id(oa_id)
    d = _get("/works", {
        "filter": "cites:" + sid,
        "sort": "cited_by_count:desc",
        "per-page": str(min(limit, 200)),
        "select": "id,display_name,authorships,primary_location,publication_year,doi,cited_by_count,type",
    })
    meta = d.get("meta") or {}
    out = [norm_work(w) for w in (d.get("results") or [])]
    return meta.get("count") or 0, [o for o in out if o]


def get_related(oa_id, limit=20):
    """相关文献(≈Scholar 的 related articles)。返回 [题录]。"""
    sid = _short_id(oa_id)
    w = _get("/works/" + urllib.parse.quote(sid),
             {"select": "related_works"})
    rel = (w.get("related_works") or [])[:limit]
    return get_works_batch(rel)
