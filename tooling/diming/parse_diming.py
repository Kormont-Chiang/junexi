# -*- coding: utf-8 -*-
"""中国历史地名大辞典 结构化解析器 v1
版式规则（来自 page 500 实测）：
- 双栏，左栏 x0<700 先读，右栏后读（笔画排序，左栏字少在前）
- 词条行与正文行框高一致（~28-34px），无法按字号分，按【释文开头信号词】切段
- 词条格式: 词头(2-12字,可带①-⑩义项号) + 释文(以在今/即今/金时/清康熙/明嘉靖/①/年份等开头)
- 跨页词条：页首不命中信号词的行挂到上一词条
页型分类：索引页 = 大量 "词头 + 3-4位页码" 短行
输出: diming_entries.jsonl {head, note, page} + 解析统计
"""
import json, os, re, sys
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

DATA = os.environ.get(u"DIMING_DATA", os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(DATA, 'diming_ocr.jsonl')
OUT = os.path.join(DATA, 'diming_entries.jsonl')

# 释文开头信号（时代/地理谓语）；词头 = 信号词之前的 2-12 纯汉字（可带义项号）
OPENER = re.compile(
    u'(?:'
    u'在今|即今|治今|当在今|应在今|疑在今|故城|故治|又|亦|本|旧'
    u'|又名|亦名|一名|古称|旧称|简称|又称|或作|一作'
    u'|即(?!今)(?=[\\u3400-\\u9fff])|在(?!今)(?=[\\u3400-\\u9fff])'
    u'|(?:明|清|唐|宋|元|金|隋|晋|吴|魏|蜀|秦|汉|齐|梁|陈|周|夏|辽|西夏'
    u'|前赵|后赵|前秦|后秦|西秦|前燕|后燕|北燕|南燕|前凉|后凉|南凉|北凉|西凉'
    u'|北魏|东魏|西魏|北齐|北周|后梁|后唐|后晋|后汉|后周|北宋|南宋|民国)置'
    u'|金时|金代|金初|金末|金明昌|金贞'
    u'|明(?:嘉|万|洪|崇|顺|康|乾|道|同|光|宣|永|建|正|景|天|成化|洪武|嘉靖|万历|崇祯|顺治|康熙|雍正|乾隆|嘉庆|道光|同治|光绪|初|末|代)'
    u'|清(?:康|乾|嘉|道|同|光|宣|顺|初|末|代)'
    u'|民国|西汉|东汉|三国|西晋|东晋|南朝|隋|唐(?:初|代|武|玄|高|中|末)|五代|宋(?:初|代|北|南)|辽|元(?:代|初|末)'
    u'|[0-9]{3,4}年|①|②|③|④|⑤|\\(|（|《'
    u')'
)
SENSE = re.compile(u'^[①②③④⑤⑥⑦⑧⑨⑩]+')
CONT_MARK = re.compile(u'^[”"。；！？）》]')  # 续行标志（行首闭合符）

# v2 索引真值引导：截断切点必须命中索引词头表（_idx_truth.json，由 _idx_truth.py 生成）
# 无真值文件时 v2 截断关闭（退回 v1 语义），保证精度优先
_TRUTH = None


def _load_truth():
    global _TRUTH
    if _TRUTH is None:
        tp = os.path.join(DATA, '_idx_truth.json')
        _TRUTH = {}
        try:
            import json as _json
            _TRUTH = _json.load(open(tp, encoding='utf-8'))
        except Exception:
            pass
    return _TRUTH
HEAD_CLEAN = re.compile(u'^[\\u3400-\\u9fff·]{1,12}[①②③④⑤⑥⑦⑧⑨⑩]?$')
# v2: 词头过食修补——词头候选整体不匹配时，允许"短词头+谓语字"截断
# 约束：词头≤6 字 且 余字首字为谓语集合（防正文续行误判）
HEAD_PREFIX = re.compile(u'^[\\u3400-\\u9fff·]{1,6}')
PRED_START = u'指为即之古春秋战本旧属在一统合总南北魏晋隋唐宋元明清后前西东汉齐梁陈吴蜀魏燕凉秦周夏辽金'
HEAD_IDX = re.compile(u'^(\\S{1,12})\\s*(\\d{3,4})$')

def quad(b):
    return min(b[0::2]), min(b[1::2]), max(b[0::2]), max(b[1::2])

def load_pages(path):
    data = open(path, 'rb').read()
    pages = {}
    for ln in data.decode('utf-8', 'ignore').splitlines():
        try:
            o = json.loads(ln)
            pages[o['page']] = o['lines']
        except Exception:
            pass
    return pages

def is_index_page(lines):
    """索引页判据：行短(≤16字)且几乎无句号——正文必有《》。引文句号"""
    if not lines:
        return False
    short = sum(1 for l in lines if len(l.get('text', '').strip()) <= 16)
    nodot = sum(1 for l in lines if '。' not in l.get('text', ''))
    return short / len(lines) > 0.6 and nodot / len(lines) > 0.95

def col_split(lines):
    left, right = [], []
    for l in lines:
        b = l.get('box')
        if not b:
            continue
        (right if quad(b)[0] >= 700 else left).append(l)
    key = lambda l: quad(l['box'])[1]
    left.sort(key=key)
    right.sort(key=key)
    return left + right  # 左栏先读

def parse_body(lines, page_no, entries, carry):
    for l in lines:
        t = l.get('text', '').strip()
        if not t:
            continue
        m = OPENER.search(t)
        # 词头候选：信号词前 1-12 个纯汉字（可跟义项号），信号词须在前 14 字内
        head = None
        if m and 1 <= m.start() <= 14:
            cand = SENSE.sub('', t[:m.start()]).strip()
            if HEAD_CLEAN.match(cand):
                head = cand
            else:
                # v2 截断（索引真值引导）：从长到短扫描，切点须"后续字为谓语 且 词头在索引真值中"
                # 长优先：防"一合坞"在 L=1 被 合(统合总) 抢先截成"一"
                truth = _load_truth()
                if truth:
                    for L in range(min(6, len(cand)), 0, -1):
                        if cand[L:L + 1] and cand[L] in PRED_START and HEAD_PREFIX.match(cand[:L]):
                            if cand[:L] in truth:
                                head = cand[:L]
                                break
        if head:
            entries.append({'head': head, 'note': t[m.start():], 'page': page_no})
            carry = entries[-1]
        elif carry is not None:
            carry['note'] += t  # 续行并入
    return carry

def _page_printed(lines):
    """书眉双版式解析印刷页码：右页眉'4二画二' / 左页眉'二画二丁7'"""
    for l in lines[:6] + lines[-4:]:
        t = l.get('text', '').strip()
        m = _HDR.match(t) or _HDR_TAIL.match(t)
        if m:
            return int(m.group(1))
    return None


_HDR = re.compile(u'^([0-9]{1,4})[一二三四五六七八九十]{1,3}画')
_HDR_TAIL = re.compile(u'^[一二三四五六七八九十]{1,3}画.*?([0-9]{1,4})\s*$')


_FOLD_EXTRA = {u"剌": u"刺"}  # 地名典实测字形差（v4 OCR 剌/刺混淆，索引与正文互现）
_t2s_cache = None

def _load_t2s():
    global _t2s_cache
    if _t2s_cache is None:
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                          "data", "toolbooks", "t2s_map.json")
        try:
            _t2s_cache = json.load(open(fp, encoding="utf-8"))
        except Exception:
            _t2s_cache = {}
    return _t2s_cache

def _fold_h(s):
    """词头匹配键：繁简折叠 + 形近折叠 + 地名典特有形差（不影响输出显示）"""
    t2s = _load_t2s()
    return "".join(_FOLD_EXTRA.get(t2s.get(c, c), t2s.get(c, c)) for c in s)


def rescue_heads(pages, page_printed, entries, stats):
    """v3/v4 行首真词兜底：无信号词条头（"二江古代…的总称"）正常解析抓不到，
    但索引真值知道它在哪页——行首命中即补建条目（note=该行余文）。
    单字词头须行首+后随谓语/书名号/义项号，防正文行误配。
    v4 增：①行首剥离前导引号（’七沟村） ②折叠匹配（三不剌川≈三不刺川）
          ③词头独占一行时接力下一行作释义（七里川）
    """
    truth = _load_truth()
    if not truth:
        return
    by_printed = {}
    for h, pp in truth.items():
        by_printed.setdefault(pp, []).append(h)
    rescued = 0
    rescued_interp = 0
    parsed_by_page = {}
    for e in entries:
        parsed_by_page.setdefault(e["page"], set()).add(e["head"])
    for pno, (pr, was_interp) in ((k, v) for k, v in page_printed.items()):
        lines = [l for l in pages.get(pno, []) if "text" in l]
        got = parsed_by_page.get(pno, set())
        for h in by_printed.get(pr, []):
            if h in got or len(h) > 12:
                continue
            fh = _fold_h(h)
            note = None
            for i, l in enumerate(lines):
                t = l.get("text", "").lstrip(u"·•　 ‘’'“”\"「」『』")
                if len(h) >= 2:
                    ok = t.startswith(h) or _fold_h(t[:len(h)]) == fh
                else:
                    ok = bool(re.match(
                        u"^%s[①②③（(《]|[%s][指为即之古春战国本旧属在一]" % (re.escape(h), re.escape(h)), t))
                if not ok:
                    continue
                rest = t[len(h):].strip(u"·•　 ，,。：:")
                if len(rest) < 4 and i + 1 < len(lines):
                    # 词头独占一行、释义接下一行（实测：七里川）：接力，门控防串条
                    nt = lines[i + 1].get("text", "").strip()
                    if (len(nt) >= 4 and not _HDR.match(nt) and not _HDR_TAIL.match(nt)
                            and nt[:2] not in truth and not re.match(u"^[①②③（(《0-9A-Za-z]", nt)):
                        rest = nt
                note = rest.strip(u"·•　 ，,。：:）」』”’\"")
                break
            if note and len(note) >= 4:
                entries.append({"head": h, "note": note, "page": pno, "rescued": True})
                got.add(h)
                rescued += 1
                if was_interp:
                    rescued_interp += 1
    stats["rescued"] = rescued
    stats["rescued_interp"] = rescued_interp


def _interpolate_printed(pages, page_printed):
    """书眉缺失页补锚：印刷页↔PDF页偏移单调缓变（插页致漂移），相邻锚点间线性插值。
    仅内插不外推；插值只决定'试哪些词头'，行首真词匹配的门不变，故精度无损、只增召回。
    返回 {pdf: (印刷页, 是否插值)}。
    """
    anchored = sorted(page_printed)
    out = {p: (page_printed[p], False) for p in anchored}
    for a, b in zip(anchored, anchored[1:]):
        pa, pb = page_printed[a], page_printed[b]
        if pb <= pa:
            continue
        for pno in range(a + 1, b):
            if pno not in pages:
                continue
            lines = [l for l in pages[pno] if 'text' in l and l.get('box')]
            if is_index_page(lines):
                continue
            est = pa + round((pb - pa) * (pno - a) / float(b - a))
            out[pno] = (est, True)
    return out


def main():
    pages = load_pages(IN)
    entries = []
    stats = Counter()
    carry = None
    page_printed = {}
    for pno in sorted(pages):
        lines = [l for l in pages[pno] if 'text' in l and l.get('box')]
        if is_index_page(lines):
            stats['index_pages'] += 1
            continue
        stats['body_pages'] += 1
        pr = _page_printed(lines)
        if pr:
            page_printed[pno] = pr
        carry = parse_body(col_split(lines), pno, entries, carry)
    interp = _interpolate_printed(pages, page_printed)
    stats['pages_interpolated'] = sum(1 for _, f in interp.values() if f)
    rescue_heads(pages, interp, entries, stats)
    with open(OUT, 'w', encoding='utf-8') as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    stats['entries'] = len(entries)
    print(json.dumps(stats, ensure_ascii=False))
    lens = sorted(len(e['note']) for e in entries)
    if lens:
        print('note len p50/p90:', lens[len(lens)//2], lens[int(len(lens)*0.9)])
    for e in entries[100:110]:
        print(e['page'], e['head'], '|', e['note'][:44])

if __name__ == '__main__':
    main()
