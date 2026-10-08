# -*- coding: utf-8 -*-
"""错字校对（词典反向校验）：OCR/录入文本的疑似错字检测 + 建议

原理：57 万词库做**锚定单错匹配**——词库中某词 W 与文本切片仅差 1 字，
该位置即疑似错字，W 为依据词。例：王芝石→王安石（芝→安）、洛阝→洛阳（阝→阳）。
另报"未收录串"（词库也救不了的区段，多为真未收词/连续错字）。
吾与点没有的一层：工具书反向校验。全本地、零模型。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entity_tag

_MAX_WORD = 10
_TYPE_PRIO = {u"年号": 0, u"人名": 1, u"官名": 2, u"地名": 3}
_PUNCT = set(u"，。！？；：、·…—‐‑‒―‗‘’“”《》〈〉〔〕【】()[]{}<>「」『』.,;:!?\"'`~^*|/\\-+=%&@#$ \t\r\n0123456789０１２３４５６７８９")
MAX_TEXT = 3000


def _unknown_spans(idx, text):
    """最长匹配分词（标点分隔），返回未登录串 [(s,e)]。"""
    n = len(text)
    spans = []
    i = 0
    while i < n:
        ch = text[i]
        if ch in _PUNCT:
            i += 1
            continue
        bucket = idx.get(ch)
        hit = None
        if bucket:
            for surface, _t, _bk, _h, _g, _r in bucket["era"] + bucket["lex"]:
                if 2 <= len(surface) <= _MAX_WORD and text.startswith(surface, i):
                    if hit is None or len(surface) > len(hit):
                        hit = surface
        if hit:
            i += len(hit)
            continue
        s = i
        while i < n and text[i] not in _PUNCT:
            b2 = idx.get(text[i])
            ok = False
            if b2:
                for surface, _t, _bk, _h, _g, _r in b2["era"] + b2["lex"]:
                    if text.startswith(surface, i):
                        ok = True
                        break
            if ok:
                break
            i += 1
        spans.append((s, i))
    return spans


def proofread(text, max_report=80, per_pos=25):
    if not text:
        return {"ok": False, "error": "empty text"}
    if len(text) > MAX_TEXT:
        return {"ok": False, "error": u"文本过长（校对上限 %d 字）" % MAX_TEXT}
    idx, stats = entity_tag._index()
    n = len(text)
    spans = _unknown_spans(idx, text)

    _YEARISH = u"元一二三四五六七八九十百千〇零0123456789"

    def _evidence_ok(surface, t):
        # 压制「建安六年」类地名噪声（年号+年尾的地名衍生条，不当错字证据）
        if t == u"地名" and len(surface) <= 6 and surface.endswith(u"年") \
                and all(c in _YEARISH for c in surface[:-1]):
            return False
        return True

    def _anchor_zones():
        # 错字只会落在未收录串及其紧邻左缘（王芝|石拜 型切分歧义）：[s-2, e)
        for s, e in spans:
            yield (max(0, s - 2), e)

    zones = list(_anchor_zones())

    def _in_zone(p, L):
        for zs, ze in zones:
            if p < ze and p + L > zs:
                return True
        return False

    def _strict_in_span(mpos):
        return any(s <= mpos < e for s, e in spans)

    by_pos = {}
    for zs, ze in zones:
        for p in range(zs, min(n, ze + 1)):
            ch = text[p]
            if ch in _PUNCT:
                continue
            bucket = idx.get(ch)
            if not bucket:
                continue
            for surface, t, bk, h, g, _r in bucket["era"] + bucket["lex"]:
                L = len(surface)
                if not (2 <= L <= _MAX_WORD) or p + L > n or not _evidence_ok(surface, t):
                    continue
                if not _in_zone(p, L):
                    continue
                ndiff = 0
                diff = None
                for k in range(L):
                    a = text[p + k]
                    if a != surface[k]:
                        ndiff += 1
                        if ndiff > 1:
                            break
                        diff = (k, a, surface[k])
                if ndiff != 1:
                    continue
                k, orig, fixed = diff
                if orig in _PUNCT:
                    continue
                mpos = p + k
                # 差异必须落在未收录串内（或其紧邻左缘 1 字）
                if not any(s - 1 <= mpos < e for s, e in spans):
                    continue
                in_span = 1 if _strict_in_span(mpos) else 0
                if L < 3 and not in_span:
                    continue
                score = (-L, _TYPE_PRIO.get(t, 9))
                cand = {"pos": mpos, "orig": orig, "char": fixed, "word": surface,
                        "type": t, "book": bk, "gloss": (g or "")[:60]}
                lst = by_pos.setdefault(mpos, [])
                if all(c[1]["char"] != fixed for c in lst):
                    lst.append((score, cand))
    suggestions = []
    for mpos in sorted(by_pos):
        best = sorted(by_pos[mpos], key=lambda x: x[0])[:per_pos]
        suggestions.extend(c for _s, c in best)
    suggestions.sort(key=lambda x: x["pos"])
    return {"ok": True, "suggestions": suggestions[:max_report],
            "unknown": [{"start": s, "end": e, "text": text[s:e]} for s, e in spans[:40]],
            "stats": stats, "n_unknown": len(spans)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import time
    t0 = time.time()
    r = proofread(u"建安四年春，王芝石拜参知政事，出知江宁府，至洛阝一带。秋七月，猎於昇州西。"
                  u"又選將出征，路由朐忍县。")
    print(u"%.2fs, suggestions=%d, unknown=%d" % (time.time() - t0, len(r["suggestions"]), r["n_unknown"]))
    for x in r["suggestions"]:
        print(x["pos"], x["orig"] + u"→" + x["char"], u"<%s|%s>" % (x["word"], x["type"]))
    print(u"--- unknown ---")
    for u_ in r["unknown"]:
        print(u_["start"], repr(u_["text"]))
