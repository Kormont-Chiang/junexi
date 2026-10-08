# -*- coding: utf-8 -*-
"""实体标注（二期 v1 词典锚定）：OCR/句读文本 × 自家工具书 = 可点词条

思路：工具书本身就是实体表——年号考 eras、地名典 head。
最长匹配扫文本，命中即带词条摘要返回，前端高亮+点击弹卡。
地名典数据今晚 OCR 完工后自动变全量（加载期探测文件变化）。
"""
import io
import json
import os
import threading
import time

_LOCK = threading.Lock()
_STATE = {"sig": None, "index": None, "stats": {}}

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
    for fn in ("diming_clean.jsonl", "nianhao_clean.jsonl"):
        p = os.path.join(d, fn)
        out.append((fn, os.path.getsize(p) if os.path.isfile(p) else 0,
                    int(os.path.getmtime(p)) if os.path.isfile(p) else 0))
    return tuple(out)


def _build():
    """first_char -> [(surface, type, book, head, gloss)]，按 surface 长度降序。"""
    idx = {}
    stats = {}
    d = _toolbook_dir()

    def add(surface, etype, book, head, gloss):
        surface = (surface or "").strip()
        if len(surface) < 2:
            return
        idx.setdefault(surface[0], []).append((surface, etype, book, head, gloss))

    nh = os.path.join(d, "nianhao_clean.jsonl")
    n_nh = 0
    if os.path.isfile(nh):
        for line in io.open(nh, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            gloss = e.get("year_span") or ""
            ruler = (e.get("ruler") or "").strip()
            note = (e.get("note") or "").strip()
            snippet = note[:80] if note else ""
            for era in (e.get("eras") or []):
                era = (era or "").strip()
                if era:
                    add(era, u"年号", u"二十史朔闰表", era,
                        (gloss + u" " + snippet).strip() or ruler)
                    n_nh += 1
    stats["nianhao_eras"] = n_nh

    dm = os.path.join(d, "diming_clean.jsonl")
    n_dm = 0
    if os.path.isfile(dm):
        for line in io.open(dm, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            head = (e.get("head") or "").strip()
            if head:
                add(head, u"地名", u"中国历史地名大辞典", head, (e.get("note") or "")[:80])
                n_dm += 1
    stats["diming_heads"] = n_dm

    for k in idx:
        idx[k].sort(key=lambda x: -len(x[0]))
    return idx, stats


def _index():
    with _LOCK:
        s = _sig()
        if _STATE["index"] is None or _STATE["sig"] != s:
            _STATE["index"], _STATE["stats"] = _build()
            _STATE["sig"] = s
        return _STATE["index"], _STATE["stats"]


def annotate(text, max_hits=200):
    """最长匹配实体标注。返回 {ok, entities:[{start,end,text,type,book,head,gloss}], stats}"""
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
            for surface, etype, book, head, gloss in bucket:
                if text.startswith(surface, i):
                    hit = (surface, etype, book, head, gloss)
                    break
            if hit:
                surface, etype, book, head, gloss = hit
                ents.append({
                    "start": i, "end": i + len(surface),
                    "text": surface, "type": etype,
                    "book": book, "head": head, "gloss": gloss,
                })
                i += len(surface)
                continue
        i += 1
    return {"ok": True, "entities": ents, "stats": stats,
            "truncated": len(ents) >= max_hits}


def stats():
    _, st = _index()
    return {"ok": True, "stats": st}
