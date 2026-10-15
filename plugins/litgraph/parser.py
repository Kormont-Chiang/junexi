# -*- coding: utf-8 -*-
"""文献图谱解析器: 知网/国社科导出文本(Refworks 标记格式 / GB/T 7714) → 图谱节点与边。
节点身份 = 标题归一化(简繁归一+去标点空白), 跨框同名合并。
kind: seed(种子) / ref(参考文献, 种子→它) / citedby(引证, 它→种子) / both。
"""
import re

_PUNCT_RE = re.compile(r'[\s\[\]【】()（）．.，,：:;；"“”‘’、\-—~·《》<>〈〉?!？!\'\\|/＊*＆&]')

_S2T = None


def _s2t():
    global _S2T
    if _S2T is None:
        try:
            from opencc import OpenCC
            _S2T = OpenCC("s2t")
        except Exception:
            _S2T = False
    return _S2T


def norm_title(t):
    """标题归一化: 简→繁 + 去标点空白 + lower。节点唯一键。"""
    t = (t or "").strip()
    conv = _s2t()
    if conv:
        t = conv.convert(t)
    return _PUNCT_RE.sub('', t).lower()


# ── Refworks 标记格式(CNKI 导出选项之一) ──────────────────
_RW_TAG = re.compile(r'^([A-Z][A-Z0-9])\s+(.*)$')


def parse_refworks(text):
    """CNKI Refworks 导出: 记录以 RT 开头, 每行 'TAG 值', 空行分段。"""
    recs, cur, last = [], None, None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _RW_TAG.match(line)
        if m:
            tag, val = m.group(1), m.group(2).strip()
            if tag == 'RT' or cur is None:
                cur = {}
                recs.append(cur)
            cur.setdefault(tag, []).append(val)
            last = tag
        elif cur is not None and last:
            cur[last][-1] += ' ' + line
    out = []
    for r in recs:
        title = ' '.join(r.get('T1') or r.get('TI') or r.get('T2') or []).strip()
        if not title or norm_title(title) == '':
            continue
        authors = []
        for a in (r.get('A1') or r.get('AU') or []):
            authors += [x.strip() for x in re.split(r'[;；]', a) if x.strip()]
        out.append({
            'title': title,
            'authors': authors,
            'source': ' '.join(r.get('JF') or r.get('JO') or r.get('PB') or []).strip(),
            'year': (r.get('YR') or r.get('PY') or r.get('FD') or [''])[0].strip()[:4],
        })
    return out


# ── GB/T 7714 顺序编码(CNKI 参考文献/引证文献页导出) ──────
_NUM_PREFIX = re.compile(r'^\s*(?:\[|［|〔)\s*\d+\s*(?:\]|］|〕)\s*')
_TYPE_MARK = re.compile(r'\[([A-Za-z]{1,4}(?:/OL)?)\]')
_YEAR_RE = re.compile(r'((?:19|20)\d{2}|前\s?\d{2,4})')


def _clean_authors(seg):
    seg = _NUM_PREFIX.sub('', seg).strip()
    parts = re.split(r'[,，;；]', seg)
    out = []
    for p in parts:
        p = p.strip().strip('.．')
        if p and not _YEAR_RE.search(p) and len(p) <= 30:
            out.append(p)
    return out


def parse_gbt(text):
    """GB/T 7714 行: '[n] 作者. 标题[J]. 刊名, 年, 卷(期): 页.' 宽容解析。"""
    out = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        body = _NUM_PREFIX.sub('', line).strip()
        if not body:
            continue
        tm = _TYPE_MARK.search(body)
        doctype = tm.group(1) if tm else ''
        # 按 '. ' 切段; 含类型标记的段 = 标题段
        parts = re.split(r'[.．]\s*', body)
        title, authors, source = '', [], ''
        if tm:
            t_idx = next((i for i, p in enumerate(parts) if _TYPE_MARK.search(p)), None)
            if t_idx is not None:
                seg = parts[t_idx]
                t_m = _TYPE_MARK.search(seg)
                title = (seg[:t_m.start()] + seg[t_m.end():]).strip(' ,，.．')
                authors = _clean_authors('.'.join(parts[:t_idx]))
                source = '.'.join(parts[t_idx + 1:]).strip(' ,，.．')
        if not title and len(parts) >= 2:
            # 无类型标记: 作者. 标题. 其余
            authors = _clean_authors(parts[0])
            title = parts[1].strip(' ,，.．')
            source = '.'.join(parts[2:]).strip(' ,，.．')
        title = title.strip()
        if not title or len(title) > 120:
            continue
        ym = _YEAR_RE.search(body)
        out.append({
            'title': title,
            'authors': authors,
            'source': source[:80],
            'year': ym.group(1).replace(' ', '') if ym else '',
            'doctype': doctype,
        })
    return out


def parse_any(text):
    """自动识别: 含 RT 行 → Refworks; 否则 GB/T 7714。"""
    if re.search(r'(?m)^RT\s+\S', text or ""):
        return parse_refworks(text)
    return parse_gbt(text)


# ── 图谱装配 ────────────────────────────────────────────────
def build_graph(seed_title, refs=None, citedby=None):
    """refs=种子引用(出边), citedby=被引(入边)。返回 (seed_id, nodes, edges)。"""
    seed_title = (seed_title or "").strip()
    seed_id = norm_title(seed_title)
    if not seed_id:
        return '', [], []
    nodes = {seed_id: {
        'id': seed_id, 'title': seed_title, 'authors': [], 'source': '',
        'year': '', 'kind': 'seed', 'n': 0,
    }}
    edges = []

    def _fill(nd, it):
        for f in ('source', 'year'):
            if not nd.get(f) and it.get(f):
                nd[f] = it[f]
        if not nd.get('authors') and it.get('authors'):
            nd['authors'] = it['authors']

    def add(items, kind):
        for it in items:
            nid = norm_title(it.get('title'))
            if not nid or nid == seed_id:
                continue
            if nid in nodes:
                nd = nodes[nid]
                if nd['kind'] != 'seed' and nd['kind'] != kind:
                    nd['kind'] = 'both'
                nd['n'] = nd.get('n', 0) + 1
                _fill(nd, it)
            else:
                nodes[nid] = {
                    'id': nid, 'title': it.get('title', ''), 'authors': it.get('authors') or [],
                    'source': it.get('source', ''), 'year': it.get('year', ''),
                    'kind': kind, 'n': 1,
                }
            edges.append({'s': seed_id, 't': nid} if kind == 'ref'
                         else {'s': nid, 't': seed_id})

    add(refs or [], 'ref')
    add(citedby or [], 'citedby')
    seen = set()
    dedup = []
    for e in edges:
        k = (e['s'], e['t'])
        if k not in seen:
            seen.add(k)
            dedup.append(e)
    return seed_id, list(nodes.values()), dedup
