# -*- coding: utf-8 -*-
"""实体标注（二期 词典锚定）：OCR/句读文本 × 自家词库 = 可点词条

词库 = 工具书 + CBDB：
- 年号（二十史朔闰表 3715 别名）——同位优先 + 纪年尾词抑制
- 地名（中国历史地名大辞典 ~6.9 万）
- 官名 / 人名（CBDB 5.3 万人、3.4 万官职）——点击弹生卒朝代，可接 CBDB 详情

匹配：era 桶先查；其余 lex 桶（place/office/person 合并）按长度降序最长匹配。
数据文件按签名热更新（投放新词库无需重启）。
"""
import io
import json
import os
import pickle
import threading

_LOCK = threading.Lock()
_STATE = {"sig": None, "index": None, "stats": {}}
_YEARISH = u"元一二三四五六七八九十百千〇零0123456789"

TOOLBOOK_DIR_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "toolbooks"),
]


def _toolbook_dir():
    for c in TOOLBOOK_DIR_CANDIDATES:
        if os.path.isdir(c):
            return c
    return TOOLBOOK_DIR_CANDIDATES[0]


def _sig():
    d = _toolbook_dir()
    out = []
    for fn in ("diming_clean.jsonl", "nianhao_clean.jsonl",
               "cbdb_persons.jsonl", "cbdb_offices.jsonl", "cbdb_places.jsonl"):
        p = os.path.join(d, fn)
        out.append((fn, os.path.getsize(p) if os.path.isfile(p) else 0,
                    int(os.path.getmtime(p)) if os.path.isfile(p) else 0))
    return tuple(out)


def _load_jsonl(path):
    if not os.path.isfile(path):
        return
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except Exception:
                continue


_T2S = None


def _t2s(s):
    """CBDB 官名为繁体，转简索引；失败原样返回。"""
    global _T2S
    if _T2S is None:
        try:
            from opencc import OpenCC
            _T2S = OpenCC("t2s")
        except Exception:
            _T2S = False
    if _T2S is False:
        return s
    try:
        return _T2S.convert(s)
    except Exception:
        return s


_TYPE_PRIO = {u"人名": 0, u"官名": 1, u"地名": 2}


def _build():
    idx = {}
    stats = {}
    d = _toolbook_dir()

    def add(bucket, surface, etype, book, head, gloss, ref=None):
        surface = (surface or "").strip()
        if len(surface) < 2:
            return
        b = idx.setdefault(surface[0], {"era": [], "lex": []})
        ent = (surface, etype, book, head, gloss, ref)
        b[bucket].append(ent)

    # 年号
    n = 0
    for e in _load_jsonl(os.path.join(d, "nianhao_clean.jsonl")):
        gloss = e.get("year_span") or ""
        ruler = (e.get("ruler") or "").strip()
        note = (e.get("note") or "").strip()
        snippet = note[:80] if note else ""
        for era in (e.get("eras") or []):
            era = (era or "").strip()
            if era:
                add("era", era, u"年号", u"二十史朔闰表", era,
                    (gloss + " " + snippet).strip() or ruler)
                n += 1
    stats["nianhao_eras"] = n

    # 地名
    n = 0
    for e in _load_jsonl(os.path.join(d, "diming_clean.jsonl")):
        head = (e.get("head") or "").strip()
        if head:
            add("lex", head, u"地名", u"中国历史地名大辞典", head, (e.get("note") or "")[:80])
            n += 1
    stats["diming_heads"] = n

    # 地名补（CBDB ADDR_CODES 繁体库，简繁双索引补缺口如「洛阳/洛陽」；地名典优先）
    n = 0
    for e in _load_jsonl(os.path.join(d, "cbdb_places.jsonl")):
        head = (e.get("head") or "").strip()
        if head:
            for surf in {head, _t2s(head)}:
                add("lex", surf, u"地名", u"CBDB 地名", head, u"", e.get("aid"))
            n += 1
    stats["cbdb_places"] = n

    # 官名（CBDB，繁体→简繁双索引）
    n = 0
    for e in _load_jsonl(os.path.join(d, "cbdb_offices.jsonl")):
        head = (e.get("head") or "").strip()
        if head:
            for surf in {head, _t2s(head)}:
                add("lex", surf, u"官名", u"CBDB 历代官职", head,
                    u"官职编号 %s" % e.get("oid"), e.get("oid"))
            n += 1
    stats["cbdb_offices"] = n

    # 人名（CBDB，弹生卒朝代；简繁双索引）
    n = 0
    for e in _load_jsonl(os.path.join(d, "cbdb_persons.jsonl")):
        head = (e.get("head") or "").strip()
        if head:
            for surf in {head, _t2s(head)}:
                add("lex", surf, u"人名", u"CBDB 历代人物", head,
                    (e.get("gloss") or "").strip(), e.get("pid"))
            n += 1
    stats["cbdb_persons"] = n

    for b in idx.values():
        b["era"].sort(key=lambda x: -len(x[0]))
        # 等长 tie：人名 > 官名 > 地名（黄庭坚是人不是词牌地名）
        b["lex"].sort(key=lambda x: (-len(x[0]), _TYPE_PRIO.get(x[1], 9)))
    return idx, stats


def _index():
    with _LOCK:
        s = _sig()
        if _STATE["index"] is not None and _STATE["sig"] == s:
            return _STATE["index"], _STATE["stats"]
        # pickle 缓存：57 万词条首次全量建 10s，缓存命中 ~0.3s
        cache = os.path.join(_toolbook_dir(), ".entity_idx_cache.pkl")
        try:
            if os.path.isfile(cache) and os.path.getmtime(cache) >= max(
                    m for _, _, m in s if m):
                with open(cache, "rb") as f:
                    sig, idx, stats = pickle.load(f)
                if sig == s:
                    _STATE["index"], _STATE["stats"], _STATE["sig"] = idx, stats, s
                    return idx, stats
        except Exception:
            pass
        _STATE["index"], _STATE["stats"] = _build()
        _STATE["sig"] = s
        try:
            with open(cache, "wb") as f:
                pickle.dump((s, _STATE["index"], _STATE["stats"]), f, protocol=4)
        except Exception:
            pass
        return _STATE["index"], _STATE["stats"]


def annotate(text, max_hits=300):
    """实体标注入口。繁体文本自动走简体回退通道（位置逐字映射回原文）。"""
    s, pos_map = _t2s_mapped(text)
    result = _annotate_core(s, max_hits=max_hits)
    if pos_map is not None:
        for e in result["entities"]:
            e["start"] = pos_map[e["start"]]
            e["end"] = pos_map[e["end"] - 1] + 1
            e["text"] = text[e["start"]:e["end"]]
            e["surface"] = e["text"]
        result["traditional_pass"] = True
    return result


def _looks_traditional(text):
    sample = text[:500]
    if not sample:
        return False
    hits = sum(1 for c in sample if _t2s(c) != c)
    return hits / float(len(sample)) > 0.12


def _t2s_mapped(text):
    """逐字转简体并记录位置映射；任一字转出不为一字则放弃回退（返回 None 映射）。"""
    if not _looks_traditional(text):
        return text, None
    out = []
    pos_map = []
    for i, c in enumerate(text):
        c2 = _t2s(c)
        if len(c2) != 1:
            return text, None
        out.append(c2)
        pos_map.append(i)
    return u"".join(out), pos_map


def _annotate_core(text, max_hits=300):
    if not text:
        return {"ok": False, "error": "empty text"}
    idx, stats = _index()
    ents = []
    i = 0
    n = len(text)
    while i < n and len(ents) < max_hits:
        ch = text[i]
        bucket = idx.get(ch)
        if bucket:
            hit = None
            # 1) 年号同位优先
            for surface, etype, book, head, gloss, ref in bucket["era"]:
                if text.startswith(surface, i):
                    hit = (surface, etype, book, head, gloss, ref)
                    break
            if hit:
                surface = hit[0]
                ents.append({"start": i, "end": i + len(surface),
                             "text": surface, "type": hit[1], "book": hit[2],
                             "head": hit[3], "gloss": hit[4], "ref": hit[5]})
                i += len(surface)
                continue
            # 2) lex 最长匹配（年号后纪年尾词抑制）
            for surface, etype, book, head, gloss, ref in bucket["lex"]:
                if text.startswith(surface, i):
                    if (surface.endswith(u"年") and len(surface) <= 5
                            and all(c in _YEARISH for c in surface[:-1])
                            and ents and ents[-1]["type"] == u"年号"
                            and ents[-1]["end"] == i):
                        hit = None
                        break
                    hit = (surface, etype, book, head, gloss, ref)
                    break
            if hit:
                surface = hit[0]
                ents.append({"start": i, "end": i + len(surface),
                             "text": surface, "type": hit[1], "book": hit[2],
                             "head": hit[3], "gloss": hit[4], "ref": hit[5]})
                i += len(surface)
                continue
        i += 1
    return {"ok": True, "entities": ents, "stats": stats,
            "truncated": len(ents) >= max_hits}


def stats():
    _, st = _index()
    return {"ok": True, "stats": st}
