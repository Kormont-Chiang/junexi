#!/usr/bin/env python3
"""
六月息 · 历史学学术面板后端
Flask + DeepSeek + CBDB + Obsidian Local REST API
"""

import os
import re
import sys
import json
import threading
from collections import OrderedDict
import requests
import subprocess
from datetime import datetime
from urllib.parse import quote, unquote
from flask import Flask, jsonify, request, render_template, send_from_directory, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ── Config ──────────────────────────────────────────────
OBSIDIAN_VAULT = "论文写作"
OBSIDIAN_API_PORT = 27123  # Local REST API 插件默认端口
OBSIDIAN_API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"  # 通过 OpenClaw 调用

# CBDB 本地数据库路径
# 数据已从微信接收目录迁移到稳定位置（微信会定期清理旧文件，导致"又打不开"）。
# 可用环境变量 CBDB_DATA_PATH 覆盖。
CBDB_DATA_PATH = os.environ.get(
    "CBDB_DATA_PATH",
    os.path.expanduser(r"~\Documents\historia-data\cbdb\CBDB_20240208_DATA1.mdb"),
)
CBDB_CONN_STR = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={CBDB_DATA_PATH};'

# 简繁转换：CBDB 字库为繁体，简体输入自动转繁检索（opencc 不可用时静默降级为原样检索）
try:
    from opencc import OpenCC
    _OPENCC_S2T = OpenCC("s2t")
except Exception:
    _OPENCC_S2T = None

def name_variants(name):
    """生成姓名检索变体：原文 + 简转繁，去重保序。"""
    variants = [name]
    if _OPENCC_S2T:
        try:
            traditional = _OPENCC_S2T.convert(name)
            if traditional and traditional not in variants:
                variants.append(traditional)
        except Exception:
            pass
    return variants

# CHGIS 数据目录（安装版落在可写目录，开发期在项目内）
if getattr(sys, "frozen", False):
    CHGIS_DATA_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JuneXi", "chgis_data"
    )
else:
    CHGIS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chgis_data")
os.makedirs(CHGIS_DATA_DIR, exist_ok=True)

def get_app_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__,
    template_folder=os.path.join(get_app_dir(), "templates"),
    static_folder=os.path.join(get_app_dir(), "static"))
CORS(app)

@app.after_request
def add_no_cache_headers(response):
    # 本地应用：禁止缓存前端文件，避免 WebView2/浏览器用到旧 JS
    response.headers["Cache-Control"] = "no-store"
    return response

@app.before_request
def fix_raw_non_utf8_query():
    """宽容修复请求行的原始非 UTF-8 字节（如 PowerShell 把 GBK 字节直发 URL）。

    正常浏览器请求是 percent-encoded UTF-8，字节全是 ASCII，快速放行；
    原始 GBK 字节经 Werkzeug 多层翻搅后可能变成"双重乱码"（仍是合法 UTF-8），
    判断依据是解码结果含 U+0080–U+00FF 的 latin-1 高字符——正常中文不会有。
    还原为 GBK 后再重新 percent-encode 进 environ，下游 request.args 即正确中文。"""
    raw = request.environ.get("QUERY_STRING", "")
    if not raw:
        return
    b = raw.encode("latin-1")  # WSGI 以 latin-1 暴露，encode 回原始字节
    try:
        s1 = b.decode("utf-8")
    except UnicodeDecodeError:
        # 原始字节不是 UTF-8：大概率是 GBK 直发
        try:
            fixed = b.decode("gbk")
        except UnicodeDecodeError:
            return
    else:
        if not any(0x80 <= ord(ch) <= 0xFF for ch in s1):
            return  # ASCII 或干净中文，无需处理
        # 含 latin-1 高字符（½øÊ¿ ÂÃ 之类）→ 双重乱码，剥一层再按 GBK 还原
        try:
            fixed = s1.encode("latin-1").decode("gbk")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return
    if any(0x80 <= ord(ch) <= 0xFF for ch in fixed):
        return  # 还原结果仍含高字符，不敢乱动
    from urllib.parse import quote, parse_qsl
    new_qs = quote(fixed, safe="=&?/,;:@+")
    request.environ["QUERY_STRING"] = new_qs
    # sans-io Request 在 __init__ 时把 query_string 存为实例属性，且 args 是
    # cached_property——本 hook 之前可能已被提前解析缓存，这里一并重写
    request.query_string = new_qs.encode("latin-1")
    from werkzeug.datastructures import MultiDict
    request.__dict__["args"] = MultiDict(parse_qsl(new_qs, keep_blank_values=True))

# ── CBDB 本地数据库连接 ─────────────────────────────────

_KIN_MOURNING_RE = None

# 亲属符号 → 中文（符号体系见 KINSHIP_CODES.c_kinrel：F父 M母 B兄弟 Z姐妹 S子 D女 W妻 H夫 A姻親）
_KIN_SYM = {"F": "父", "M": "母", "B": "兄弟", "Z": "姐妹", "S": "子", "D": "女",
            "W": "妻", "H": "夫", "A": "姻親"}
_KIN_NUM_1 = {"S": "長子", "D": "長女"}
_KIN_NUM_N = {"S": "子", "D": "女"}


def _describe_kin_path(path_rel):
    """把关系符号串翻成中文链：B-S1=弟之長子、WFF=妻之父之父、ZS=姐妹之子。"""
    import re as _re
    tokens = _re.findall(r"[A-Z][+\-]?\d*", path_rel)
    parts = []
    for tk in tokens:
        sym = tk[0]
        mod = tk[1:]
        base = _KIN_SYM.get(sym)
        if not base:
            continue
        if sym in ("B", "Z"):
            if "+" in mod:
                word = "兄" if sym == "B" else "姐"
            elif "-" in mod:
                word = "弟" if sym == "B" else "妹"
            else:
                word = base
        elif sym in ("S", "D"):
            num = "".join(c for c in mod if c.isdigit())
            if num == "1":
                word = _KIN_NUM_1[sym]
            elif num:
                cn = {"2": "次", "3": "三", "4": "四", "5": "五", "6": "六", "7": "七",
                      "8": "八", "9": "九"}.get(num, num)
                word = cn + _KIN_NUM_N[sym]
            else:
                word = base
        elif sym == "W":
            num = "".join(c for c in mod if c.isdigit())
            if num:
                n = int(num)
                word = f"第{n}任妻"
            else:
                word = base
        else:
            word = base
        parts.append(word)
    return "之".join(parts)


def _mourning_lookup(path_rel, mourning):
    """按路径关系串查五服表。CBDB 符号带修饰：+/- 表兄弟长幼、数字表排行
    （B-=弟、B+=兄、D1=長女、S6=六子），KIN_Mourning 键是规范形（B/D/S），
    故逐级规范化：原串 → 去 +/- 与数字 → 首 token 再规范化。"""
    global _KIN_MOURNING_RE
    if _KIN_MOURNING_RE is None:
        import re as _re
        _KIN_MOURNING_RE = _re.compile(r"[+\-\d]")
    if path_rel in mourning:
        return mourning[path_rel]
    norm = _KIN_MOURNING_RE.sub("", path_rel)
    if norm in mourning:
        return mourning[norm]
    head = _KIN_MOURNING_RE.sub("", path_rel.split(" ", 1)[0])
    return mourning.get(head) or {}


def _in_clause(column, ids, params, chunk=500):
    """Access 参数化 IN 列表（超 500 参数会 HY001，分片 OR 连接）。
    ids 为空时返回恒假条件。params 就地追加，顺序与占位符一致。"""
    ids = [int(i) for i in ids]
    if not ids:
        return "1=0"
    parts = []
    for i in range(0, len(ids), chunk):
        seg = ids[i:i + chunk]
        parts.append(f"{column} IN ({','.join('?' for _ in seg)})")
        params.extend(seg)
    return "(" + " OR ".join(parts) + ")"


class CBDBConnection:
    """CBDB 本地 .mdb 数据库连接"""
    _instance = None
    _conn = None

    @classmethod
    def get_conn(cls):
        # 每次创建新连接，避免状态问题
        import pyodbc
        try:
            return pyodbc.connect(CBDB_CONN_STR)
        except Exception as e:
            print(f"CBDB connection error: {e}")
            return None

    _avail_cache = {"t": 0, "v": False}

    @classmethod
    def is_available(cls):
        # 可用性探测含 COUNT(*) BIOG_MAIN 全表扫描（Access 上秒级），
        # 每次请求都调用会把所有检索拖慢 3s+；TTL 60s 缓存探测结果。
        import time as _time
        now = _time.time()
        if now - cls._avail_cache["t"] < 60:
            return cls._avail_cache["v"]
        conn = cls.get_conn()
        v = False
        if conn is not None:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM BIOG_MAIN")
                cursor.fetchone()
                v = True
            except Exception:
                v = False
        cls._avail_cache = {"t": now, "v": v}
        return v

    @classmethod
    def search_persons(cls, name, dynasty_code=None, gender=None, addr_id=None, limit=50,
                       by_from=None, by_to=None, dy_from=None, dy_to=None,
                       index_from=None, index_to=None):
        """搜索人物：姓名/拼音/姓/名/字/号/谥号等别名/人物ID 直达；结果附朝代与籍贯。
        纯数字输入按人物ID精确匹配（CBDB 原生支持按 ID 检索）。
        原生按人查询维度：朝代、性别（c_female 1=女 0=男）、籍贯地址、
        生年区间(by_from/by_to)、卒年区间(dy_from/dy_to)、索引年区间(index_from/index_to)。
        拼音三种模式（原生按人查询）：全小写=任意子串；首字母大写=逐字首匹配（"Hao"命中 Zhang Hao/Hao Jing）；
        加 ! 前缀=整串最左匹配（"!Hao"仅命中 Hao Jing）。
        多行 / 、 ， ； 分隔 = 批量查人（OR 语义，任一名字命中即可）。
        籍贯地址匹配指数地址（c_index_addr_id）或基本地址（BIOG_ADDR_DATA c_addr_type=1）。
        注意：c_female 是 BIT 列，参数必须绑 bool，绑 int 会被 Access ODBC 静默置否（实测）。"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()

        raw = name.strip()
        # 批量查人：换行 / 、 ， ； ; 分隔的多检索词，任一命中即可（OR 语义）
        tokens = [t.strip() for t in re.split(r"[\n,，、;；]+", raw) if t.strip()]
        if not tokens:
            return []

        # 单个中文词的快速通道：精确+前缀条件可走索引（实测 0.00s），
        # 现行模糊条件（首尾通配+EXISTS 别名）要全表扫 3s+/变体。
        # 快速通道零命中时回退模糊，保证"东坡"搜字號等部分匹配仍能命中。
        single_cjk = len(tokens) == 1 and not re.fullmatch(r"!?[A-Za-z ]+", tokens[0])

        def _build_conditions(fast):
            conditions, params = [], []
            for token in tokens:
                tok_conds, tok_params = [], []
                # 拼音分支：输入全为 ASCII 字母（可含空格、! 前缀）时走 c_name 罗马字
                if re.fullmatch(r"!?[A-Za-z ]+", token):
                    body = token[1:] if token.startswith("!") else token
                    body = " ".join(body.split())
                    if token.startswith("!"):
                        tok_conds.append("b.c_name LIKE ?")
                        tok_params.append(body + "%")
                    elif body and body[0].isupper():
                        # 逐字首匹配：每个 token 须出现在词首位置，token 间 AND
                        # （token 只含字母空格，直接内联，绕开 Access 参数绑定怪癖）
                        groups = []
                        for tok in body.split():
                            groups.append("(" + " OR ".join([
                                f"b.c_name LIKE '{tok} %'", f"b.c_name LIKE '% {tok} %'",
                                f"b.c_name LIKE '% {tok}'", f"b.c_name = '{tok}'",
                            ]) + ")")
                        tok_conds.append("(" + " AND ".join(groups) + ")")
                    else:
                        like = f"%{body}%"
                        tok_conds.append("(b.c_name LIKE ? OR b.c_name LIKE ?)")
                        tok_params += [like, like]
                elif fast:
                    # 快速通道：仅全名列的精确+前缀（实测 0.00s 走索引；
                    # 三列混合 OR 会退化到 1.4s+，姓/名的部分匹配留给模糊回退）
                    for variant in name_variants(token):
                        tok_conds.append("b.c_name_chn = ?")
                        tok_params.append(variant)
                        tok_conds.append("b.c_name_chn LIKE ?")
                        tok_params.append(variant + "%")
                else:
                    # c_name 是罗马字名；中文全名在 c_name_chn（繁体字库），另支持搜姓/名
                    # 简体输入自动转繁，两组变体 OR 检索，保证简繁都能命中
                    variants = name_variants(token)
                    for column in ("b.c_name", "b.c_name_chn", "b.c_surname_chn", "b.c_mingzi_chn"):
                        for variant in variants:
                            tok_conds.append(f"{column} LIKE ?")
                            tok_params.append(f"%{variant}%")
                    # 别名（字/號/諡/小字等，ALTNAME_DATA）用 EXISTS 子查询，避免 JOIN 放大行数
                    for variant in variants:
                        tok_conds.append(
                            "EXISTS (SELECT 1 FROM ALTNAME_DATA an "
                            "WHERE an.c_personid = b.c_personid AND an.c_alt_name_chn LIKE ?)"
                        )
                        tok_params.append(f"%{variant}%")
                conditions.append("(" + " OR ".join(tok_conds) + ")")
                params += tok_params
            return conditions, params

        def _run(fast):
            conditions, params = _build_conditions(fast)
            where = "(" + " OR ".join(conditions) + ")"
            # 纯数字单输入：人物ID 直达置顶
            pid = tokens[0] if len(tokens) == 1 else ""
            if pid.isdigit():
                where = "(b.c_personid = ? OR " + where + ")"
                params.insert(0, int(pid))
            return where, params

        def _decorate(rows):
            results = []
            for row in rows:
                surname = safe_decode(row.c_surname_chn)
                mingzi = safe_decode(row.c_mingzi_chn)
                name_chn = safe_decode(row.c_name_chn) or (surname + mingzi)
                results.append({
                    "id": row.c_personid,
                    "name": row.c_name or "",
                    "name_chn": name_chn,
                    "surname_chn": surname,
                    "mingzi_chn": mingzi,
                    "birthyear": row.c_birthyear,
                    "deathyear": row.c_deathyear,
                    "dynasty_code": row.c_dy,
                    "dynasty": safe_decode(row.c_dynasty_chn) or "未知",
                    "native_place": safe_decode(getattr(row, "native_place", None)) or ""
                })
            return results

        def _apply_filters(sql, params):
            if dynasty_code:
                sql += " AND b.c_dy = ?"
                params.append(int(dynasty_code))
            if gender is not None and str(gender) in ("0", "1"):
                sql += " AND b.c_female = ?"
                params.append(str(gender) == "1")  # BIT 列必须绑 bool
            if addr_id:
                sql += (" AND (b.c_index_addr_id = ? OR EXISTS ("
                        "SELECT 1 FROM BIOG_ADDR_DATA ba "
                        "WHERE ba.c_personid = b.c_personid AND ba.c_addr_type = 1 AND ba.c_addr_id = ?))")
                params += [int(addr_id), int(addr_id)]
            if by_from:
                sql += " AND b.c_birthyear > 0 AND b.c_birthyear >= ?"
                params.append(int(by_from))
            if by_to:
                sql += " AND b.c_birthyear > 0 AND b.c_birthyear <= ?"
                params.append(int(by_to))
            if dy_from:
                sql += " AND b.c_deathyear > 0 AND b.c_deathyear >= ?"
                params.append(int(dy_from))
            if dy_to:
                sql += " AND b.c_deathyear > 0 AND b.c_deathyear <= ?"
                params.append(int(dy_to))
            if index_from:
                sql += " AND b.c_index_year >= ?"
                params.append(int(index_from))
            if index_to:
                sql += " AND b.c_index_year <= ?"
                params.append(int(index_to))
            return sql, params

        def _detail_by_ids(ids):
            """按主键取详情（朝代名/籍贯），JOIN 只作用于 ≤limit 行。
            籍贯子查询必须一人一行：同一人可能有多条 c_addr_type=1 记录
            （籍贯变更/数据重复），JOIN 放大会让 TOP limit 个 id 返回 >limit 行。"""
            marks = ",".join("?" * len(ids))
            sql = f"""
                SELECT b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                       b.c_birthyear, b.c_deathyear, b.c_dy, d.c_dynasty_chn, ad.c_name_chn AS native_place
                FROM ((BIOG_MAIN b
                LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
                LEFT JOIN (
                    SELECT ba.c_personid, MIN(ac.c_name_chn) AS c_name_chn
                    FROM BIOG_ADDR_DATA ba LEFT JOIN ADDR_CODES ac ON ba.c_addr_id = ac.c_addr_id
                    WHERE ba.c_addr_type = 1
                    GROUP BY ba.c_personid
                ) ad ON b.c_personid = ad.c_personid)
                WHERE b.c_personid IN ({marks})
                ORDER BY b.c_personid
            """
            cursor.execute(sql, list(ids))
            return _decorate(cursor.fetchall())

        def _exec(where, params, plain=False):
            if plain:
                # 快速通道：无 JOIN 单表按索引取 TOP id（Access 多 JOIN 结构会放弃索引全表扫），
                # 再按主键取详情。仅用于无 addr_id 过滤时（addr 过滤含 EXISTS，会破坏索引路径）。
                fsql, fparams = _apply_filters(f"SELECT TOP {limit} c_personid FROM BIOG_MAIN b WHERE {where}", list(params))
                # 不按 c_personid 排序：索引顺序取前 limit 即可，避免大命中集（如单字姓
                # "王"数万条）整体物化排序；详情查询再按主键排序保证输出稳定
                cursor.execute(fsql, fparams)
                ids = [r.c_personid for r in cursor.fetchall()]
                if not ids:
                    return []
                return _detail_by_ids(ids)

            sql = f"""
            SELECT TOP {limit} b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, b.c_dy, d.c_dynasty_chn, ad.c_name_chn AS native_place
            FROM ((BIOG_MAIN b
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            LEFT JOIN (
                SELECT ba.c_personid, ac.c_name_chn
                FROM BIOG_ADDR_DATA ba LEFT JOIN ADDR_CODES ac ON ba.c_addr_id = ac.c_addr_id
                WHERE ba.c_addr_type = 1
            ) ad ON b.c_personid = ad.c_personid)
            WHERE {where}
        """

            sql, params = _apply_filters(sql, params)
            sql += " ORDER BY b.c_personid"
            cursor.execute(sql, params)
            return _decorate(cursor.fetchall())

        # 先走索引快速通道；单中文词零命中时回退模糊全扫
        if single_cjk:
            results = _exec(*_run(True), plain=not addr_id)
            if not results:
                results = _exec(*_run(False))
            return results
        return _exec(*_run(False))

    @classmethod
    def search_offices(cls, q, category=None, limit=30):
        """官名检索：匹配 OFFICE_CODES（中文名/别名/拼音/英文译名）；category 按门类筛选"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        variants = name_variants(q)
        conditions, params = [], []
        if q.strip():
            for col in ("c_office_chn", "c_office_chn_alt", "c_office_pinyin"):
                for v in variants:
                    conditions.append(f"{col} LIKE ?")
                    params.append(f"%{v}%")
        where = ""
        if conditions:
            where = "(" + " OR ".join(conditions) + ")"
        if category:
            # 门类值是繁体（如「機構」「統稱」），简体输入自动转繁匹配
            cat_conds = []
            for v in name_variants(category):
                cat_conds.append("c_category_1 LIKE ?")
                params.append(f"%{v}%")
            cat_cond = "(" + " OR ".join(cat_conds) + ")"
            where = f"{where} AND {cat_cond}" if where else cat_cond
        if not where:
            return []
        sql = f"""
            SELECT TOP {limit} o.c_office_id, o.c_office_chn, o.c_office_pinyin, o.c_office_trans,
                   o.c_dy, d.c_dynasty_chn, o.c_category_1
            FROM OFFICE_CODES o
            LEFT JOIN DYNASTIES d ON o.c_dy = d.c_dy
            WHERE {where}
            ORDER BY o.c_office_id
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [{
            "office_id": r.c_office_id,
            "office_chn": safe_decode(r.c_office_chn),
            "pinyin": r.c_office_pinyin or "",
            "trans": r.c_office_trans or "",
            "dynasty": safe_decode(r.c_dynasty_chn) or "",
            "category": safe_decode(r.c_category_1) or "",
        } for r in rows]

    @classmethod
    def persons_by_office(cls, office_id, from_year=None, to_year=None, addr_id=None, limit=300):
        """某官职的全部任职者（含任期）；可选任职年份区间/任官地址过滤（CBDB 原生职官检索维度）"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        where = "p.c_office_id = ?"
        params = [int(office_id)]
        if from_year:
            # 任期与 [from_year, ∞) 有重叠：lastyear 未知(0) 视为延伸至将来
            where += " AND (p.c_lastyear = 0 OR p.c_lastyear >= ?)"
            params.append(int(from_year))
        if to_year:
            where += " AND (p.c_firstyear = 0 OR p.c_firstyear <= ?)"
            params.append(int(to_year))
        if addr_id:
            where += " AND EXISTS (SELECT 1 FROM POSTED_TO_ADDR_DATA pa " \
                      "WHERE pa.c_posting_id = p.c_posting_id AND pa.c_addr_id = ?)"
            params.append(int(addr_id))
        sql = f"""
            SELECT TOP {limit} p.c_personid, p.c_firstyear, p.c_lastyear,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn, o.c_office_chn
            FROM (((POSTED_TO_OFFICE_DATA p
            LEFT JOIN BIOG_MAIN b ON p.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            LEFT JOIN OFFICE_CODES o ON p.c_office_id = o.c_office_id)
            WHERE {where}
            ORDER BY p.c_firstyear, p.c_personid
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
            fy = r.c_firstyear or 0
            ly = r.c_lastyear or 0
            results.append({
                "id": r.c_personid,
                "name": r.c_name or "",
                "name_chn": name_chn,
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "office_chn": safe_decode(r.c_office_chn),
                "firstyear": fy if fy > 0 else None,
                "lastyear": ly if ly > 0 else None,
            })
        return results

    @classmethod
    def search_places(cls, q, admin_type=None, from_year=None, to_year=None, limit=30):
        """地名检索：ADDR_CODES（中文名/英文名/旧名）；
        admin_type 行政层级过滤（Xian/Zhou/Fu...）；年份区间与地名存续期求交"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        variants = name_variants(q)
        conditions, params = [], []
        if q.strip():
            for col in ("c_name_chn", "c_name", "c_alt_names"):
                for v in variants:
                    conditions.append(f"{col} LIKE ?")
                    params.append(f"%{v}%")
        where = "(" + " OR ".join(conditions) + ")" if conditions else ""
        if admin_type:
            cond = "c_admin_type = ?"
            params.append(admin_type)
            where = f"{where} AND {cond}" if where else cond
        if from_year:
            cond = "(c_lastyear = 0 OR c_lastyear >= ?)"
            params.append(int(from_year))
            where = f"{where} AND {cond}" if where else cond
        if to_year:
            cond = "(c_firstyear = 0 OR c_firstyear <= ?)"
            params.append(int(to_year))
            where = f"{where} AND {cond}" if where else cond
        if not where:
            return []
        sql = f"""
            SELECT TOP {limit} c_addr_id, c_name, c_name_chn, c_firstyear, c_lastyear,
                   c_admin_type, x_coord, y_coord
            FROM ADDR_CODES
            WHERE {where}
            ORDER BY c_firstyear
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [{
            "addr_id": r.c_addr_id,
            "name_chn": safe_decode(r.c_name_chn),
            "name": r.c_name or "",
            "firstyear": r.c_firstyear or None,
            "lastyear": r.c_lastyear or None,
            "admin_type": r.c_admin_type or "",
            "x_coord": r.x_coord,
            "y_coord": r.y_coord,
        } for r in rows]

    _ADDR_COORDS_CACHE = None  # ADDR_CODES 坐标全量内存缓存（只读快照，无需失效）
    _ADDR_COORDS_LOCK = threading.Lock()  # 单飞锁：并发反查等首次加载完成，禁止重复全量扫描

    @classmethod
    def _addr_coords(cls):
        """坐标反查的内存缓存：一次性全量加载带坐标地名（约 60k 条），
        之后每次反查是纯 Python 数学（<0.5s）。Access 逐次函数扫描+排序冷态可达 30s+，不可用。"""
        if cls._ADDR_COORDS_CACHE is not None:
            return cls._ADDR_COORDS_CACHE
        with cls._ADDR_COORDS_LOCK:
            if cls._ADDR_COORDS_CACHE is not None:  # 双检：等待锁期间别的线程已加载
                return cls._ADDR_COORDS_CACHE
            conn = cls.get_conn()
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c_addr_id, c_name_chn, c_name, c_firstyear, c_lastyear,
                       c_admin_type, x_coord, y_coord
                FROM ADDR_CODES
                WHERE x_coord IS NOT NULL AND y_coord IS NOT NULL
            """)
            cls._ADDR_COORDS_CACHE = [{
                "addr_id": r.c_addr_id,
                "name_chn": safe_decode(r.c_name_chn),
                "name": r.c_name or "",
                "firstyear": r.c_firstyear or None,
                "lastyear": r.c_lastyear or None,
                "admin_type": r.c_admin_type or "",
                "x": float(r.x_coord),
                "y": float(r.y_coord),
            } for r in cursor.fetchall()]
            return cls._ADDR_COORDS_CACHE

    @classmethod
    def nearest_places(cls, x, y, limit=8, max_km=100.0):
        """地图反查：给定 WGS84 经纬度，返回半径内最近的 ADDR_CODES 地名（含距离 km）。
        基于内存坐标缓存做等距圆柱近似（经度差乘 cos(lat)），中国范围内误差可忽略。
        同一坐标的多个朝代记录合并为一条（与 persons_by_place 的 include_same_coord
        语义一致，人物端本就按坐标并入）；代表取最早 firstyear 的记录，返回同址计数。"""
        import math
        cosf = math.cos(math.radians(y))
        groups = {}  # (x, y) -> [min_dist, rep, count]
        for p in cls._addr_coords():
            d = math.hypot((p["x"] - x) * cosf, p["y"] - y) * 111.32
            if d > max_km:
                continue
            key = (p["x"], p["y"])
            g = groups.get(key)
            if g is None:
                groups[key] = [d, p, 1]
            else:
                g[0] = min(g[0], d)
                g[2] += 1
                # 代表规则：最早 firstyear（无年份视为极大）优先，再比 addr_id 小
                a, b = g[1], p
                ka = (a["firstyear"] if a["firstyear"] is not None else 10**9, a["addr_id"])
                kb = (b["firstyear"] if b["firstyear"] is not None else 10**9, b["addr_id"])
                if kb < ka:
                    g[1] = b
        scored = sorted(
            ({**rep, "dist_km": round(d, 1), "same_coord_count": n,
              "x_coord": rep["x"], "y_coord": rep["y"]}
             for (d, rep, n) in groups.values()),
            key=lambda q: q["dist_km"])
        return scored[:limit]

    @classmethod
    def _same_coord_addr_ids(cls, cursor, addr_id):
        """同坐标地址并入（CBDB 新版原生功能）：返回含自身的 addr_id 列表"""
        cursor.execute(
            "SELECT x_coord, y_coord FROM ADDR_CODES WHERE c_addr_id = ?", int(addr_id)
        )
        row = cursor.fetchone()
        if not row or row.x_coord is None or row.y_coord is None:
            return [int(addr_id)]
        cursor.execute(
            "SELECT c_addr_id FROM ADDR_CODES WHERE x_coord = ? AND y_coord = ?",
            row.x_coord, row.y_coord,
        )
        ids = [r.c_addr_id for r in cursor.fetchall() if r.c_addr_id]
        return ids or [int(addr_id)]

    @classmethod
    def persons_by_place(cls, addr_id, include_same_coord=False, limit=300):
        """与某地址相关的人物：籍贯/居址（BIOG_ADDR_DATA）+ 任职地（POSTED_TO_ADDR_DATA）；
        include_same_coord=True 时并入同坐标地址（对应 CBDB 在线版"同坐标地址自动纳入"）"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()

        if include_same_coord:
            ids = cls._same_coord_addr_ids(cursor, addr_id)
        else:
            ids = [int(addr_id)]
        # Access 参数化 IN 列表
        in_clause = ",".join("?" for _ in ids)
        params = list(ids)

        # 籍贯/居址等
        cursor.execute(f"""
            SELECT TOP {limit} ba.c_personid, ba.c_addr_type,
                   t.c_addr_desc_chn,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM (((BIOG_ADDR_DATA ba
            LEFT JOIN BIOG_ADDR_CODES t ON ba.c_addr_type = t.c_addr_type)
            LEFT JOIN BIOG_MAIN b ON ba.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            WHERE ba.c_addr_id IN ({in_clause})
            ORDER BY ba.c_addr_type, ba.c_personid
        """, params)
        rows_a = cursor.fetchall()

        # 任职地
        cursor.execute(f"""
            SELECT TOP {limit} pa.c_personid,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM (POSTED_TO_ADDR_DATA pa
            LEFT JOIN BIOG_MAIN b ON pa.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
            WHERE pa.c_addr_id IN ({in_clause})
            ORDER BY pa.c_personid
        """, params)
        rows_b = cursor.fetchall()

        def person_of(r, link_type):
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
            return {
                "id": r.c_personid,
                "name": r.c_name or "",
                "name_chn": name_chn,
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "link_type": link_type,
            }

        seen = set()
        results = []
        for r in rows_a:
            if r.c_personid in seen:
                continue
            seen.add(r.c_personid)
            label = safe_decode(r.c_addr_desc_chn) or "地址关联"
            results.append(person_of(r, label))
        for r in rows_b:
            if r.c_personid in seen:
                continue
            seen.add(r.c_personid)
            results.append(person_of(r, "任职地"))
        return results

    @classmethod
    def search_entry_types(cls, q, limit=30):
        """入仕方式检索：ENTRY_CODES"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        variants = name_variants(q)
        conditions, params = [], []
        for col in ("c_entry_desc_chn", "c_entry_desc"):
            for v in variants:
                conditions.append(f"{col} LIKE ?")
                params.append(f"%{v}%")
        sql = f"""
            SELECT TOP {limit} c_entry_code, c_entry_desc_chn, c_entry_desc
            FROM ENTRY_CODES
            WHERE {" OR ".join(conditions)}
            ORDER BY c_entry_code
        """
        cursor.execute(sql, params)
        return [{
            "code": r.c_entry_code,
            "name_chn": safe_decode(r.c_entry_desc_chn),
            "name_eng": r.c_entry_desc or "",
        } for r in cursor.fetchall()]

    @classmethod
    def resolve_entry_code(cls, keyword):
        """入仕关键词 → 代码。三级策略（每级含简繁变体）：
        1. 全名精确匹配；
        2. 类目段锚定（':' 后段以关键词开头，如'进士'→'科舉: 進士(籠統)'），
           排序：含'(籠統)'泛称标记者优先，其次描述最短者；
        3. 普通子串，同序。
        解析失败返回 None。"""
        conn = cls.get_conn()
        if not conn or not keyword:
            return None
        cursor = conn.cursor()
        kw = keyword.strip()
        variants = name_variants(kw)
        rank = "IIF(c_entry_desc_chn LIKE '%籠統%', 0, 1), LEN(c_entry_desc_chn) ASC"
        for v in variants:
            cursor.execute(
                "SELECT TOP 1 c_entry_code FROM ENTRY_CODES WHERE c_entry_desc_chn = ?",
                v)
            row = cursor.fetchone()
            if row:
                return row.c_entry_code
        for v in variants:
            cursor.execute(
                f"SELECT TOP 1 c_entry_code FROM ENTRY_CODES "
                f"WHERE (c_entry_desc_chn LIKE ? OR c_entry_desc_chn LIKE ?) "
                f"ORDER BY {rank}",
                f"%: {v}%", f"%:{v}%")
            row = cursor.fetchone()
            if row:
                return row.c_entry_code
        for v in variants:
            cursor.execute(
                f"SELECT TOP 1 c_entry_code FROM ENTRY_CODES "
                f"WHERE c_entry_desc_chn LIKE ? ORDER BY {rank}",
                f"%{v}%")
            row = cursor.fetchone()
            if row:
                return row.c_entry_code
        return None

    @classmethod
    def entry_code_name(cls, entry_code):
        """入仕代码 → 中文名（用于结果回显）。"""
        conn = cls.get_conn()
        if not conn or not entry_code:
            return None
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c_entry_desc_chn FROM ENTRY_CODES WHERE c_entry_code = ?",
            int(entry_code))
        row = cursor.fetchone()
        return safe_decode(row.c_entry_desc_chn) if row else None

    @classmethod
    def persons_by_entry(cls, entry_code, from_year=None, to_year=None, addr_id=None,
                         use_index=False, limit=300):
        """某入仕方式的人物列表（含入仕年、榜次、科场）；可选入仕年区间/入仕地址过滤。
        use_index=True（原生"使用索引年份"）：年份区间同时用索引年兜底——
        入仕年多未标（c_year=0），勾选后 (入仕年 或 索引年) 落在区间内都算。"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        where = "e.c_entry_code = ?"
        params = [int(entry_code)]
        if from_year:
            if use_index:
                where += " AND ((e.c_year > 0 AND e.c_year >= ?) OR (b.c_index_year > 0 AND b.c_index_year >= ?))"
                params += [int(from_year), int(from_year)]
            else:
                where += " AND (e.c_year = 0 OR e.c_year >= ?)"
                params.append(int(from_year))
        if to_year:
            if use_index:
                where += " AND ((e.c_year > 0 AND e.c_year <= ?) OR (b.c_index_year > 0 AND b.c_index_year <= ?))"
                params += [int(to_year), int(to_year)]
            else:
                where += " AND (e.c_year = 0 OR e.c_year <= ?)"
                params.append(int(to_year))
        if addr_id:
            where += " AND e.c_entry_addr_id = ?"
            params.append(int(addr_id))
        sql = f"""
            SELECT TOP {limit} e.c_personid, e.c_year, e.c_exam_rank, e.c_exam_field,
                   ec.c_entry_desc_chn,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM (((ENTRY_DATA e
            LEFT JOIN ENTRY_CODES ec ON e.c_entry_code = ec.c_entry_code)
            LEFT JOIN BIOG_MAIN b ON e.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            WHERE {where}
            ORDER BY e.c_year, e.c_personid
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
            yr = r.c_year or 0
            results.append({
                "id": r.c_personid,
                "name": r.c_name or "",
                "name_chn": name_chn,
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "entry_name": safe_decode(r.c_entry_desc_chn),
                "year": yr if yr > 0 else None,
                "exam_rank": safe_decode(r.c_exam_rank) or "",
                "exam_field": safe_decode(r.c_exam_field) or "",
            })
        return results

    @classmethod
    def get_person_kin(cls, person_id, limit=200):
        """人物亲属列表：KIN_DATA + KINSHIP_CODES"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        sql = f"""
            SELECT TOP {limit} k.c_kin_id, k.c_kin_code, kc.c_kinrel_chn,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM (((KIN_DATA k
            LEFT JOIN KINSHIP_CODES kc ON k.c_kin_code = kc.c_kincode)
            LEFT JOIN BIOG_MAIN b ON k.c_kin_id = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            WHERE k.c_personid = ?
            ORDER BY k.c_kin_code, k.c_kin_id
        """
        cursor.execute(sql, int(person_id))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            if r.c_kin_id is None:
                continue
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi) or f"人物{r.c_kin_id}"
            results.append({
                "id": r.c_kin_id,
                "name_chn": name_chn,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "relation": safe_decode(r.c_kinrel_chn) or "亲属",
            })
        return results

    @classmethod
    def get_person_assoc(cls, person_id, limit=200):
        """人物社会关系列表：ASSOC_DATA + ASSOC_CODES（含年份、文献题名）"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        sql = f"""
            SELECT TOP {limit} a.c_assoc_id, a.c_assoc_year, a.c_text_title, ac.c_assoc_desc_chn,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM (((ASSOC_DATA a
            LEFT JOIN ASSOC_CODES ac ON a.c_assoc_code = ac.c_assoc_code)
            LEFT JOIN BIOG_MAIN b ON a.c_assoc_id = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            WHERE a.c_personid = ?
            ORDER BY a.c_assoc_year, a.c_assoc_id
        """
        cursor.execute(sql, int(person_id))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            if r.c_assoc_id is None:
                continue
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi) or f"人物{r.c_assoc_id}"
            results.append({
                "id": r.c_assoc_id,
                "name_chn": name_chn,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "relation": safe_decode(r.c_assoc_desc_chn) or "关联",
                "year": r.c_assoc_year or None,
                "text_title": safe_decode(r.c_text_title) or "",
            })
        return results

    @classmethod
    def search_status_types(cls, q, limit=30):
        """社会区分类型检索：STATUS_CODES（封号/功名/身份标识）"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        variants = name_variants(q)
        conditions, params = [], []
        for col in ("c_status_desc_chn", "c_status_desc"):
            for v in variants:
                conditions.append(f"{col} LIKE ?")
                params.append(f"%{v}%")
        if not conditions:
            return []
        sql = f"""
            SELECT TOP {limit} c_status_code, c_status_desc_chn, c_status_desc
            FROM STATUS_CODES
            WHERE {" OR ".join(conditions)}
            ORDER BY c_status_code
        """
        cursor.execute(sql, params)
        return [{
            "code": r.c_status_code,
            "name_chn": safe_decode(r.c_status_desc_chn),
            "name_eng": r.c_status_desc or "",
        } for r in cursor.fetchall()]

    @classmethod
    def persons_by_status(cls, status_code, from_year=None, to_year=None, limit=300):
        """某社会区分的人物列表；可选该身份的起止年区间过滤"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        where = "s.c_status_code = ?"
        params = [int(status_code)]
        if from_year:
            where += " AND (s.c_lastyear = 0 OR s.c_lastyear >= ?)"
            params.append(int(from_year))
        if to_year:
            where += " AND (s.c_firstyear = 0 OR s.c_firstyear <= ?)"
            params.append(int(to_year))
        sql = f"""
            SELECT TOP {limit} s.c_personid, s.c_firstyear, s.c_lastyear,
                   sc.c_status_desc_chn,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM (((STATUS_DATA s
            LEFT JOIN STATUS_CODES sc ON s.c_status_code = sc.c_status_code)
            LEFT JOIN BIOG_MAIN b ON s.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            WHERE {where}
            ORDER BY s.c_firstyear, s.c_personid
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
            fy = r.c_firstyear or 0
            ly = r.c_lastyear or 0
            results.append({
                "id": r.c_personid,
                "name": r.c_name or "",
                "name_chn": name_chn,
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "status": safe_decode(r.c_status_desc_chn),
                "firstyear": fy if fy > 0 else None,
                "lastyear": ly if ly > 0 else None,
            })
        return results

    @classmethod
    def search_texts(cls, q, limit=30):
        """著作检索：TEXT_CODES（中文书名/英文名/别名）"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        variants = name_variants(q)
        conditions, params = [], []
        for col in ("c_title_chn", "c_title", "c_title_alt_chn"):
            for v in variants:
                conditions.append(f"{col} LIKE ?")
                params.append(f"%{v}%")
        if not conditions:
            return []
        sql = f"""
            SELECT TOP {limit} c_textid, c_title_chn, c_title, c_text_dy, c_extant
            FROM TEXT_CODES
            WHERE {" OR ".join(conditions)}
            ORDER BY c_textid
        """
        cursor.execute(sql, params)
        return [{
            "text_id": r.c_textid,
            "title_chn": safe_decode(r.c_title_chn) or safe_decode(r.c_title),
            "title": r.c_title or "",
            "dynasty": r.c_text_dy or None,
            "extant": bool(r.c_extant),
        } for r in cursor.fetchall()]

    @classmethod
    def persons_by_text(cls, text_id, limit=300):
        """某著作的相关人物（作者/编者/注者等，按角色标注）"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        sql = f"""
            SELECT TOP {limit} bt.c_personid, bt.c_role_id, tr.c_role_desc_chn,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM ((BIOG_TEXT_DATA bt
            LEFT JOIN BIOG_MAIN b ON bt.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            LEFT JOIN TEXT_ROLE_CODES tr ON bt.c_role_id = tr.c_role_id
            WHERE bt.c_textid = ? AND bt.c_personid > 0
            ORDER BY bt.c_role_id, bt.c_personid
        """
        cursor.execute(sql, int(text_id))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
            results.append({
                "id": r.c_personid,
                "name": r.c_name or "",
                "name_chn": name_chn,
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                "role": safe_decode(r.c_role_desc_chn) or "",
            })
        return results

    # ── 社会关系检索（对标原生十大模块第 5 项）────────────────
    # 大类归类规则：按 ASSOC_CODES 中文描述关键词归类（库内为繁体），顺序即优先级。
    # 辅助筛选层，非学术定级；规则可随使用反馈迭代。
    _ASSOC_CATEGORY_RULES = [
        ("学术教育", ["師", "學", "問學", "講學", "從學", "受業", "弟子", "門人", "門孫", "同學",
                      "游學", "書院", "執教", "及門", "登門", "問道", "切磋", "師法", "同門",
                      "課讀", "訓導", "學術", "儒學", "同硯", "硯席", "學徒", "教席", "志業",
                      "職業", "科舉", "場屋", "應舉", "同年"]),
        ("婚姻亲属", ["婚", "娶", "嫁", "岳", "翁", "婿", "姻", "妻", "締親", "結親", "親家", "聘為", "聘娶", "養育"]),
        ("丧葬纪念", ["墓", "墳", "棺", "喪", "葬", "塔", "諡", "挽", "祭", "神道", "壙", "誌",
                      "書丹", "填諱", "碑", "去思", "遺愛", "德政", "生祠", "舍利", "銘", "誄",
                      "哀辭", "諱", "追悼", "悼念", "弔", "酹"]),
        ("宗教方外", ["僧", "法嗣", "禪", "寺", "佛", "住持", "法師", "剃度", "受戒", "醮",
                      "道觀", "羽士", "方外", "高僧", "道", "羽客", "俗講", "轉經", "唸佛"]),
        ("法律诉讼", ["原告", "被告", "訟", "訴", "獄", "冤", "彈劾", "告發", "首告", "斷案", "審理"]),
        ("军事戎务", ["征", "戰", "軍", "戍", "兵", "討伐", "從軍", "戎", "禦", "防禦", "征討", "平亂", "剿", "部將"]),
        ("刑戮迫害", ["謀殺", "處決", "殺害", "逮捕", "鞫治"]),
        ("艺术赏鉴", ["畫", "書法", "琴", "棋", "鑒賞", "收藏", "題畫", "畫像", "圖譜", "臨摹", "摹", "拓"]),
        ("财物往来", ["贈物", "贈財", "餽", "賄", "借貸", "債", "賂", "賚", "賜", "俸", "祿",
                      "賑", "捐獻", "田疇", "田產", "莊宅", "贈金", "贈銀", "贈米", "贈糧", "貸"]),
        ("政治行政", ["薦", "舉薦", "辟", "除授", "貶", "上司", "下屬", "屬官", "幕僚", "同僚",
                      "黨", "朋附", "保任", "提攜", "陞遷", "左遷", "拜官", "差遣", "謀主", "策士",
                      "游說", "獻策", "諫", "議政", "論政", "入對", "召對", "扈從", "潛邸", "輔弼",
                      "勸進", "稱帝", "納諫", "封事", "廷", "掾", "參軍", "判官", "推官", "巡檢",
                      "通判", "知州", "知府", "知縣", "縣令", "縣丞", "主簿", "尉", "屬吏",
                      "恩主", "支持", "排擠", "主政", "政策", "謀士", "門客", "赦免"]),
        ("文学创作", ["序", "跋", "詩", "詞", "曲", "賦", "箴", "頌", "贊", "祭文", "祝文",
                      "代筆", "屬文", "屬稿", "撰述", "著述", "刊刻", "評論", "題", "篆", "抄",
                      "鈔", "校勘", "注疏", "箋", "翻譯", "選編", "輯錄", "作記", "書信", "尺牘",
                      "寄書", "遺書", "惠書", "報書", "贈詩", "贈文", "贈言", "投贈", "贈別",
                      "唱和", "聯句", "分韻", "和詩", "和韻", "次韻", "依韻", "酬唱", "屬和",
                      "誄", "青詞", "樂章", "對聯", "匾額", "器銘", "文會", "詩社",
                      "義莊記", "作傳", "傳記", "字說", "名述", "文風"]),
        ("交游应酬", ["會", "訪", "飲宴", "遊", "游", "送別", "結義", "訂交", "訂盟", "聚會",
                      "雅集", "詩會", "酒會", "泛舟", "清談", "劇談", "過從", "往還", "通問",
                      "書尺", "音問", "省候", "候問", "起居", "攀談", "握手", "賞花", "賞月",
                      "賞雪", "觀潮", "聽琴", "看棋", "宴集", "宴飲", "餞", "餞別", "祖餞",
                      "友", "同鄉", "相識", "不合"]),
        ("医疗照护", ["醫", "藥", "侍疾", "侍病", "視疾", "問疾", "調護", "湯藥", "針灸"]),
    ]

    @classmethod
    def _assoc_category(cls, desc_chn):
        for cat, kws in cls._ASSOC_CATEGORY_RULES:
            if any(k in desc_chn for k in kws):
                return cat
        return "其他"

    _ASSOC_QUERY_SYNONYMS = {
        "師": ["師", "門人", "弟子", "問學", "從學", "受業", "執教", "講學", "門孫", "學徒", "及門"],
        "师": ["師", "門人", "弟子", "問學", "從學", "受業", "執教", "講學", "門孫", "學徒", "及門"],
        "門生": ["門人", "弟子", "門孫", "及門", "登門", "受業", "學徒"],
        "门生": ["門人", "弟子", "門孫", "及門", "登門", "受業", "學徒"],
        "學生": ["門人", "弟子", "問學", "從學", "受業", "學徒"],
        "学生": ["門人", "弟子", "問學", "從學", "受業", "學徒"],
        "同年": ["同年", "同榜", "同科", "同第", "同登", "同舉", "同選", "同貢"],
        "同僚": ["同僚", "僚", "同官", "同寅", "寅恭", "僚友", "同署", "同衙"],
        "薦": ["薦", "舉薦", "保任", "推薦", "薦舉", "薦辟"],
        "举荐": ["薦", "舉薦", "保任", "推薦", "薦舉", "薦辟"],
        "墓誌": ["墓誌", "神道", "壙誌", "墓銘", "碑", "銘", "書丹", "填諱", "墓", "葬"],
        "墓志": ["墓誌", "神道", "壙誌", "墓銘", "碑", "銘", "書丹", "填諱", "墓", "葬"],
        "序": ["作序", "請序", "序", "跋", "題跋"],
        "跋": ["跋", "題跋", "作跋"],
        "僧": ["僧", "法嗣", "禪", "住持", "法師", "剃度", "受戒", "高僧"],
        "婚": ["婚", "娶", "嫁", "姻", "締親", "結親", "親家"],
    }

    @classmethod
    def search_assoc_types(cls, q=None, category=None):
        """社会关系类型字典（ASSOC_CODES 全量 ~490 条，带大类标签与配对码）。
        q 支持中文/英文关键词（简繁自动，内置常见同义词扩展）；category 按大类过滤。"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        if q:
            terms = [q]
            for key, extras in cls._ASSOC_QUERY_SYNONYMS.items():
                if key in q:
                    terms.extend(extras)
                    break
            variants = []
            for t in terms:
                variants.extend(name_variants(t))
            variants = list(dict.fromkeys(variants))
            conditions, params = [], []
            for col in ("c_assoc_desc_chn", "c_assoc_desc"):
                for v in variants:
                    conditions.append(f"{col} LIKE ?")
                    params.append(f"%{v}%")
            sql = f"""
                SELECT c_assoc_code, c_assoc_desc_chn, c_assoc_desc, c_assoc_pair
                FROM ASSOC_CODES
                WHERE ({' OR '.join(conditions)}) AND c_assoc_code > 0
                ORDER BY c_assoc_code
            """
            cursor.execute(sql, params)
        else:
            cursor.execute("""
                SELECT c_assoc_code, c_assoc_desc_chn, c_assoc_desc, c_assoc_pair
                FROM ASSOC_CODES WHERE c_assoc_code > 0 ORDER BY c_assoc_code
            """)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            desc_chn = safe_decode(r.c_assoc_desc_chn) or ""
            cat = cls._assoc_category(desc_chn)
            if category and cat != category:
                continue
            pair = r.c_assoc_pair
            try:
                pair = int(pair) if pair is not None else None
            except (ValueError, TypeError):
                pair = None
            results.append({
                "code": r.c_assoc_code,
                "name_chn": desc_chn,
                "name_eng": r.c_assoc_desc or "",
                "pair": pair,
                "category": cat,
            })
        return results

    @classmethod
    def assoc_type_by_code(cls, code):
        code = int(code)
        for t in cls.search_assoc_types():
            if t["code"] == code:
                return t
        return None

    @classmethod
    def persons_by_assoc(cls, code, pair=False, from_year=None, to_year=None,
                         dynasty_code=None, limit=500):
        """社会关系检索（CBDB 原生十大模块之五）：按关系类型返回人物对 A—关系→B。
        pair=True 时把配对关系（如 師長↔門生 互为 pair）一并纳入；
        支持年份区间、朝代（A 或 B 属该朝）过滤。
        返回 {total, relations, persons}：persons 为去重人物列表，供范围传递/导出。"""
        conn = cls.get_conn()
        if not conn:
            return {"total": 0, "relations": [], "persons": []}
        cursor = conn.cursor()
        codes = [int(code)]
        if pair:
            t = cls.assoc_type_by_code(code)
            if t and t.get("pair") and t["pair"] != int(code):
                codes.append(t["pair"])
        marks = ",".join("?" * len(codes))
        where = f"a.c_assoc_code IN ({marks}) AND a.c_assoc_id > 0"
        params = list(codes)
        if from_year:
            where += " AND a.c_assoc_year >= ?"
            params.append(int(from_year))
        if to_year:
            where += " AND a.c_assoc_year <= ?"
            params.append(int(to_year))
        if dynasty_code:
            where += " AND (b1.c_dy = ? OR b2.c_dy = ?)"
            params += [int(dynasty_code), int(dynasty_code)]

        # Access 接受线性括号链 JOIN；d1/d2 必须包进同一括号链，不能追加在链外
        base_from = """
            FROM (((((ASSOC_DATA a
            LEFT JOIN ASSOC_CODES ac ON a.c_assoc_code = ac.c_assoc_code)
            LEFT JOIN BIOG_MAIN b1 ON a.c_personid = b1.c_personid)
            LEFT JOIN BIOG_MAIN b2 ON a.c_assoc_id = b2.c_personid)
            LEFT JOIN DYNASTIES d1 ON b1.c_dy = d1.c_dy)
            LEFT JOIN DYNASTIES d2 ON b2.c_dy = d2.c_dy)
        """
        cursor.execute(f"SELECT COUNT(*) AS n {base_from} WHERE {where}", params)
        total = cursor.fetchone().n

        sql = f"""
            SELECT TOP {int(limit)} a.c_personid, a.c_assoc_id, a.c_assoc_year, a.c_text_title,
                   ac.c_assoc_desc_chn,
                   b1.c_name AS a_name, b1.c_name_chn AS a_name_chn,
                   b1.c_surname_chn AS a_su, b1.c_mingzi_chn AS a_mi,
                   b1.c_dy AS a_dy, d1.c_dynasty_chn AS a_dyn,
                   b2.c_name AS b_name, b2.c_name_chn AS b_name_chn,
                   b2.c_surname_chn AS b_su, b2.c_mingzi_chn AS b_mi,
                   b2.c_dy AS b_dy, d2.c_dynasty_chn AS b_dyn
            {base_from}
            WHERE {where}
            ORDER BY a.c_assoc_year, a.c_personid
        """
        cursor.execute(sql, params)
        relations = []
        seen_ids = {}
        order = []
        for r in cursor.fetchall():
            a_name = safe_decode(r.a_name_chn) or (safe_decode(r.a_su) + safe_decode(r.a_mi)) or r.a_name or f"人物{r.c_personid}"
            b_name = safe_decode(r.b_name_chn) or (safe_decode(r.b_su) + safe_decode(r.b_mi)) or r.b_name or f"人物{r.c_assoc_id}"
            relations.append({
                "a_id": r.c_personid, "a_name": a_name,
                "b_id": r.c_assoc_id, "b_name": b_name,
                "relation": safe_decode(r.c_assoc_desc_chn) or "關聯",
                "year": r.c_assoc_year or None,
                "text": safe_decode(r.c_text_title) or "",
                "a_dynasty": safe_decode(r.a_dyn) or "",
                "b_dynasty": safe_decode(r.b_dyn) or "",
            })
            for pid, nm, dyn in ((r.c_personid, a_name, r.a_dyn), (r.c_assoc_id, b_name, r.b_dyn)):
                if pid and pid > 0 and pid not in seen_ids:
                    seen_ids[pid] = {"id": pid, "name_chn": nm,
                                     "dynasty": safe_decode(dyn) or "未知"}
                    order.append(pid)
        return {"total": total, "relations": relations,
                "persons": [seen_ids[i] for i in order]}

    @classmethod
    def persons_by_year(cls, year, dynasty_code=None, person_ids=None, entry_code=None, limit=300):
        """年份检索（CBDB 原生）：某年在世的人物。
        在世 = 生卒年夹住 Y，或活跃期（flourished）夹住 Y。
        person_ids 可选：仅在该人物列表范围内检索（跨查询列表传递）。
        entry_code 可选：仅某入仕方式（如进士）的人物，ENTRY_DATA EXISTS 子查询。"""
        conn = cls.get_conn()
        if not conn:
            return {"total": 0, "persons": []}
        cursor = conn.cursor()
        where = (
            "(((b.c_birthyear > 0 AND b.c_birthyear <= ?) "
            "AND (b.c_deathyear > 0 AND b.c_deathyear >= ?)) "
            "OR ((b.c_fl_earliest_year > 0 AND b.c_fl_earliest_year <= ?) "
            "AND (b.c_fl_latest_year > 0 AND b.c_fl_latest_year >= ?)))"
        )
        params = [int(year), int(year), int(year), int(year)]
        if dynasty_code:
            where += " AND b.c_dy = ?"
            params.append(int(dynasty_code))
        if entry_code:
            where += (" AND EXISTS (SELECT 1 FROM ENTRY_DATA e "
                      "WHERE e.c_personid = b.c_personid AND e.c_entry_code = ?)")
            params.append(int(entry_code))
        if person_ids is not None:
            where += " AND " + _in_clause("b.c_personid", person_ids, params)

        cursor.execute(f"SELECT COUNT(*) AS n FROM BIOG_MAIN b WHERE {where}", params)
        total = cursor.fetchone().n

        sql = f"""
            SELECT TOP {limit} b.c_personid, b.c_name, b.c_name_chn,
                   b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, b.c_index_year,
                   b.c_dy, d.c_dynasty_chn
            FROM BIOG_MAIN b
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
            WHERE {where}
            ORDER BY b.c_index_year, b.c_personid
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        persons = []
        for r in rows:
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
            persons.append({
                "id": r.c_personid,
                "name": r.c_name or "",
                "name_chn": name_chn,
                "birthyear": r.c_birthyear,
                "deathyear": r.c_deathyear,
                "index_year": r.c_index_year or None,
                "dynasty_code": r.c_dy,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
            })
        return {"total": total, "persons": persons}

    # ── 六期：原生窗体补全（两人关系/地区关系/群体网络/按人群查询）──

    @classmethod
    def _place_person_ids(cls, cursor, addr_id, include_same_coord=False, cap=3000):
        """与某地相关的人物 ID 集合：籍贯/居址（BIOG_ADDR_DATA）+ 任职地（POSTED_TO_ADDR_DATA）
        + 索引地址（BIOG_MAIN.c_index_addr_id）；可选并入同坐标地址（原生功能）。"""
        if include_same_coord:
            ids = cls._same_coord_addr_ids(cursor, addr_id)
        else:
            ids = [int(addr_id)]
        in_clause = ",".join("?" for _ in ids)
        found = set()
        cursor.execute(
            f"SELECT c_personid FROM BIOG_ADDR_DATA WHERE c_addr_id IN ({in_clause})", ids)
        for r in cursor.fetchall():
            if r.c_personid:
                found.add(r.c_personid)
        cursor.execute(
            f"SELECT c_personid FROM POSTED_TO_ADDR_DATA WHERE c_addr_id IN ({in_clause})", ids)
        for r in cursor.fetchall():
            if r.c_personid:
                found.add(r.c_personid)
        cursor.execute(
            f"SELECT c_personid FROM BIOG_MAIN WHERE c_index_addr_id IN ({in_clause})", ids)
        for r in cursor.fetchall():
            if r.c_personid:
                found.add(r.c_personid)
        return sorted(found)[:cap]

    @classmethod
    def assoc_between(cls, a, b):
        """两人社会关系（原生 Query Pair-wise Associations）：
        A→B 与 B→A 全部社会关系记录；另附两人直系亲属直查（含五服，复用亲属索引）。"""
        conn = cls.get_conn()
        if not conn:
            return {"error": "CBDB 本地数据库未连接"}
        cursor = conn.cursor()
        a, b = int(a), int(b)

        cursor.execute("""
            SELECT b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM BIOG_MAIN b LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
            WHERE b.c_personid IN (?, ?)
        """, a, b)
        persons = {}
        for r in cursor.fetchall():
            surname = safe_decode(r.c_surname_chn)
            mingzi = safe_decode(r.c_mingzi_chn)
            persons[r.c_personid] = {
                "id": r.c_personid,
                "name_chn": safe_decode(r.c_name_chn) or (surname + mingzi) or r.c_name or f"人物{r.c_personid}",
                "name": r.c_name or "",
                "birthyear": r.c_birthyear, "deathyear": r.c_deathyear,
                "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
            }
        if len(persons) < 2:
            conn.close()
            return {"error": "人物 ID 无效（至少一方不存在）"}

        cursor.execute("""
            SELECT a.c_personid, a.c_assoc_id, a.c_assoc_year, a.c_text_title,
                   ac.c_assoc_desc_chn
            FROM ASSOC_DATA a LEFT JOIN ASSOC_CODES ac ON a.c_assoc_code = ac.c_assoc_code
            WHERE (a.c_personid = ? AND a.c_assoc_id = ?)
               OR (a.c_personid = ? AND a.c_assoc_id = ?)
            ORDER BY a.c_assoc_year
        """, a, b, b, a)
        relations = [{
            "from_id": r.c_personid,
            "from_name": persons.get(r.c_personid, {}).get("name_chn", str(r.c_personid)),
            "to_id": r.c_assoc_id,
            "to_name": persons.get(r.c_assoc_id, {}).get("name_chn", str(r.c_assoc_id)),
            "relation": safe_decode(r.c_assoc_desc_chn) or "關聯",
            "year": r.c_assoc_year or None,
            "text": safe_decode(r.c_text_title) or "",
        } for r in cursor.fetchall()]

        kin = []
        idx = cls._load_kin_index()
        if idx:
            out_edges, kinship, mourning = idx
            for src, dst in ((a, b), (b, a)):
                for k2, code in out_edges.get(src, []):
                    if k2 != dst:
                        continue
                    ks = kinship.get(code) or {}
                    rel = (ks.get("rel") or "").strip()
                    mo = _mourning_lookup(rel, mourning) if rel else {}
                    kin.append({
                        "from_id": src, "from_name": persons[src]["name_chn"],
                        "to_id": dst, "to_name": persons[dst]["name_chn"],
                        "relation": mo.get("rel_chn") or ks.get("chn") or "親屬",
                        "mourning": mo.get("mourning") or "",
                        "kintype": mo.get("kintype") or "",
                    })
        conn.close()
        return {"a": persons[a], "b": persons[b], "relations": relations, "kin": kin}

    @classmethod
    def persons_by_place_assoc(cls, addr_id, code=None, pair=False, from_year=None, to_year=None,
                               include_same_coord=False, both_in=False, limit=500):
        """地区关系检索（原生 Query Place Associations）：
        某地相关人物（籍贯/居址/任职地/索引地址）之间的社会关系；
        可选关系类型（含配对并入）/年份区间过滤；both_in=True 时仅保留双方均在该地区的人物对。
        返回 {total, relations, persons, place_persons}。"""
        conn = cls.get_conn()
        if not conn:
            return {"error": "CBDB 本地数据库未连接", "total": 0, "relations": [], "persons": []}
        cursor = conn.cursor()

        ids = cls._place_person_ids(cursor, addr_id, include_same_coord)
        if not ids:
            conn.close()
            return {"total": 0, "relations": [], "persons": [], "place_persons": 0}
        if both_in and len(ids) > 1500:
            ids = ids[:1500]  # 双 IN 参数翻倍，截断防 Access 参数上限
        params = []
        where = _in_clause("a.c_personid", ids, params)
        if both_in:
            where += " AND " + _in_clause("a.c_assoc_id", ids, params)
        else:
            where += " AND a.c_assoc_id > 0"
        codes = []
        if code:
            codes = [int(code)]
            if pair:
                t = cls.assoc_type_by_code(code)
                if t and t.get("pair") and t["pair"] != int(code):
                    codes.append(t["pair"])
        if codes:
            where += " AND a.c_assoc_code IN (" + ",".join("?" * len(codes)) + ")"
            params += codes
        if from_year:
            where += " AND a.c_assoc_year >= ?"
            params.append(int(from_year))
        if to_year:
            where += " AND a.c_assoc_year <= ?"
            params.append(int(to_year))
        base_from = """
            FROM (((((ASSOC_DATA a
            LEFT JOIN ASSOC_CODES ac ON a.c_assoc_code = ac.c_assoc_code)
            LEFT JOIN BIOG_MAIN b1 ON a.c_personid = b1.c_personid)
            LEFT JOIN BIOG_MAIN b2 ON a.c_assoc_id = b2.c_personid)
            LEFT JOIN DYNASTIES d1 ON b1.c_dy = d1.c_dy)
            LEFT JOIN DYNASTIES d2 ON b2.c_dy = d2.c_dy)
        """
        cursor.execute(f"SELECT COUNT(*) AS n {base_from} WHERE {where}", params)
        total = cursor.fetchone().n
        sql = f"""
            SELECT TOP {int(limit)} a.c_personid, a.c_assoc_id, a.c_assoc_year, a.c_text_title,
                   ac.c_assoc_desc_chn,
                   b1.c_name AS a_name, b1.c_name_chn AS a_name_chn,
                   b1.c_surname_chn AS a_su, b1.c_mingzi_chn AS a_mi, d1.c_dynasty_chn AS a_dyn,
                   b2.c_name AS b_name, b2.c_name_chn AS b_name_chn,
                   b2.c_surname_chn AS b_su, b2.c_mingzi_chn AS b_mi, d2.c_dynasty_chn AS b_dyn
            {base_from}
            WHERE {where}
            ORDER BY a.c_assoc_year, a.c_personid
        """
        cursor.execute(sql, params)
        relations = []
        seen = {}
        order = []
        for r in cursor.fetchall():
            a_name = safe_decode(r.a_name_chn) or (safe_decode(r.a_su) + safe_decode(r.a_mi)) or r.a_name or f"人物{r.c_personid}"
            b_name = safe_decode(r.b_name_chn) or (safe_decode(r.b_su) + safe_decode(r.b_mi)) or r.b_name or f"人物{r.c_assoc_id}"
            relations.append({
                "a_id": r.c_personid, "a_name": a_name,
                "b_id": r.c_assoc_id, "b_name": b_name,
                "relation": safe_decode(r.c_assoc_desc_chn) or "關聯",
                "year": r.c_assoc_year or None,
                "text": safe_decode(r.c_text_title) or "",
                "a_dynasty": safe_decode(r.a_dyn) or "",
                "b_dynasty": safe_decode(r.b_dyn) or "",
            })
            for pid, nm, dyn in ((r.c_personid, a_name, r.a_dyn), (r.c_assoc_id, b_name, r.b_dyn)):
                if pid and pid > 0 and pid not in seen:
                    seen[pid] = {"id": pid, "name_chn": nm, "dynasty": safe_decode(dyn) or "未知"}
                    order.append(pid)
        conn.close()
        return {"total": total, "relations": relations,
                "persons": [seen[i] for i in order],
                "place_persons": len(ids)}

    @classmethod
    def network_group(cls, person_ids, include_kin=False, up=1, down=1, col=0, mar=0,
                      dynasty_code=None, limit=500):
        """群体社会关系网络（原生 Query Social Networks 窗体）：
        对一组人物（来自任意检索结果）查他们彼此之间的社会关系；
        include_kin=True 混入亲属（≤80 人时按先世/后世/旁系/姻亲四参数 BFS 外延，否则仅组内直边）。
        返回 {nodes, edges, meta}；edge 带 kind: assoc|kin，与单人网络同构。"""
        conn = cls.get_conn()
        if not conn:
            return {"nodes": [], "edges": []}
        cursor = conn.cursor()
        ids = []
        seen = set()
        for i in person_ids:
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if i > 0 and i not in seen:
                seen.add(i)
                ids.append(i)
            if len(ids) >= 500:
                break
        if not ids:
            conn.close()
            return {"nodes": [], "edges": [], "meta": {"group_size": 0}}

        params = []
        where = (_in_clause("a.c_personid", ids, params)
                 + " AND " + _in_clause("a.c_assoc_id", ids, params)
                 + " AND a.c_assoc_id > 0")
        cursor.execute(f"""
            SELECT a.c_personid, a.c_assoc_id, a.c_assoc_year,
                   ac.c_assoc_desc_chn
            FROM (ASSOC_DATA a
            LEFT JOIN ASSOC_CODES ac ON a.c_assoc_code = ac.c_assoc_code)
            WHERE {where}
        """, params)
        edges = []
        involved = set()
        for r in cursor.fetchall():
            edges.append({"source": r.c_personid, "target": r.c_assoc_id,
                          "relation": safe_decode(r.c_assoc_desc_chn) or "關聯",
                          "kind": "assoc", "year": r.c_assoc_year or None})
            involved.add(r.c_personid)
            involved.add(r.c_assoc_id)
        meta = {"group_size": len(ids), "assoc_edges": len(edges)}

        if include_kin:
            idx = cls._load_kin_index()
            if idx:
                out_edges, kinship, mourning = idx
                gid = set(ids)
                kin_added = 0
                for pid in ids:
                    for k2, code in out_edges.get(pid, []):
                        if k2 not in gid:
                            continue
                        ks = kinship.get(code) or {}
                        rel = (ks.get("rel") or "").strip()
                        mo = _mourning_lookup(rel, mourning) if rel else {}
                        edges.append({"source": pid, "target": k2,
                                      "relation": mo.get("rel_chn") or ks.get("chn") or "親屬",
                                      "kind": "kin", "year": None})
                        involved.add(k2)
                        kin_added += 1
                meta["kin_edges"] = kin_added
                if len(ids) <= 80:
                    from collections import deque
                    up, down, col, mar = int(up), int(down), int(col), int(mar)
                    extra = set()
                    for root in ids:
                        if len(extra) > 800:
                            break
                        visited = {root}
                        q = deque([(root, 0, 0, 0, 0)])
                        while q:
                            pid, u, d, m, c = q.popleft()
                            for k2, code in out_edges.get(pid, []):
                                if k2 in visited or k2 in gid:
                                    continue
                                ks = kinship.get(code)
                                if not ks or ks["up"] >= 99 or ks["down"] >= 99:
                                    continue
                                if ks["up"] == 0 and ks["down"] == 0 and ks["mar"] == 0 and ks["col"] == 0:
                                    continue
                                nu, nd, nm, nc = (u + ks["up"], d + ks["down"],
                                                  m + ks["mar"], c + ks["col"])
                                if nu > up or nd > down or nm > mar or nc > col:
                                    continue
                                visited.add(k2)
                                edges.append({"source": pid, "target": k2,
                                              "relation": ks.get("chn") or "親屬",
                                              "kind": "kin", "year": None})
                                involved.add(k2)
                                extra.add(k2)
                                if len(extra) > 800:
                                    q.clear()
                                    break
                                q.append((k2, nu, nd, nm, nc))
                    meta["kin_expanded"] = len(extra)

        involved = sorted(involved)[:1500]
        nodes = []
        if involved:
            info = {}
            CHUNK = 500
            for i in range(0, len(involved), CHUNK):
                chunk = involved[i:i + CHUNK]
                ph = ",".join("?" for _ in chunk)
                cursor.execute(f"""
                    SELECT b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                           b.c_dy, d.c_dynasty_chn
                    FROM BIOG_MAIN b LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
                    WHERE b.c_personid IN ({ph})
                """, *chunk)
                for r in cursor.fetchall():
                    info[r.c_personid] = r
            for pid in involved:
                r = info.get(pid)
                if not r:
                    continue
                if dynasty_code and (r.c_dy or 0) != int(dynasty_code) and pid not in seen:
                    continue  # 朝代限定时外围节点过滤（组内成员始终保留）
                surname = safe_decode(r.c_surname_chn)
                mingzi = safe_decode(r.c_mingzi_chn)
                nodes.append({
                    "id": pid,
                    "name": safe_decode(r.c_name_chn) or (surname + mingzi) or r.c_name or f"人物{pid}",
                    "dynasty": safe_decode(r.c_dynasty_chn) or "",
                    "center": False,
                    "member": pid in seen,
                })
        conn.close()
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]
        return {"nodes": nodes, "edges": edges, "meta": meta}

    @classmethod
    def group_data(cls, person_ids, limit=500):
        """按人群查询（原生 Look Up Data on a Group of People）：
        一批人物的属性总表：姓名/朝代/生卒/索引年/性别/籍贯/入仕/官职/社会区分/著作数/亲属数/社会关系数。
        所有属性表分批 IN 查询后在内存组装，一人一行的扁平表（可 CSV）。"""
        conn = cls.get_conn()
        if not conn:
            return {"total": 0, "rows": []}
        cursor = conn.cursor()
        ids = []
        seen = set()
        for i in person_ids:
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if i > 0 and i not in seen:
                seen.add(i)
                ids.append(i)
            if len(ids) >= limit:
                break
        if not ids:
            conn.close()
            return {"total": 0, "rows": []}
        CHUNK = 500
        rows = {}
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            ph = ",".join("?" for _ in chunk)
            cursor.execute(f"""
                SELECT b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                       b.c_birthyear, b.c_deathyear, b.c_index_year, b.c_female, b.c_dy,
                       d.c_dynasty_chn, ad.c_name_chn AS native_place
                FROM ((BIOG_MAIN b
                LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
                LEFT JOIN ADDR_CODES ad ON b.c_index_addr_id = ad.c_addr_id)
                WHERE b.c_personid IN ({ph})
            """, *chunk)
            for r in cursor.fetchall():
                surname = safe_decode(r.c_surname_chn)
                mingzi = safe_decode(r.c_mingzi_chn)
                rows[r.c_personid] = {
                    "id": r.c_personid,
                    "name_chn": safe_decode(r.c_name_chn) or (surname + mingzi) or r.c_name or "",
                    "name": r.c_name or "",
                    "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                    "birthyear": r.c_birthyear, "deathyear": r.c_deathyear,
                    "index_year": r.c_index_year or None,
                    "female": bool(r.c_female),
                    "native_place": safe_decode(getattr(r, "native_place", None)) or "",
                    "entry": "", "offices": "", "statuses": "",
                    "texts_count": 0, "kin_count": 0, "assoc_count": 0,
                }

        # 入仕（每人取最早一条）
        entries = {}
        entry_codes = set()
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            ph = ",".join("?" for _ in chunk)
            cursor.execute(
                f"SELECT c_personid, c_entry_code, c_year FROM ENTRY_DATA "
                f"WHERE c_personid IN ({ph}) ORDER BY c_year", *chunk)
            for r in cursor.fetchall():
                if r.c_personid not in entries:
                    entries[r.c_personid] = {"code": r.c_entry_code, "year": r.c_year}
                    entry_codes.add(r.c_entry_code)
        if entry_codes:
            codes_sorted = sorted(entry_codes)
            ph = ",".join("?" for _ in codes_sorted)
            cursor.execute(
                f"SELECT c_entry_code, c_entry_desc_chn FROM ENTRY_CODES "
                f"WHERE c_entry_code IN ({ph})", *codes_sorted)
            edesc = {r.c_entry_code: safe_decode(r.c_entry_desc_chn)
                     for r in cursor.fetchall()}
            for pid, e in entries.items():
                if pid in rows:
                    rows[pid]["entry"] = (edesc.get(e["code"]) or str(e["code"])) + (
                        f" {e['year']}" if e["year"] else "")

        # 官职（每人前 2 任，按起始年）
        offs = {}
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            ph = ",".join("?" for _ in chunk)
            cursor.execute(f"""
                SELECT p.c_personid, o.c_office_chn, p.c_firstyear, p.c_lastyear
                FROM POSTED_TO_OFFICE_DATA p
                LEFT JOIN OFFICE_CODES o ON p.c_office_id = o.c_office_id
                WHERE p.c_personid IN ({ph})
                ORDER BY p.c_personid, p.c_firstyear
            """, *chunk)
            for r in cursor.fetchall():
                o = safe_decode(r.c_office_chn)
                if not o:
                    continue
                item = o + (f"({r.c_firstyear})" if r.c_firstyear else "")
                offs.setdefault(r.c_personid, []).append(item)
        for pid, lst in offs.items():
            if pid in rows:
                rows[pid]["offices"] = "、".join(lst[:2]) + (
                    f" 等{len(lst)}任" if len(lst) > 2 else "")

        # 社会区分（每人前 3 项）
        sts = {}
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            ph = ",".join("?" for _ in chunk)
            cursor.execute(f"""
                SELECT s.c_personid, sc.c_status_desc_chn
                FROM STATUS_DATA s
                LEFT JOIN STATUS_CODES sc ON s.c_status_code = sc.c_status_code
                WHERE s.c_personid IN ({ph})
            """, *chunk)
            for r in cursor.fetchall():
                v = safe_decode(r.c_status_desc_chn)
                if v:
                    sts.setdefault(r.c_personid, []).append(v)
        for pid, lst in sts.items():
            if pid in rows:
                rows[pid]["statuses"] = "、".join(lst[:3])

        # 著作/亲属/社会关系计数
        for table, key in (("BIOG_TEXT_DATA", "texts_count"),
                           ("KIN_DATA", "kin_count"),
                           ("ASSOC_DATA", "assoc_count")):
            for i in range(0, len(ids), CHUNK):
                chunk = ids[i:i + CHUNK]
                ph = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT c_personid, COUNT(*) AS n FROM {table} "
                    f"WHERE c_personid IN ({ph}) GROUP BY c_personid", *chunk)
                for r in cursor.fetchall():
                    if r.c_personid in rows:
                        rows[r.c_personid][key] = r.n
        conn.close()
        return {"total": len(rows), "rows": [rows[i] for i in ids if i in rows]}

    # ── 亲属递归索引（懒加载，进程内常驻内存；53.7 万边全量加载约 2.5s）──
    _kin_index = None  # (out_edges, kinship_map, mourning_map)

    @classmethod
    def _load_kin_index(cls):
        if cls._kin_index is not None:
            return cls._kin_index
        conn = cls.get_conn()
        if not conn:
            return None
        cursor = conn.cursor()
        out_edges = {}
        cursor.execute("SELECT c_personid, c_kin_id, c_kin_code FROM KIN_DATA")
        for r in cursor.fetchall():
            out_edges.setdefault(r.c_personid, []).append((r.c_kin_id, r.c_kin_code))
        kinship = {}
        cursor.execute(
            "SELECT c_kincode, c_upstep, c_dwnstep, c_marstep, c_colstep, "
            "c_kinrel, c_kinrel_chn FROM KINSHIP_CODES"
        )
        for r in cursor.fetchall():
            try:
                kinship[int(r.c_kincode)] = {
                    "up": int(r.c_upstep or 0), "down": int(r.c_dwnstep or 0),
                    "mar": int(r.c_marstep or 0), "col": int(r.c_colstep or 0),
                    "rel": (r.c_kinrel or "").strip(), "chn": safe_decode(r.c_kinrel_chn) or "",
                }
            except Exception:
                pass
        mourning = {}
        cursor.execute(
            "SELECT c_kinrel, c_kinrel_chn, c_mourning_chn, c_kintype_desc_chn, c_kindist "
            "FROM KIN_Mourning"
        )
        for r in cursor.fetchall():
            rel = (r.c_kinrel or "").strip()
            if rel:
                mourning[rel] = {
                    "rel_chn": safe_decode(r.c_kinrel_chn) or "",
                    "mourning": safe_decode(r.c_mourning_chn) or "",
                    "kintype": safe_decode(r.c_kintype_desc_chn) or "",
                    "kindist": r.c_kindist or "",
                }
        conn.close()
        cls._kin_index = (out_edges, kinship, mourning)
        return cls._kin_index

    @classmethod
    def get_person_kin_recursive(cls, person_id, up=2, down=2, col=1, mar=1, limit=5000):
        """亲属递归检索（复刻 CBDB 原生四参数）：先世/后世/旁系/姻亲步数限制。
        沿 KIN_DATA 有向边 BFS，每边按 KINSHIP_CODES 的四步维度累加，任一超限即剪枝；
        路径关系符号串（如 FBS）查 KIN_Mourning 得五服。原生循环上限 5000。"""
        idx = cls._load_kin_index()
        if not idx:
            return {"error": "亲属索引加载失败"}
        out_edges, kinship, mourning = idx
        up, down, col, mar = int(up), int(down), int(col), int(mar)
        root = int(person_id)

        visited = {root}
        from collections import deque
        queue = deque([(root, 0, 0, 0, 0, "")])  # pid, up, down, mar, col, path_rel
        found = []  # (pid, path_rel, up, down, mar, col, edge_code)
        truncated = False
        while queue:
            pid, u, d, m, c, path = queue.popleft()
            for k2, code in out_edges.get(pid, []):
                if k2 in visited:
                    continue
                ks = kinship.get(code)
                if not ks:
                    continue
                # 99 步 = 代数未知（G-n 类），缺失数据边不参与递归
                if ks["up"] >= 99 or ks["down"] >= 99:
                    continue
                if ks["up"] == 0 and ks["down"] == 0 and ks["mar"] == 0 and ks["col"] == 0:
                    continue
                nu, nd, nm, nc = u + ks["up"], d + ks["down"], m + ks["mar"], c + ks["col"]
                if nu > up or nd > down or nm > mar or nc > col:
                    continue
                visited.add(k2)
                new_path = path + ks["rel"]
                found.append((k2, new_path, nu, nd, nm, nc, code))
                if len(found) >= limit:
                    truncated = True
                    queue.clear()
                    break
                queue.append((k2, nu, nd, nm, nc, new_path))

        persons = []
        if found:
            conn = cls.get_conn()
            if conn:
                cursor = conn.cursor()
                ids = [f[0] for f in found]
                info = {}
                CHUNK = 500  # Access IN 参数过多会 HY001，分片
                for i in range(0, len(ids), CHUNK):
                    chunk = ids[i:i + CHUNK]
                    ph = ",".join("?" for _ in chunk)
                    cursor.execute(f"""
                        SELECT b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                               b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
                        FROM BIOG_MAIN b LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
                        WHERE b.c_personid IN ({ph})
                    """, *chunk)
                    for r in cursor.fetchall():
                        info[r.c_personid] = r
                conn.close()
                for pid, path, nu, nd, nm, nc, code in found:
                    r = info.get(pid)
                    if not r:
                        continue
                    surname = safe_decode(r.c_surname_chn)
                    mingzi = safe_decode(r.c_mingzi_chn)
                    name_chn = safe_decode(r.c_name_chn) or (surname + mingzi)
                    mo = _mourning_lookup(path, mourning)
                    last_ks = kinship.get(code) or {}
                    persons.append({
                        "id": pid,
                        "name": r.c_name or "",
                        "name_chn": name_chn or f"人物{pid}",
                        "birthyear": r.c_birthyear,
                        "deathyear": r.c_deathyear,
                        "dynasty": safe_decode(r.c_dynasty_chn) or "未知",
                        "path_rel": path,
                        "relation": mo.get("rel_chn") or _describe_kin_path(path) or last_ks.get("chn") or "亲属",
                        "mourning": mo.get("mourning") or "",
                        "kintype": mo.get("kintype") or "",
                        "kindist": mo.get("kindist") or "",
                        "up": nu, "down": nd, "mar": nm, "col": nc,
                    })
        return {
            "root": root, "count": len(persons), "truncated": truncated,
            "limits": {"up": up, "down": down, "col": col, "mar": mar},
            "persons": persons,
        }

    @classmethod
    def kin_path(cls, a, b, max_depth=6):
        """两人最短亲属路径（KIN_DATA 无向 BFS）：
        CBDB 亲属边双向记录（父录子、子录父），沿 out_edges 正向 BFS 即无向遍历；
        回溯得符号串，翻译链式称谓 + 查五服。max_depth 限深防跑飞。"""
        idx = cls._load_kin_index()
        if not idx:
            return {"error": "亲属索引加载失败"}
        out_edges, kinship, mourning = idx
        a, b = int(a), int(b)
        if a not in out_edges:
            return {"a": a, "b": b, "found": False,
                    "reason": "起点在 KIN_DATA 无亲属记录"}
        from collections import deque
        visited = {a}
        prev = {a: None}  # node -> (parent, rel_symbol)
        queue = deque([a])
        meet = None
        while queue:
            cur = queue.popleft()
            if cur == b:
                meet = cur
                break
            depth = 0
            n = cur
            while prev[n] is not None:
                depth += 1
                n = prev[n][0]
            if depth >= max_depth:
                continue
            for k2, code in out_edges.get(cur, []):
                if k2 in visited:
                    continue
                ks = kinship.get(code)
                if not ks:
                    continue
                if ks["up"] >= 99 or ks["down"] >= 99:
                    continue
                if ks["up"] == 0 and ks["down"] == 0 and ks["mar"] == 0 and ks["col"] == 0:
                    continue
                visited.add(k2)
                prev[k2] = (cur, ks["rel"])
                if k2 == b:
                    meet = k2
                    queue.clear()
                    break
                queue.append(k2)
        if not meet:
            return {"a": a, "b": b, "found": False, "depth_limit": max_depth,
                    "reason": f"{max_depth} 步内无亲属路径（CBDB 亲属记录不全是已知数据边界）"}
        chain = []
        n = b
        while prev[n] is not None:
            p, rel = prev[n]
            chain.append((n, rel))
            n = p
        chain.reverse()
        path_rel = "".join(rel for _, rel in chain)
        person_ids = [a] + [pid for pid, _ in chain]
        info = {}
        conn = cls.get_conn()
        if conn:
            cursor = conn.cursor()
            CHUNK = 500
            for i in range(0, len(person_ids), CHUNK):
                chunk = person_ids[i:i + CHUNK]
                ph = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT c_personid, c_name, c_name_chn, c_surname_chn, c_mingzi_chn "
                    f"FROM BIOG_MAIN WHERE c_personid IN ({ph})", *chunk)
                for r in cursor.fetchall():
                    info[r.c_personid] = r
            conn.close()
        persons = []
        for pid in person_ids:
            r = info.get(pid)
            surname = safe_decode(r.c_surname_chn) if r else ""
            mingzi = safe_decode(r.c_mingzi_chn) if r else ""
            name_chn = (safe_decode(r.c_name_chn) if r else "") or (surname + mingzi)
            persons.append({
                "id": pid,
                "name_chn": name_chn or f"#{pid}",
                "name": (r.c_name if r else "") or "",
            })
        mo = _mourning_lookup(path_rel, mourning)
        return {
            "a": a, "b": b, "found": True, "depth": len(chain),
            "persons": persons,
            "rel_chain": _describe_kin_path(path_rel),
            "rel_symbols": path_rel,
            "mourning": mo,
        }

    @classmethod
    def query_persons(cls, filters, limit=300):
        """综合查询（原生 CBDB 查询维度全搬运）：姓名(含别名)/朝代/性别/指数年区间/
        生卒年区间/地址(指数或指定类型：籍贯·祖籍·居址·葬地等)/入仕方式+入仕年/
        职官+任职年/社会区分/著作/社会关系类型 任意 AND 组合。
        POST 时 JSON 可附 person_ids（范围传递），上限 5000 截断"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()

        where = []
        params = []

        name = (filters.get("name") or "").strip()
        if name:
            variants = name_variants(name)
            name_conds = []
            for col in ("b.c_name", "b.c_name_chn", "b.c_surname_chn", "b.c_mingzi_chn"):
                for v in variants:
                    name_conds.append(f"{col} LIKE ?")
                    params.append(f"%{v}%")
            # 别名（字/号/谥/小名等）并入姓名检索，同人名模块
            for v in variants:
                name_conds.append(
                    "EXISTS (SELECT 1 FROM ALTNAME_DATA an "
                    "WHERE an.c_personid = b.c_personid AND an.c_alt_name_chn LIKE ?)"
                )
                params.append(f"%{v}%")
            where.append("(" + " OR ".join(name_conds) + ")")

        if filters.get("dy"):
            where.append("b.c_dy = ?")
            params.append(int(filters["dy"]))

        if filters.get("gender") in ("0", "1"):
            where.append("b.c_female = ?")
            params.append(filters["gender"] == "1")

        if filters.get("from_year"):
            where.append("b.c_index_year >= ?")
            params.append(int(filters["from_year"]))
        if filters.get("to_year"):
            where.append("b.c_index_year <= ?")
            params.append(int(filters["to_year"]))

        if filters.get("birth_from"):
            where.append("b.c_birthyear > 0 AND b.c_birthyear >= ?")
            params.append(int(filters["birth_from"]))
        if filters.get("birth_to"):
            where.append("b.c_birthyear > 0 AND b.c_birthyear <= ?")
            params.append(int(filters["birth_to"]))
        if filters.get("death_from"):
            where.append("b.c_deathyear > 0 AND b.c_deathyear >= ?")
            params.append(int(filters["death_from"]))
        if filters.get("death_to"):
            where.append("b.c_deathyear > 0 AND b.c_deathyear <= ?")
            params.append(int(filters["death_to"]))

        if filters.get("place_id"):
            addr_type = int(filters.get("addr_type") or 1)
            if addr_type == 1:
                # 籍贯：指数地址 OR BIOG_ADDR_DATA 类型1，同人名模块
                where.append("("
                             "b.c_index_addr_id = ? OR EXISTS ("
                             "SELECT 1 FROM BIOG_ADDR_DATA ba "
                             "WHERE ba.c_personid = b.c_personid "
                             "AND ba.c_addr_type = 1 AND ba.c_addr_id = ?))")
                params += [int(filters["place_id"]), int(filters["place_id"])]
            else:
                where.append("EXISTS (SELECT 1 FROM BIOG_ADDR_DATA ba "
                             "WHERE ba.c_personid = b.c_personid "
                             "AND ba.c_addr_type = ? AND ba.c_addr_id = ?)")
                params += [addr_type, int(filters["place_id"])]

        entry_code = filters.get("entry_code")
        if entry_code or filters.get("entry_from") or filters.get("entry_to"):
            sub = "SELECT 1 FROM ENTRY_DATA e WHERE e.c_personid = b.c_personid"
            sp = []
            if entry_code:
                sub += " AND e.c_entry_code = ?"
                sp.append(int(entry_code))
            if filters.get("entry_from"):
                sub += " AND e.c_year >= ?"
                sp.append(int(filters["entry_from"]))
            if filters.get("entry_to"):
                sub += " AND e.c_year <= ?"
                sp.append(int(filters["entry_to"]))
            where.append("EXISTS (" + sub + ")")
            params += sp

        if filters.get("office_id"):
            sub = ("SELECT 1 FROM POSTED_TO_OFFICE_DATA p "
                   "WHERE p.c_personid = b.c_personid AND p.c_office_id = ?")
            sp = [int(filters["office_id"])]
            if filters.get("office_from"):
                sub += " AND (p.c_lastyear = 0 OR p.c_lastyear >= ?)"
                sp.append(int(filters["office_from"]))
            if filters.get("office_to"):
                sub += " AND (p.c_firstyear = 0 OR p.c_firstyear <= ?)"
                sp.append(int(filters["office_to"]))
            where.append("EXISTS (" + sub + ")")
            params += sp

        if filters.get("status_id"):
            where.append("EXISTS (SELECT 1 FROM STATUS_DATA s "
                         "WHERE s.c_personid = b.c_personid AND s.c_status_code = ?)")
            params.append(int(filters["status_id"]))

        if filters.get("text_id"):
            where.append("EXISTS (SELECT 1 FROM BIOG_TEXT_DATA t "
                         "WHERE t.c_personid = b.c_personid AND t.c_textid = ?)")
            params.append(int(filters["text_id"]))

        assoc_code = filters.get("assoc_code")
        if assoc_code:
            # 与独立社会关系模块默认勾选"并入配对"一致
            codes = [int(assoc_code)]
            t = cls.assoc_type_by_code(assoc_code)
            if t and t.get("pair") and t["pair"] != int(assoc_code):
                codes.append(t["pair"])
            marks = ",".join("?" * len(codes))
            where.append("EXISTS (SELECT 1 FROM ASSOC_DATA a "
                         "WHERE a.c_personid = b.c_personid "
                         f"AND a.c_assoc_code IN ({marks}))")
            params += codes

        pids = filters.get("person_ids")
        if pids is not None:
            where.append(_in_clause("b.c_personid", pids, params))

        if not where:
            return []

        sql = f"""
            SELECT TOP {limit} b.c_personid, b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, b.c_index_year, b.c_female,
                   b.c_dy, d.c_dynasty_chn, ad.c_name_chn AS native_place
            FROM ((BIOG_MAIN b
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy)
            LEFT JOIN ADDR_CODES ad ON b.c_index_addr_id = ad.c_addr_id)
            WHERE {" AND ".join(where)}
            ORDER BY b.c_index_year, b.c_personid
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            surname = safe_decode(row.c_surname_chn)
            mingzi = safe_decode(row.c_mingzi_chn)
            name_chn = safe_decode(row.c_name_chn) or (surname + mingzi)
            results.append({
                "id": row.c_personid,
                "name": row.c_name or "",
                "name_chn": name_chn,
                "birthyear": row.c_birthyear,
                "deathyear": row.c_deathyear,
                "dynasty_code": row.c_dy,
                "dynasty": safe_decode(row.c_dynasty_chn) or "未知",
                "native_place": safe_decode(getattr(row, "native_place", None)) or "",
                "index_year": row.c_index_year or None,
                "female": bool(row.c_female),
            })
        return results

    @classmethod
    def get_person_detail(cls, person_id):
        """获取人物详情：基本信息 + 字号别称 + 地址履历 + 官职履历"""
        conn = cls.get_conn()
        if not conn:
            return None
        cursor = conn.cursor()

        cursor.execute("""
            SELECT b.*, d.c_dynasty_chn
            FROM BIOG_MAIN b
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
            WHERE b.c_personid = ?
        """, person_id)
        row = cursor.fetchone()
        if not row:
            return None

        # 字号别称（字/號/諡等）
        alt_names = []
        try:
            cursor.execute("""
                SELECT a.c_alt_name_chn, t.c_name_type_desc_chn
                FROM ALTNAME_DATA a
                LEFT JOIN ALTNAME_CODES t ON a.c_alt_name_type_code = t.c_name_type_code
                WHERE a.c_personid = ?
                ORDER BY a.c_sequence
            """, person_id)
            for r in cursor.fetchall():
                nm = safe_decode(r.c_alt_name_chn)
                if nm:
                    alt_names.append({"name": nm, "type": safe_decode(r.c_name_type_desc_chn) or ""})
        except Exception:
            pass

        # 地址履历（籍贯/居址等，带类型标签）
        addresses = []
        try:
            cursor.execute("""
                SELECT TOP 12 ba.c_addr_type, ba.c_firstyear, ba.c_lastyear,
                       t.c_addr_desc_chn, ac.c_name_chn, ac.x_coord, ac.y_coord
                FROM ((BIOG_ADDR_DATA ba
                LEFT JOIN BIOG_ADDR_CODES t ON ba.c_addr_type = t.c_addr_type)
                LEFT JOIN ADDR_CODES ac ON ba.c_addr_id = ac.c_addr_id)
                WHERE ba.c_personid = ?
                ORDER BY ba.c_addr_type, ba.c_firstyear
            """, person_id)
            for r in cursor.fetchall():
                place = safe_decode(r.c_name_chn)
                if not place:
                    continue
                addresses.append({
                    "place": place,
                    "type": safe_decode(r.c_addr_desc_chn) or "",
                    "firstyear": r.c_firstyear or None,
                    "lastyear": r.c_lastyear or None,
                    "x_coord": r.x_coord,
                    "y_coord": r.y_coord,
                })
        except Exception:
            pass

        # 官职履历（前 15 条，按起始年排序）
        postings = []
        try:
            cursor.execute("""
                SELECT TOP 15 p.c_firstyear, p.c_lastyear, o.c_office_chn, o.c_office_trans
                FROM POSTED_TO_OFFICE_DATA p
                LEFT JOIN OFFICE_CODES o ON p.c_office_id = o.c_office_id
                WHERE p.c_personid = ? AND p.c_office_id > 0
                ORDER BY p.c_firstyear
            """, person_id)
            for r in cursor.fetchall():
                office = safe_decode(r.c_office_chn)
                if not office:
                    continue
                fy = r.c_firstyear or 0
                ly = r.c_lastyear or 0
                postings.append({
                    "office": office,
                    "trans": r.c_office_trans or "",
                    "firstyear": fy if fy > 0 else None,
                    "lastyear": ly if ly > 0 else None,
                })
        except Exception:
            pass

        # 社会区分（封号/功名/身份标识，STATUS_DATA）
        statuses = []
        try:
            cursor.execute("""
                SELECT s.c_status_code, s.c_firstyear, s.c_lastyear,
                       sc.c_status_desc_chn
                FROM STATUS_DATA s
                LEFT JOIN STATUS_CODES sc ON s.c_status_code = sc.c_status_code
                WHERE s.c_personid = ?
                ORDER BY s.c_firstyear, s.c_sequence
            """, person_id)
            for r in cursor.fetchall():
                desc = safe_decode(r.c_status_desc_chn)
                if not desc:
                    continue
                fy = r.c_firstyear or 0
                ly = r.c_lastyear or 0
                statuses.append({
                    "status": desc,
                    "firstyear": fy if fy > 0 else None,
                    "lastyear": ly if ly > 0 else None,
                })
        except Exception:
            pass

        # 著作（BIOG_TEXT_DATA + TEXT_CODES，附作者角色）
        texts = []
        try:
            cursor.execute("""
                SELECT TOP 30 t.c_title_chn, t.c_title, t.c_extant, t.c_text_dy,
                       bt.c_role_id, tr.c_role_desc_chn
                FROM (BIOG_TEXT_DATA bt
                LEFT JOIN TEXT_CODES t ON bt.c_textid = t.c_textid)
                LEFT JOIN TEXT_ROLE_CODES tr ON bt.c_role_id = tr.c_role_id
                WHERE bt.c_personid = ? AND bt.c_textid > 0
                ORDER BY t.c_text_year
            """, person_id)
            for r in cursor.fetchall():
                title = safe_decode(r.c_title_chn) or safe_decode(r.c_title)
                if not title:
                    continue
                texts.append({
                    "title": title,
                    "extant": bool(r.c_extant),
                    "dynasty": r.c_text_dy or None,
                    "role": safe_decode(r.c_role_desc_chn) or "",
                })
        except Exception:
            pass

        return {
            "id": row.c_personid,
            "name": row.c_name or "",
            "name_chn": safe_decode(row.c_name_chn) or (safe_decode(row.c_surname_chn) + safe_decode(row.c_mingzi_chn)),
            "surname_chn": safe_decode(row.c_surname_chn),
            "mingzi_chn": safe_decode(row.c_mingzi_chn),
            "birthyear": row.c_birthyear,
            "deathyear": row.c_deathyear,
            "dynasty_code": row.c_dy,
            "dynasty": safe_decode(row.c_dynasty_chn) or "未知",
            "notes": safe_decode(row.c_notes) or "",
            "alt_names": alt_names,
            "addresses": addresses,
            "postings": postings,
            "statuses": statuses,
            "texts": texts,
        }

    @classmethod
    def get_person_network(cls, person_id, include_kin=False, dynasty_code=None, limit=150):
        """人物关系网络：社会关系（ASSOC_DATA）+ 可选混入亲属（KIN_DATA，三期）。
        dynasty_code 仅过滤外围节点（中心人物始终保留）。
        返回 {nodes, edges}；edge 带 kind: assoc|kin，前端按类型着色。"""
        conn = cls.get_conn()
        if not conn:
            return {"nodes": [], "edges": []}
        cursor = conn.cursor()

        center = cls.get_person_detail(person_id)
        if not center:
            return {"nodes": [], "edges": []}
        root = int(person_id)

        def _name_of(r):
            return (safe_decode(r.c_name_chn)
                    or (safe_decode(r.c_surname_chn) + safe_decode(r.c_mingzi_chn))
                    or r.c_name or f"人物{r.c_personid}")

        nodes = {}
        edges = []

        def _add_node(pid, name, dynasty, is_center=False):
            if pid not in nodes:
                nodes[pid] = {"id": pid, "name": name, "dynasty": dynasty or "", "center": is_center}

        _add_node(root, center.get("name_chn") or center["name"], center.get("dynasty"), True)

        # ── 社会关系 ──
        cursor.execute("""
            SELECT a.c_assoc_id, a.c_assoc_year, ac.c_assoc_desc_chn,
                   b.c_name_chn, b.c_name, b.c_surname_chn, b.c_mingzi_chn, b.c_dy, d.c_dynasty_chn
            FROM ((ASSOC_DATA a
            LEFT JOIN ASSOC_CODES ac ON a.c_assoc_code = ac.c_assoc_code)
            LEFT JOIN BIOG_MAIN b ON a.c_assoc_id = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
            WHERE a.c_personid = ? AND a.c_assoc_id > 0
            ORDER BY a.c_assoc_year
        """, root)
        n_added = 0
        for r in cursor.fetchall():
            aid = int(r.c_assoc_id)
            if aid == root:
                continue
            if dynasty_code and (r.c_dy or 0) != int(dynasty_code):
                continue
            _add_node(aid, _name_of(r), safe_decode(r.c_dynasty_chn))
            edges.append({"source": root, "target": aid,
                          "relation": safe_decode(r.c_assoc_desc_chn) or "关联",
                          "kind": "assoc", "year": r.c_assoc_year or None})
            n_added += 1
            if n_added >= limit:
                break

        # ── 亲属混入（可开关）──
        if include_kin:
            cursor.execute("""
                SELECT k.c_kin_id, kc.c_kinrel_chn,
                       b.c_name_chn, b.c_name, b.c_surname_chn, b.c_mingzi_chn, b.c_dy, d.c_dynasty_chn
                FROM ((KIN_DATA k
                LEFT JOIN KINSHIP_CODES kc ON k.c_kin_code = kc.c_kincode)
                LEFT JOIN BIOG_MAIN b ON k.c_kin_id = b.c_personid)
                LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
                WHERE k.c_personid = ? AND k.c_kin_id > 0
                ORDER BY k.c_kin_code
            """, root)
            k_added = 0
            for r in cursor.fetchall():
                kid = int(r.c_kin_id)
                if kid == root:
                    continue
                if dynasty_code and (r.c_dy or 0) != int(dynasty_code):
                    continue
                _add_node(kid, _name_of(r), safe_decode(r.c_dynasty_chn))
                edges.append({"source": root, "target": kid,
                              "relation": safe_decode(r.c_kinrel_chn) or "亲属",
                              "kind": "kin", "year": None})
                k_added += 1
                if k_added >= limit:
                    break

        return {"nodes": list(nodes.values()), "edges": edges}

    @classmethod
    def _postings_for_persons(cls, person_ids):
        """批量拉取任职记录（POSTED_TO_OFFICE_DATA + 官名 + 任职地坐标 + 人物基本信息）。
        JOIN BIOG_MAIN/DYNASTIES：纯 posted 模式的 feature 也要带姓名/朝代/生卒，
        否则群体切"任职地"来源后弹窗第一行是空白名字。
        返回 [{person_id, office_id, office, addr_id, place, x, y, firstyear, lastyear,
                name, dynasty, birth, death}]"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        params = []
        in_sql = _in_clause("po.c_personid", person_ids, params)
        sql = f"""
            SELECT po.c_personid, po.c_office_id, o.c_office_chn,
                   po.c_firstyear, po.c_lastyear,
                   pa.c_addr_id, ac.c_name_chn AS addr_name, ac.x_coord, ac.y_coord,
                   b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
            FROM ((((POSTED_TO_OFFICE_DATA po
            LEFT JOIN OFFICE_CODES o ON po.c_office_id = o.c_office_id)
            LEFT JOIN POSTED_TO_ADDR_DATA pa ON po.c_posting_id = pa.c_posting_id)
            LEFT JOIN ADDR_CODES ac ON pa.c_addr_id = ac.c_addr_id)
            LEFT JOIN BIOG_MAIN b ON po.c_personid = b.c_personid)
            LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
            WHERE {in_sql} AND po.c_office_id > 0
            ORDER BY po.c_personid, po.c_firstyear
        """
        cursor.execute(sql, params)
        out = []
        for r in cursor.fetchall():
            name_chn = safe_decode(r.c_name_chn) or (
                safe_decode(r.c_surname_chn) + safe_decode(r.c_mingzi_chn))
            out.append({
                "person_id": r.c_personid,
                "office_id": r.c_office_id,
                "office": safe_decode(r.c_office_chn) or "",
                "addr_id": r.c_addr_id or 0,
                "place": safe_decode(getattr(r, "addr_name", None)) or "",
                "x": float(r.x_coord) if r.x_coord is not None else None,
                "y": float(r.y_coord) if r.y_coord is not None else None,
                "firstyear": r.c_firstyear or 0,
                "lastyear": r.c_lastyear or 0,
                "name": name_chn or r.c_name or "",
                "dynasty": safe_decode(r.c_dynasty_chn) or "",
                "birth": r.c_birthyear or None,
                "death": r.c_deathyear or None,
            })
        return out

    # 不做"此时官职"匹配的地址类型：籍贯/出生地/葬地/死所/另一籍贯。
    # 这些地点的语义不是"仕宦经历"，匹配任职会答非所问（眉山籍贯→鳳翔任职）。
    _OFFICE_SKIP_TYPES = {1, 8, 9, 10, 14}

    @classmethod
    def _match_postings(cls, feats, postings):
        """为 bio 模式 feature 按年份交叠匹配任职记录 → properties.offices。
        交叠规则：地址区间 [af, al]（缺省用生卒年兜底）、任职区间 [of, ol]（缺 ol 视作单年 of）。
        双方都无年份则无法匹配。匹配按地名相同优先 + 年份交叠。"""
        by_person = {}
        for p in postings:
            by_person.setdefault(p["person_id"], []).append(p)
        for f in feats:
            props = f.get("properties", {})
            pid = props.get("person_id")
            if props.get("addr_type_code") in cls._OFFICE_SKIP_TYPES:
                props["offices"] = []
                continue
            af = props.get("firstyear") or 0
            al = props.get("lastyear") or 0
            if not af and not al:
                # 地址无年份：用生卒年兜底（宽限各 2 年）
                birth = props.get("birth") or 0
                death = props.get("death") or 0
                if birth > 0 and death > 0:
                    af, al = birth - 2, death + 2
                else:
                    props["offices"] = []
                    continue
            if not al:
                al = af
            if not af:
                af = al
            matched = []
            place = props.get("place") or ""
            for p in by_person.get(pid, []):
                of, ol = p["firstyear"], p["lastyear"]
                if not of and not ol:
                    continue
                if not ol:
                    ol = of
                if not of:
                    of = ol
                if max(af, of) <= min(al, ol):
                    matched.append(p)
            # 同地名任职排前
            matched.sort(key=lambda p: (0 if p["place"] == place else 1, -(p["lastyear"] or p["firstyear"])))
            props["offices"] = [
                {"office": p["office"], "firstyear": p["firstyear"] or None,
                 "lastyear": p["lastyear"] or None, "place": p["place"]}
                for p in matched[:4]
            ]

    @classmethod
    def persons_geojson(cls, person_ids, limit=2000, addr_types=None, addr_source="bio", with_offices=False):
        """人物地址 GeoJSON（三期 GIS 导出 + 十期任职地/官职联动）。
        addr_source: 'bio'(生活地址,默认) / 'posted'(任职地) / 'all'(两者合并)。
        with_offices: bio/all 模式下为每条地址按年份交叠匹配任职记录 → properties.offices。
        坐标系 WGS84。addr_types 仅作用于 bio 模式。"""
        conn = cls.get_conn()
        if not conn:
            return {"type": "FeatureCollection", "features": []}
        cursor = conn.cursor()
        feats = []
        if addr_source in ("bio", "all"):
            params = []
            in_sql = _in_clause("ba.c_personid", person_ids, params)
            type_sql = ""
            if addr_types:
                type_sql = " AND " + _in_clause("ba.c_addr_type", addr_types, params)
            sql = f"""
                SELECT ba.c_personid, ba.c_addr_type, ba.c_firstyear, ba.c_lastyear,
                       t.c_addr_desc_chn, ac.c_name_chn AS addr_name, ac.x_coord, ac.y_coord,
                       b.c_name, b.c_name_chn, b.c_surname_chn, b.c_mingzi_chn,
                       b.c_birthyear, b.c_deathyear, d.c_dynasty_chn
                FROM (((BIOG_ADDR_DATA ba
                LEFT JOIN BIOG_ADDR_CODES t ON ba.c_addr_type = t.c_addr_type)
                LEFT JOIN ADDR_CODES ac ON ba.c_addr_id = ac.c_addr_id)
                LEFT JOIN BIOG_MAIN b ON ba.c_personid = b.c_personid)
                LEFT JOIN DYNASTIES d ON b.c_dy = d.c_dy
                WHERE {in_sql} AND ac.x_coord IS NOT NULL AND ac.y_coord IS NOT NULL{type_sql}
                ORDER BY ba.c_personid, ba.c_addr_type
            """
            cursor.execute(sql, params)
            for r in cursor.fetchall():
                if r.x_coord is None or r.y_coord is None:
                    continue
                name_chn = safe_decode(r.c_name_chn) or (
                    safe_decode(r.c_surname_chn) + safe_decode(r.c_mingzi_chn))
                feats.append({
                    "type": "Feature",
                    "geometry": {"type": "Point",
                                 "coordinates": [float(r.x_coord), float(r.y_coord)]},
                    "properties": {
                        "person_id": r.c_personid,
                        "name": name_chn or r.c_name or "",
                        "pinyin": r.c_name or "",
                        "dynasty": safe_decode(r.c_dynasty_chn) or "",
                        "birth": r.c_birthyear or None,
                        "death": r.c_deathyear or None,
                        "addr_type": safe_decode(r.c_addr_desc_chn) or "",
                        "addr_type_code": r.c_addr_type,
                        "place": safe_decode(getattr(r, "addr_name", None)) or "",
                        "firstyear": r.c_firstyear or None,
                        "lastyear": r.c_lastyear or None,
                        "source": "bio",
                    },
                })
                if len(feats) >= limit:
                    break
        if addr_source in ("posted", "all"):
            posted = cls._postings_for_persons(person_ids)
            n0 = len(feats)
            for p in posted:
                if p["x"] is None or p["y"] is None:
                    continue
                feats.append({
                    "type": "Feature",
                    "geometry": {"type": "Point",
                                 "coordinates": [p["x"], p["y"]]},
                    "properties": {
                        "person_id": p["person_id"],
                        "name": p["name"],
                        "pinyin": "",
                        "dynasty": p["dynasty"],
                        "birth": p["birth"],
                        "death": p["death"],
                        "addr_type": "任职地",
                        "addr_type_code": 100,
                        "place": p["place"],
                        "firstyear": p["firstyear"] or None,
                        "lastyear": p["lastyear"] or None,
                        "source": "posted",
                        "office": p["office"],
                        "office_id": p["office_id"],
                    },
                })
                if len(feats) - n0 >= limit:
                    break
        # bio/all 模式下补充姓名朝代等信息缺失的 posted 要素
        if addr_source == "all":
            info = {}
            for f in feats:
                pr = f["properties"]
                if pr.get("source") == "bio" and pr["person_id"] not in info:
                    info[pr["person_id"]] = {
                        "name": pr["name"], "dynasty": pr["dynasty"],
                        "birth": pr["birth"], "death": pr["death"]}
            for f in feats:
                pr = f["properties"]
                if pr.get("source") == "posted":
                    inf = info.get(pr["person_id"])
                    if inf:
                        for k, v in inf.items():
                            if not pr.get(k):
                                pr[k] = v
        if with_offices and addr_source in ("bio", "all"):
            postings = cls._postings_for_persons(person_ids)
            cls._match_postings(feats, postings)
        # meta：数据覆盖统计（含无坐标记录），让前端诚实呈现数据边界
        meta = {"returned": len(feats), "limit": limit}
        if addr_source in ("bio", "all"):
            n_bio_coord = sum(1 for f in feats if f["properties"].get("source") == "bio")
            try:
                cur2 = conn.cursor()
                p2 = []
                in2 = _in_clause("ba.c_personid", person_ids, p2)
                cur2.execute(f"SELECT COUNT(*) FROM BIOG_ADDR_DATA ba WHERE {in2}", p2)
                addr_total = cur2.fetchone()[0]
                meta["addr_total"] = addr_total
                meta["addr_nocoord"] = max(0, addr_total - n_bio_coord)
            except Exception:
                pass
        if addr_source in ("posted", "all"):
            n_posted_coord = sum(1 for f in feats if f["properties"].get("source") == "posted")
            meta["posting_total"] = len(posted)
            meta["posting_nocoord"] = max(0, len(posted) - n_posted_coord)
        return {"type": "FeatureCollection", "features": feats, "meta": meta}

    @classmethod
    def get_dynasty_list(cls):
        """获取朝代列表"""
        conn = cls.get_conn()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("SELECT c_dy, c_dynasty_chn FROM DYNASTIES WHERE c_dy > 0 ORDER BY c_dy")
        rows = cursor.fetchall()
        return [{"code": r.c_dy, "name": safe_decode(r.c_dynasty_chn)} for r in rows]

def safe_decode(val):
    """安全解码中文字符"""
    if val is None:
        return ""
    if isinstance(val, str):
        # 已经是字符串，可能已经是正确的或乱码
        # 如果包含明显的乱码特征，尝试转换
        return val
    return str(val)

def obsidian_api(method, path, payload=None):
    """调用 Obsidian Local REST API"""
    url = f"http://127.0.0.1:{OBSIDIAN_API_PORT}{path}"
    headers = {"Authorization": f"Bearer {OBSIDIAN_API_KEY}"} if OBSIDIAN_API_KEY else {}
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            r = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                            json=payload, timeout=5)
        elif method == "PUT":
            r = requests.put(url, headers={**headers, "Content-Type": "application/json"},
                           json=payload, timeout=5)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=5)
        else:
            return {"error": f"Unsupported method {method}"}
        return r.json() if r.text else {"success": True}
    except requests.exceptions.ConnectionError:
        return {"error": "无法连接 Obsidian Local REST API。请确认插件已启用。"}
    except Exception as e:
        return {"error": str(e)}

def deepseek_chat(messages, stream=False):
    """调用 DeepSeek（优先直连 API，fallback OpenClaw gateway）"""
    # 有 API key 时优先直连，更快更稳
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        try:
            r = requests.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": DEEPSEEK_MODEL, "messages": messages, "stream": stream},
                timeout=60)
            if r.status_code == 200:
                return r.json()
        except:
            pass

    # fallback：OpenClaw 本地 gateway
    try:
        r = requests.post("http://127.0.0.1:8642/v1/chat/completions",
            json={"model": DEEPSEEK_MODEL, "messages": messages, "stream": stream},
            timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass

    if not api_key:
        return {"error": "未配置 DeepSeek API Key"}
    return {"error": "DeepSeek 服务暂不可用（直连与 gateway 均失败）"}

# ── Routes: 页面 ────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory(app.static_folder, path)

# ── API: Obsidian ───────────────────────────────────────

@app.route("/api/obsidian/notes", methods=["GET"])
def obsidian_list_notes():
    """列出 Obsidian 笔记（搜索功能），始终返回数组"""
    query = request.args.get("q", "")
    folder = request.args.get("folder", "")

    if query:
        result = obsidian_api("GET", f"/search/simple/?query={quote(query)}")
    else:
        result = obsidian_api("GET", f"/vault/{quote(folder)}/" if folder else "/vault/")

    # 统一返回数组格式
    if isinstance(result, dict):
        if "files" in result:
            files = result["files"]
            # 过滤掉 README.md 和隐藏文件
            files = [f for f in files if not f.startswith('.') and f != 'README.md']
            return jsonify(files)
        if "matches" in result:
            return jsonify(result["matches"])
    return jsonify([])

@app.route("/api/obsidian/note/<path:filepath>", methods=["GET"])
def obsidian_get_note(filepath):
    """读取 Obsidian 笔记内容"""
    result = obsidian_api("GET", f"/vault/{filepath}")
    return jsonify(result)

@app.route("/api/obsidian/note/<path:filepath>", methods=["PUT"])
def obsidian_update_note(filepath):
    """更新/创建 Obsidian 笔记"""
    data = request.json or {}
    content = data.get("content", "")
    result = obsidian_api("PUT", f"/vault/{filepath}", {"content": content})
    return jsonify(result)

@app.route("/api/obsidian/note/<path:filepath>", methods=["DELETE"])
def obsidian_delete_note(filepath):
    """删除 Obsidian 笔记"""
    result = obsidian_api("DELETE", f"/vault/{filepath}")
    return jsonify(result)

@app.route("/api/obsidian/daily", methods=["POST"])
def obsidian_create_daily():
    """创建/追加今日札记(文件直写, 不依赖 Local REST API 插件)"""
    import datetime as _dt
    import urllib.parse as _up
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    content = ((request.get_json(force=True, silent=True) or {}).get("content") or "").strip()
    vault = _vault_path()
    if not vault:
        return jsonify({"ok": False, "error": "vault not found"})
    folder = os.path.join(vault, "日记")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return jsonify({"ok": False, "error": "mkdir: %s" % e})
    fp = os.path.join(folder, today + ".md")
    try:
        if os.path.isfile(fp):
            old = open(fp, encoding="utf-8", errors="ignore").read()
            body = old.rstrip() + ("\n\n" + content if content else "") + "\n"
        else:
            body = "# %s 札记\n\n%s\n" % (today, content)
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    except Exception as e:
        return jsonify({"ok": False, "error": "write: %s" % e})
    uri = "obsidian://open?vault=%s&file=%s" % (
        _up.quote(os.path.basename(vault)), _up.quote("日记/" + today + ".md"))
    return jsonify({"ok": True, "path": fp, "file": today + ".md", "obsidian": uri})

@app.route("/api/obsidian/stats", methods=["GET"])
def obsidian_stats():
    """获取 Obsidian 统计信息（递归统计 Vault 所有文件）"""
    result = obsidian_api("GET", "/vault/")
    stats = {"total_files": 0, "total_folders": 0, "folders": {}, "root_files": []}

    def count_recursive(path, depth=0):
        """递归统计文件夹内容"""
        if depth > 3:
            return 0, 0
        encoded_path = quote(path, safe='/')
        res = obsidian_api("GET", f"/vault/{encoded_path}")
        if not isinstance(res, dict) or "files" not in res:
            return 0, 0
        files_count = 0
        folders_count = 0
        for f in res["files"]:
            if f.endswith("/"):
                folders_count += 1
                sub_files, sub_folders = count_recursive(f"{path}{f}", depth + 1)
                files_count += sub_files
                folders_count += sub_folders
            else:
                files_count += 1
        return files_count, folders_count

    if isinstance(result, dict) and "files" in result:
        for f in result["files"]:
            if f.endswith("/"):
                folder_name = f.rstrip("/")
                fc, folc = count_recursive(f"{f}")
                stats["folders"][folder_name] = {"files": fc, "subfolders": folc}
                stats["total_files"] += fc
                stats["total_folders"] += folc + 1
            else:
                stats["root_files"].append(f)
                stats["total_files"] += 1

    # 兼容旧格式：仪表盘使用 论文/札记/人物/史料/日记 作为 key
    legacy = {}
    for folder in ["论文", "札记", "人物", "史料", "日记"]:
        legacy[folder] = stats["folders"].get(folder, {}).get("files", 0)
    stats["legacy"] = legacy

    return jsonify(stats)

# ── API: 学术动态 ─────────────────────────────────────

@app.route("/api/news", methods=["GET"])
def get_news():
    """从 Obsidian 读取学术动态"""
    result = obsidian_api("GET", "/vault/学术动态.md")
    if "error" in result:
        return jsonify({"items": [], "error": "未找到 学术动态.md，请在 Vault 根目录创建此文件"})

    content = result.get("content", "")
    items = []

    # 解析 markdown 格式：每行格式为 `- [标题](链接) | 时间 | 标签`
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            item = {"title": line[2:].strip(), "time": "", "badge": ""}
            # 尝试解析链接
            if "](" in line:
                import re
                link_match = re.search(r'\[(.+?)\]\((.+?)\)', line)
                if link_match:
                    item["title"] = link_match.group(1)
                    item["link"] = link_match.group(2)
            # 尝试解析 badge（NEW/HOT）
            if "NEW" in line.upper():
                item["badge"] = "NEW"
            elif "HOT" in line.upper():
                item["badge"] = "HOT"
            if item["title"]:
                items.append(item)

    return jsonify({"items": items[:10]})

@app.route("/api/news", methods=["PUT"])
def update_news():
    """更新学术动态"""
    data = request.json or {}
    content = data.get("content", "")
    result = obsidian_api("PUT", "/vault/学术动态.md", {"content": content})
    return jsonify(result)


# ── API: CBDB ───────────────────────────────────────────

# 人物检索结果缓存（CBDB 静态快照，数据不变）：参数键 -> 结果，LRU 300 条
_SEARCH_CACHE = OrderedDict()
_SEARCH_CACHE_LOCK = threading.Lock()
_SEARCH_CACHE_CAP = 300

@app.route("/api/cbdb/search", methods=["GET"])
def cbdb_search():
    """CBDB 人物搜索（本地数据库）：?name= 必填；可选 &dy=朝代代码 &gender=0男1女 &addr_id=籍贯地址（原生人名查询维度）"""
    name = request.args.get("name", "")
    dynasty = request.args.get("dynasty", "")
    dy = request.args.get("dy", "")

    # 结果缓存：钻取过程中反复查同名人时零等待（CBDB 是静态快照，无需失效）
    cache_key = tuple(sorted((k, v) for k, v in request.args.items()))
    with _SEARCH_CACHE_LOCK:
        if cache_key in _SEARCH_CACHE:
            _SEARCH_CACHE.move_to_end(cache_key)
            return jsonify(_SEARCH_CACHE[cache_key])

    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接。请确认数据库文件路径正确。"})

    if not name:
        return jsonify({"error": "请输入人名"})

    dynasty_code = None
    if dy:
        try:
            dynasty_code = int(dy)
        except ValueError:
            dynasty_code = None
    elif dynasty:
        dynasty_map = {
            "唐": 5, "宋": 15, "北宋": 15, "南宋": 15,
            "元": 25, "明": 35, "清": 45
        }
        dynasty_code = dynasty_map.get(dynasty)

    results = CBDBConnection.search_persons(
        name, dynasty_code,
        gender=request.args.get("gender", "").strip() or None,
        addr_id=request.args.get("addr_id", "").strip() or None,
        by_from=request.args.get("by_from", "").strip() or None,
        by_to=request.args.get("by_to", "").strip() or None,
        dy_from=request.args.get("dy_from", "").strip() or None,
        dy_to=request.args.get("dy_to", "").strip() or None,
        index_from=request.args.get("index_from", "").strip() or None,
        index_to=request.args.get("index_to", "").strip() or None,
    )
    with _SEARCH_CACHE_LOCK:
        _SEARCH_CACHE[cache_key] = results
        if len(_SEARCH_CACHE) > _SEARCH_CACHE_CAP:
            _SEARCH_CACHE.popitem(last=False)
    return jsonify(results)

@app.route("/api/cbdb/offices/search", methods=["GET"])
def cbdb_office_search():
    """官名检索：?q= 官名关键词，?category= 门类筛选"""
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    if not q and not category:
        return jsonify({"error": "请输入官名或选择门类"})
    return jsonify(CBDBConnection.search_offices(q, category=category or None))

@app.route("/api/cbdb/offices/<int:office_id>/persons", methods=["GET"])
def cbdb_office_persons(office_id):
    """某官职的任职者列表；?from_year=&to_year= 任职年区间，?addr_id= 任官地址"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    return jsonify(CBDBConnection.persons_by_office(
        office_id,
        from_year=request.args.get("from_year") or None,
        to_year=request.args.get("to_year") or None,
        addr_id=request.args.get("addr_id") or None,
    ))

@app.route("/api/cbdb/places/search", methods=["GET"])
def cbdb_place_search():
    """地名检索：?q= 地名，?admin_type= 层级，?from_year=&to_year= 存续期"""
    q = request.args.get("q", "").strip()
    admin_type = request.args.get("admin_type", "").strip()
    from_year = request.args.get("from_year") or None
    to_year = request.args.get("to_year") or None
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    if not q and not admin_type:
        return jsonify({"error": "请输入地名或选择层级"})
    return jsonify(CBDBConnection.search_places(
        q, admin_type=admin_type or None, from_year=from_year, to_year=to_year
    ))

@app.route("/api/cbdb/places/nearest", methods=["GET"])
def cbdb_place_nearest():
    """地图反查：?x=经度&y=纬度 → 半径内最近的 CBDB 地名（?max_km= 默认 100）"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    try:
        x = float(request.args.get("x", ""))
        y = float(request.args.get("y", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "x/y 参数无效"}), 400
    if not (73 <= x <= 135 and 18 <= y <= 54):
        return jsonify({"error": "坐标超出中国历史地图范围"}), 400
    try:
        max_km = min(max(float(request.args.get("max_km", 100)), 1.0), 500.0)
    except (ValueError, TypeError):
        max_km = 100.0
    return jsonify(CBDBConnection.nearest_places(x, y, max_km=max_km))

@app.route("/api/cbdb/places/<int:addr_id>/persons", methods=["GET"])
def cbdb_place_persons(addr_id):
    """与某地相关的人物列表；?include_same_coord=1 并入同坐标地址（CBDB 新版原生）"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    include_same = request.args.get("include_same_coord") in ("1", "true")
    return jsonify(CBDBConnection.persons_by_place(addr_id, include_same_coord=include_same))

@app.route("/api/cbdb/entries/search", methods=["GET"])
def cbdb_entry_search():
    """入仕方式检索"""
    q = request.args.get("q", "").strip()
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    if not q:
        return jsonify({"error": "请输入入仕方式"})
    return jsonify(CBDBConnection.search_entry_types(q))

@app.route("/api/cbdb/entries/resolve", methods=["GET"])
def cbdb_entry_resolve():
    """入仕关键词 → 代码（复用三级解析器）：?q=关键词或代码 → {code, name}。AI 意图/快捷入口用。"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "请输入入仕方式"})
    code = int(q) if q.lstrip("-").isdigit() else CBDBConnection.resolve_entry_code(q)
    if code is None:
        return jsonify({"error": f"未找到入仕方式：{q}"})
    return jsonify({"code": code, "name": CBDBConnection.entry_code_name(code)})


@app.route("/api/cbdb/entries/<int:entry_code>/persons", methods=["GET"])
def cbdb_entry_persons(entry_code):
    """某入仕方式的人物列表；?from_year=&to_year= 入仕年区间，?addr_id= 入仕地址"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    return jsonify(CBDBConnection.persons_by_entry(
        entry_code,
        from_year=request.args.get("from_year") or None,
        to_year=request.args.get("to_year") or None,
        addr_id=request.args.get("addr_id") or None,
        use_index=request.args.get("use_index") == "1",
    ))

@app.route("/api/cbdb/person/<int:person_id>/kin", methods=["GET"])
def cbdb_person_kin(person_id):
    """人物亲属列表"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    return jsonify(CBDBConnection.get_person_kin(person_id))

@app.route("/api/cbdb/person/<int:person_id>/kin/recursive", methods=["GET"])
def cbdb_person_kin_recursive(person_id):
    """亲属递归检索（CBDB 原生四参数）：?up=先世步数&down=后世&col=旁系&mar=姻亲（0-10）"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})

    def _i(name, default):
        try:
            return max(0, min(int(request.args.get(name, "")), 10))
        except (ValueError, TypeError):
            return default

    result = CBDBConnection.get_person_kin_recursive(
        person_id,
        up=_i("up", 2), down=_i("down", 2), col=_i("col", 1), mar=_i("mar", 1),
    )
    return jsonify(result)

@app.route("/api/cbdb/person/<int:person_id>/assoc", methods=["GET"])
def cbdb_person_assoc(person_id):
    """人物社会关系列表"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    return jsonify(CBDBConnection.get_person_assoc(person_id))

@app.route("/api/cbdb/query", methods=["GET", "POST"])
def cbdb_query():
    """综合查询：name/dy/gender/from_year/to_year/place_id/entry_code 任意组合。
    POST 时 JSON 体可带 person_ids（跨查询人物列表传递，≤5000），结果取交集。"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    if request.method == "POST":
        data = request.json or {}
        filters = data.get("filters") or {}
        try:
            pids = [int(i) for i in (data.get("person_ids") or [])][:5000]
        except (ValueError, TypeError):
            pids = []
        filters["person_ids"] = pids
    else:
        filters = {
            "name": request.args.get("name", ""),
            "dy": request.args.get("dy", ""),
            "gender": request.args.get("gender", ""),
            "from_year": request.args.get("from_year", ""),
            "to_year": request.args.get("to_year", ""),
            "birth_from": request.args.get("birth_from", ""),
            "birth_to": request.args.get("birth_to", ""),
            "death_from": request.args.get("death_from", ""),
            "death_to": request.args.get("death_to", ""),
            "place_id": request.args.get("place_id", ""),
            "addr_type": request.args.get("addr_type", ""),
            "entry_code": request.args.get("entry_code", ""),
            "entry_from": request.args.get("entry_from", ""),
            "entry_to": request.args.get("entry_to", ""),
            "office_id": request.args.get("office_id", ""),
            "office_from": request.args.get("office_from", ""),
            "office_to": request.args.get("office_to", ""),
            "office_addr_id": request.args.get("office_addr_id", ""),
            "status_id": request.args.get("status_id", ""),
            "text_id": request.args.get("text_id", ""),
            "assoc_code": request.args.get("assoc_code", ""),
        }
    results = CBDBConnection.query_persons(filters)
    return jsonify(results)

@app.route("/api/cbdb/person/<int:person_id>", methods=["GET"])
def cbdb_person_detail(person_id):
    """CBDB 人物详情"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})

    person = CBDBConnection.get_person_detail(person_id)
    if not person:
        return jsonify({"error": "未找到该人物"})
    return jsonify(person)

@app.route("/api/cbdb/network/<int:person_id>", methods=["GET"])
def cbdb_network(person_id):
    """CBDB 人物关系网络：?include_kin=1 混入亲属，?dy= 朝代代码限定外围节点"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})

    include_kin = request.args.get("include_kin") in ("1", "true")
    dy = request.args.get("dy", "").strip() or None
    network = CBDBConnection.get_person_network(person_id, include_kin=include_kin, dynasty_code=dy)
    return jsonify(network)

@app.route("/api/cbdb/dynasties", methods=["GET"])
def cbdb_dynasties():
    """CBDB 朝代列表"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})

    dynasties = CBDBConnection.get_dynasty_list()
    return jsonify(dynasties)

@app.route("/api/cbdb/status/search", methods=["GET"])
def cbdb_status_search():
    """社会区分类型检索：封号/功名/身份标识"""
    q = request.args.get("q", "").strip()
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    if not q:
        return jsonify({"error": "请输入身份类型关键词"})
    return jsonify(CBDBConnection.search_status_types(q))

@app.route("/api/cbdb/status/<int:status_code>/persons", methods=["GET"])
def cbdb_status_persons(status_code):
    """某社会区分的人物列表；?from_year=&to_year= 身份起止年区间"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    return jsonify(CBDBConnection.persons_by_status(
        status_code,
        from_year=request.args.get("from_year") or None,
        to_year=request.args.get("to_year") or None,
    ))

@app.route("/api/cbdb/texts/search", methods=["GET"])
def cbdb_text_search():
    """著作检索：书名（简繁自动）"""
    q = request.args.get("q", "").strip()
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    if not q:
        return jsonify({"error": "请输入书名"})
    return jsonify(CBDBConnection.search_texts(q))

@app.route("/api/cbdb/texts/<int:text_id>/persons", methods=["GET"])
def cbdb_text_persons(text_id):
    """某著作的相关人物（作者/编者/注者等）"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    return jsonify(CBDBConnection.persons_by_text(text_id))

@app.route("/api/cbdb/assoc/types", methods=["GET"])
def cbdb_assoc_types():
    """社会关系类型字典：?q=关键词（简繁自动）&category=大类"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    q = request.args.get("q", "").strip() or None
    category = request.args.get("category", "").strip() or None
    return jsonify(CBDBConnection.search_assoc_types(q, category))

@app.route("/api/cbdb/assoc/persons", methods=["GET"])
def cbdb_assoc_persons():
    """社会关系检索（原生十大模块之五）：?code=关系码
    可选 &pair=1 并入配对关系（如師長↔門生双向）&from_year=&to_year=&dy=朝代&limit="""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    code = request.args.get("code", "").strip()
    if not code or not code.lstrip("-").isdigit():
        return jsonify({"error": "请先选择社会关系类型"})
    try:
        limit = min(int(request.args.get("limit", 500)), 1000)
    except ValueError:
        limit = 500
    return jsonify(CBDBConnection.persons_by_assoc(
        int(code),
        pair=request.args.get("pair") == "1",
        from_year=request.args.get("from_year") or None,
        to_year=request.args.get("to_year") or None,
        dynasty_code=request.args.get("dy") or None,
        limit=limit,
    ))


@app.route("/api/cbdb/assoc/between", methods=["GET"])
def cbdb_assoc_between():
    """两人社会关系（原生 Query Pair-wise Associations）：?a=人物ID&b=人物ID
    返回双向社会关系记录 + 直系亲属直查（含五服）。"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    a = request.args.get("a", "").strip()
    b = request.args.get("b", "").strip()
    if not a.isdigit() or not b.isdigit():
        return jsonify({"error": "请提供双方人物 ID"})
    if a == b:
        return jsonify({"error": "双方不能是同一个人"})
    return jsonify(CBDBConnection.assoc_between(int(a), int(b)))


@app.route("/api/cbdb/kin/path", methods=["GET"])
def cbdb_kin_path():
    """两人最短亲属路径：?a=人物ID&b=人物ID&max_depth=6（上限 10）
    KIN_DATA 无向 BFS + 链式称谓翻译 + 五服；查无记录属数据边界，忠实呈现"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 数据库未就绪"})
    a = request.args.get("a", "").strip()
    b = request.args.get("b", "").strip()
    if not a.isdigit() or not b.isdigit():
        return jsonify({"error": "请提供双方数字 ID"})
    if a == b:
        return jsonify({"error": "双方不能是同一人"})
    try:
        md = int(request.args.get("max_depth", 6))
    except ValueError:
        md = 6
    md = max(1, min(md, 10))
    return jsonify(CBDBConnection.kin_path(int(a), int(b), md))


@app.route("/api/cbdb/places/<int:addr_id>/assoc", methods=["GET"])
def cbdb_place_assoc(addr_id):
    """地区关系检索（原生 Query Place Associations）：某地相关人物之间的社会关系。
    可选 &code=关系码&pair=1&from_year=&to_year=&same=1 同坐标并入&both=1 仅双方均在该地&limit="""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    try:
        limit = min(int(request.args.get("limit", 500)), 1000)
    except ValueError:
        limit = 500
    code = request.args.get("code", "").strip()
    return jsonify(CBDBConnection.persons_by_place_assoc(
        addr_id,
        code=int(code) if code.lstrip("-").isdigit() else None,
        pair=request.args.get("pair") == "1",
        from_year=request.args.get("from_year") or None,
        to_year=request.args.get("to_year") or None,
        include_same_coord=request.args.get("same") == "1",
        both_in=request.args.get("both") == "1",
        limit=limit,
    ))


@app.route("/api/cbdb/network/group", methods=["POST"])
def cbdb_network_group():
    """群体社会关系网络（原生 Query Social Networks 窗体）：POST {ids:[...]}
    可选 include_kin + up/down/col/mar 四参数（≤80 人时外延）、dy 朝代过滤。"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "请提供人物 ID 列表"})
    def _p(name, default):
        try:
            return int(payload.get(name, default))
        except (TypeError, ValueError):
            return default
    return jsonify(CBDBConnection.network_group(
        ids,
        include_kin=bool(payload.get("include_kin")),
        up=_p("up", 1), down=_p("down", 1), col=_p("col", 0), mar=_p("mar", 0),
        dynasty_code=payload.get("dy") or None,
    ))


@app.route("/api/cbdb/group/data", methods=["POST"])
def cbdb_group_data():
    """按人群查询（原生 Look Up Data on a Group of People）：POST {ids:[...]}
    一批人物的属性总表（入仕/官职/社会区分/著作/亲属/社会关系数），一人一行的扁平表。"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "请提供人物 ID 列表"})
    return jsonify(CBDBConnection.group_data(ids))


@app.route("/api/cbdb/year/people", methods=["GET"])
def cbdb_year_people():
    """年份检索：?year= 公历年份，?dy= 朝代过滤，&ids= 逗号分隔人物ID列表（范围传递），
    &entry= 入仕方式（关键词或代码，如 进士）；返回 {total, persons}，带 entry 元数据回显"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    year = request.args.get("year", "").strip()
    if not year or not year.lstrip("-").isdigit():
        return jsonify({"error": "请输入有效的公历年份"})
    dy = request.args.get("dy", "").strip() or None
    pids = None
    raw_ids = request.args.get("ids", "").strip()
    if raw_ids:
        try:
            pids = [int(i) for i in raw_ids.split(",") if i.strip().lstrip("-").isdigit()][:5000]
        except ValueError:
            pids = None
    entry_code = None
    entry_raw = request.args.get("entry", "").strip()
    if entry_raw:
        if entry_raw.lstrip("-").isdigit():
            entry_code = int(entry_raw)
        else:
            entry_code = CBDBConnection.resolve_entry_code(entry_raw)
            if entry_code is None:
                return jsonify({"error": f"未找到入仕方式：{entry_raw}"})
    result = CBDBConnection.persons_by_year(
        int(year), dynasty_code=dy, person_ids=pids, entry_code=entry_code)
    if entry_code:
        result["entry_code"] = entry_code
        result["entry_name"] = CBDBConnection.entry_code_name(entry_code)
    return jsonify(result)


@app.route("/api/cbdb/persons/geojson", methods=["POST"])
def cbdb_persons_geojson():
    """人物地址批量导出 GeoJSON（三期 GIS 导出 + 十期任职地联动）：
    POST {ids:[...], addr_source?: 'bio'|'posted'|'all', with_offices?: bool, addr_types?: [...]}
    → FeatureCollection。每个带坐标的地址记录一个点要素；可直接拖入 QGIS。
    posted 模式 feature 额外含 office/office_id（任职地+官名）。"""
    if not CBDBConnection.is_available():
        return jsonify({"error": "CBDB 本地数据库未连接"})
    data = request.json or {}
    try:
        ids = [int(i) for i in (data.get("ids") or [])][:2000]
    except (ValueError, TypeError):
        return jsonify({"error": "ids 参数无效"}), 400
    if not ids:
        return jsonify({"error": "ids 不能为空"}), 400
    try:
        addr_types = [int(t) for t in (data.get("addr_types") or [])][:20]
    except (ValueError, TypeError):
        addr_types = []
    addr_source = (data.get("addr_source") or "bio").lower()
    if addr_source not in ("bio", "posted", "all"):
        addr_source = "bio"
    with_offices = bool(data.get("with_offices"))
    return jsonify(CBDBConnection.persons_geojson(
        ids, addr_types=addr_types, addr_source=addr_source, with_offices=with_offices))

# ── API: DeepSeek AI ────────────────────────────────────

@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    """AI 对话（兼容 {messages} 与 {message, history} 两种请求格式）"""
    data = request.json or {}
    messages = data.get("messages") or []
    if not messages and data.get("message"):
        messages = [{"role": "user", "content": data["message"]}]
    stream = data.get("stream", False)

    if not messages:
        return jsonify({"error": "messages 不能为空"})

    result = deepseek_chat(messages, stream)
    # 统一解包：保留 OpenAI 原始结构，同时提供 response 便捷字段
    if isinstance(result, dict) and "choices" in result:
        try:
            result["response"] = result["choices"][0]["message"]["content"]
        except Exception:
            pass
    return jsonify(result)

@app.route("/api/ai/summarize", methods=["POST"])
def ai_summarize():
    """AI 摘要史料"""
    data = request.json or {}
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "text 不能为空"})

    messages = [
        {"role": "system", "content": "你是一位历史学专家。请对以下史料进行学术摘要，提取关键信息（时间、地点、人物、事件），并分析其史料价值。请用中文回答。"},
        {"role": "user", "content": f"请摘要以下史料：\n\n{text[:4000]}"}
    ]
    result = deepseek_chat(messages)
    return jsonify(result)

@app.route("/api/ai/analyze", methods=["POST"])
def ai_analyze():
    """AI 分析论证"""
    data = request.json or {}
    text = data.get("text", "")
    question = data.get("question", "")

    if not text:
        return jsonify({"error": "text 不能为空"})

    messages = [
        {"role": "system", "content": "你是一位中国历史学专家，擅长文本分析和史学论证。请基于提供的史料进行分析。"},
        {"role": "user", "content": f"史料：\n{text[:4000]}\n\n问题：{question}\n\n请分析："}
    ]
    result = deepseek_chat(messages)
    return jsonify(result)

# ── API: CHGIS ──────────────────────────────────────────

@app.route("/api/chgis/status", methods=["GET"])
def chgis_status():
    """CHGIS 数据状态检查"""
    data_files = []
    if os.path.exists(CHGIS_DATA_DIR):
        for f in os.listdir(CHGIS_DATA_DIR):
            if f.endswith(('.geojson', '.json', '.shp', '.zip')):
                data_files.append({
                    "name": f,
                    "size": os.path.getsize(os.path.join(CHGIS_DATA_DIR, f)),
                    "type": f.split('.')[-1]
                })
    return jsonify({
        "data_dir": CHGIS_DATA_DIR,
        "files": data_files,
        "count": len(data_files)
    })

@app.route("/api/chgis/files", methods=["GET"])
def chgis_list_files():
    """列出可用的 CHGIS 数据文件"""
    files = []
    if os.path.exists(CHGIS_DATA_DIR):
        for f in sorted(os.listdir(CHGIS_DATA_DIR)):
            if f.endswith(('.geojson', '.json')):
                files.append(f)
    return jsonify({"files": files})

@app.route("/api/chgis/file/<filename>", methods=["GET"])
def chgis_get_file(filename):
    """获取 CHGIS GeoJSON 数据"""
    filepath = os.path.join(CHGIS_DATA_DIR, filename)
    if not os.path.exists(filepath) or not filename.endswith(('.geojson', '.json')):
        return jsonify({"error": "文件不存在"}), 404
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chgis/upload", methods=["POST"])
def chgis_upload():
    """上传 CHGIS 数据文件"""
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    allowed = ('.geojson', '.json', '.shp', '.zip')
    if not file.filename.endswith(allowed):
        return jsonify({"error": f"仅支持 {', '.join(allowed)} 格式"}), 400

    filepath = os.path.join(CHGIS_DATA_DIR, file.filename)
    file.save(filepath)
    return jsonify({"success": True, "filename": file.filename, "path": filepath})

@app.route("/api/chgis/capitals", methods=["GET"])
def chgis_capitals():
    """获取都城坐标数据（前端备用，主要数据在 chgis-data.js 中）"""
    capitals = {
        "chang_an": {"name": "长安", "modern": "西安", "lat": 34.34, "lng": 108.94, "dynasty": "唐", "period": "618-907", "type": "首都"},
        "luoyang": {"name": "洛阳", "modern": "洛阳", "lat": 34.62, "lng": 112.45, "dynasty": "唐/北宋", "period": "多朝", "type": "东都"},
        "kaifeng": {"name": "东京（开封）", "modern": "开封", "lat": 34.80, "lng": 114.31, "dynasty": "北宋", "period": "960-1127", "type": "首都"},
        "hangzhou": {"name": "临安", "modern": "杭州", "lat": 30.27, "lng": 120.15, "dynasty": "南宋", "period": "1127-1279", "type": "行在"},
        "beijing_yuan": {"name": "大都", "modern": "北京", "lat": 39.90, "lng": 116.40, "dynasty": "元", "period": "1271-1368", "type": "首都"},
        "beijing_ming": {"name": "顺天府", "modern": "北京", "lat": 39.90, "lng": 116.40, "dynasty": "明清", "period": "1421-1912", "type": "首都"},
    }
    return jsonify(capitals)

@app.route("/api/chgis/dynasty/<dynasty_key>", methods=["GET"])
def chgis_dynasty_border(dynasty_key):
    """获取指定朝代的疆域轮廓 GeoJSON"""
    # 这里可以扩展为从真实 CHGIS 数据加载
    borders = {
        "tang": CHGIS_TANG_BORDER,
        "song_north": CHGIS_SONG_NORTH_BORDER,
        "song_south": CHGIS_SONG_SOUTH_BORDER,
        "yuan": CHGIS_YUAN_BORDER,
        "ming": CHGIS_MING_BORDER,
        "qing": CHGIS_QING_BORDER
    }
    if dynasty_key not in borders:
        return jsonify({"error": "未知朝代"}), 404
    return jsonify(borders[dynasty_key])

# 简化版疆域轮廓数据（内嵌，用于 API 返回）
CHGIS_TANG_BORDER = {
    "type": "Feature",
    "properties": {"dynasty": "唐", "name": "唐帝国疆域", "period": "618-907"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [87.5, 43.0], [95.0, 43.5], [102.0, 44.0], [108.0, 43.5], [116.0, 43.0],
            [122.0, 42.0], [126.0, 40.0], [128.0, 38.0], [130.0, 35.0], [129.0, 32.0],
            [127.0, 30.0], [124.0, 28.0], [121.0, 25.0], [118.0, 23.0], [115.0, 22.0],
            [112.0, 21.5], [109.0, 21.0], [106.0, 21.5], [103.0, 22.0], [100.0, 22.5],
            [97.0, 22.0], [94.0, 21.0], [92.0, 20.0], [90.0, 19.0], [88.0, 20.0],
            [87.0, 22.0], [86.0, 24.0], [85.0, 27.0], [84.0, 30.0], [83.5, 33.0],
            [83.0, 36.0], [83.5, 38.0], [85.0, 40.0], [86.5, 42.0], [87.5, 43.0]
        ]]
    }
}
CHGIS_SONG_NORTH_BORDER = {
    "type": "Feature",
    "properties": {"dynasty": "北宋", "name": "北宋疆域", "period": "960-1127"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [104.0, 38.5], [108.0, 39.0], [112.0, 39.5], [116.0, 40.0], [119.0, 40.5],
            [122.0, 40.0], [124.0, 39.0], [125.0, 38.0], [124.5, 37.0], [123.0, 36.0],
            [121.0, 35.0], [119.0, 34.0], [117.0, 33.0], [115.0, 32.0], [113.0, 31.0],
            [111.0, 30.5], [109.0, 30.0], [107.0, 29.5], [105.0, 29.0], [103.0, 29.5],
            [101.0, 30.0], [99.0, 30.5], [98.0, 31.5], [97.5, 33.0], [98.0, 34.5],
            [99.0, 36.0], [100.5, 37.0], [102.0, 38.0], [104.0, 38.5]
        ]]
    }
}
CHGIS_SONG_SOUTH_BORDER = {
    "type": "Feature",
    "properties": {"dynasty": "南宋", "name": "南宋疆域", "period": "1127-1279"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [104.5, 33.5], [107.0, 34.0], [110.0, 34.5], [113.0, 34.0], [116.0, 33.5],
            [119.0, 33.0], [121.0, 32.5], [122.5, 32.0], [123.0, 31.0], [122.5, 30.0],
            [121.5, 29.0], [120.0, 28.0], [118.0, 27.0], [116.0, 26.0], [114.0, 25.0],
            [112.0, 24.5], [110.0, 24.0], [108.0, 24.5], [106.0, 25.0], [104.0, 26.0],
            [102.0, 27.0], [101.0, 28.0], [100.5, 29.0], [101.0, 30.0], [102.0, 31.5],
            [103.0, 32.5], [104.5, 33.5]
        ]]
    }
}
CHGIS_YUAN_BORDER = {
    "type": "Feature",
    "properties": {"dynasty": "元", "name": "元帝国疆域", "period": "1271-1368"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [75.0, 50.0], [80.0, 52.0], [85.0, 53.0], [90.0, 54.0], [95.0, 55.0],
            [100.0, 55.0], [105.0, 54.0], [110.0, 53.0], [115.0, 52.0], [120.0, 51.0],
            [125.0, 50.0], [130.0, 49.0], [135.0, 48.0], [138.0, 46.0], [140.0, 44.0],
            [141.0, 42.0], [140.0, 40.0], [138.0, 38.0], [136.0, 36.0], [134.0, 34.0],
            [132.0, 32.0], [130.0, 30.0], [128.0, 28.0], [126.0, 26.0], [124.0, 24.0],
            [122.0, 22.0], [120.0, 20.0], [118.0, 18.0], [116.0, 17.0], [114.0, 16.0],
            [112.0, 15.0], [110.0, 14.0], [108.0, 13.0], [106.0, 12.0], [104.0, 11.0],
            [102.0, 10.0], [100.0, 11.0], [98.0, 12.0], [96.0, 13.0], [94.0, 14.0],
            [92.0, 15.0], [90.0, 16.0], [88.0, 17.0], [86.0, 18.0], [84.0, 19.0],
            [82.0, 20.0], [80.0, 22.0], [78.0, 24.0], [76.0, 26.0], [75.0, 28.0],
            [74.0, 30.0], [73.0, 32.0], [72.0, 34.0], [71.0, 36.0], [70.0, 38.0],
            [70.0, 40.0], [71.0, 42.0], [72.0, 44.0], [73.0, 46.0], [74.0, 48.0],
            [75.0, 50.0]
        ]]
    }
}
CHGIS_MING_BORDER = {
    "type": "Feature",
    "properties": {"dynasty": "明", "name": "明帝国疆域", "period": "1368-1644"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [97.0, 42.0], [100.0, 42.5], [104.0, 43.0], [108.0, 43.5], [112.0, 43.0],
            [116.0, 42.5], [120.0, 42.0], [124.0, 41.0], [126.0, 40.0], [127.5, 39.0],
            [128.0, 38.0], [127.5, 37.0], [126.5, 36.0], [125.0, 35.0], [123.0, 34.0],
            [121.0, 33.0], [119.0, 32.0], [117.0, 31.0], [115.0, 30.0], [113.0, 29.0],
            [111.0, 28.5], [109.0, 28.0], [107.0, 27.5], [105.0, 27.0], [103.0, 27.5],
            [101.0, 28.0], [99.0, 29.0], [97.5, 30.0], [96.5, 31.5], [96.0, 33.0],
            [96.0, 34.5], [96.5, 36.0], [97.0, 38.0], [97.0, 40.0], [97.0, 42.0]
        ]]
    }
}
CHGIS_QING_BORDER = {
    "type": "Feature",
    "properties": {"dynasty": "清", "name": "清帝国疆域", "period": "1644-1912"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [80.0, 50.0], [85.0, 51.0], [90.0, 52.0], [95.0, 53.0], [100.0, 53.5],
            [105.0, 53.0], [110.0, 52.0], [115.0, 51.0], [120.0, 50.0], [125.0, 49.0],
            [130.0, 48.0], [135.0, 47.0], [138.0, 45.0], [140.0, 43.0], [141.0, 41.0],
            [140.0, 39.0], [138.0, 37.0], [136.0, 35.0], [134.0, 33.0], [132.0, 31.0],
            [130.0, 29.0], [128.0, 27.0], [126.0, 25.0], [124.0, 23.0], [122.0, 21.0],
            [120.0, 19.0], [118.0, 17.0], [116.0, 16.0], [114.0, 15.0], [112.0, 14.0],
            [110.0, 13.0], [108.0, 12.0], [106.0, 11.0], [104.0, 10.0], [102.0, 10.5],
            [100.0, 11.0], [98.0, 12.0], [96.0, 13.0], [94.0, 14.0], [92.0, 15.0],
            [90.0, 16.0], [88.0, 17.0], [86.0, 18.0], [84.0, 19.0], [82.0, 20.0],
            [80.0, 22.0], [78.0, 24.0], [76.0, 26.0], [75.0, 28.0], [74.0, 30.0],
            [73.0, 32.0], [72.0, 34.0], [71.0, 36.0], [70.0, 38.0], [70.0, 40.0],
            [71.0, 42.0], [72.0, 44.0], [73.0, 46.0], [74.0, 48.0], [75.0, 49.0],
            [76.0, 49.5], [78.0, 50.0], [80.0, 50.0]
        ]]
    }
}

@app.route("/api/status", methods=["GET"])
def system_status():
    """系统状态检查（三项并行探测，整体 4 秒超时，结果缓存 30 秒）"""
    import time as _time
    import concurrent.futures

    now = _time.time()
    if _STATUS_CACHE["data"] and now - _STATUS_CACHE["time"] < 30:
        return jsonify(_STATUS_CACHE["data"])

    checks = {
        "obsidian": _check_obsidian,
        "cbdb": _check_cbdb,
        "deepseek": _check_deepseek,
    }
    results = {}
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    try:
        futures = {executor.submit(fn): key for key, fn in checks.items()}
        done, _ = concurrent.futures.wait(futures, timeout=4)
        for f in done:
            key = futures[f]
            try:
                results[key] = bool(f.result())
            except Exception:
                results[key] = False
    finally:
        executor.shutdown(wait=False)
    for key in checks:
        results.setdefault(key, False)

    status = {
        "server": "running",
        "time": datetime.now().isoformat(),
        "obsidian": results["obsidian"],
        "cbdb": results["cbdb"],
        "deepseek": results["deepseek"],
        "chgis": {"data_dir": CHGIS_DATA_DIR, "files": len(os.listdir(CHGIS_DATA_DIR)) if os.path.exists(CHGIS_DATA_DIR) else 0},
    }
    _STATUS_CACHE["time"] = now
    _STATUS_CACHE["data"] = status
    return jsonify(status)


_STATUS_CACHE = {"time": 0, "data": None}


def _check_obsidian():
    try:
        r = requests.get(f"http://127.0.0.1:{OBSIDIAN_API_PORT}/", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _check_cbdb():
    try:
        return bool(CBDBConnection.is_available())
    except Exception:
        return False


def _check_deepseek():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    try:
        if api_key:
            r = requests.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=4)
        else:
            r = requests.post("http://127.0.0.1:8642/v1/chat/completions",
                json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=4)
        return r.status_code == 200
    except Exception:
        return False

@app.route("/api/obsidian/init-folders", methods=["POST"])
def obsidian_init_folders():
    """自动创建 Vault 标准文件夹结构"""
    folders = ["论文", "札记", "日记", "人物", "史料"]
    created = []
    errors = []

    for folder in folders:
        # 通过创建 README.md 来自动创建文件夹
        readme_content = f"# {folder}\n\n"
        if folder == "论文":
            readme_content += "在此文件夹中存放你的学术论文。\n"
        elif folder == "札记":
            readme_content += "日常学术思考与阅读笔记。\n"
        elif folder == "日记":
            readme_content += "每日学习记录。\n"
        elif folder == "人物":
            readme_content += "历史人物卡片。\n"
        elif folder == "史料":
            readme_content += "史料收藏与摘录。\n"

        placeholder = f"{folder}/README.md"
        result = obsidian_api("PUT", f"/vault/{placeholder}", {"content": readme_content})
        if "error" not in result:
            created.append(folder)
        else:
            errors.append({"folder": folder, "error": result["error"]})

    # 创建学术动态模板
    news_template = """# 学术动态

在此文件中维护学术动态列表，每行一条，格式：

- [标题](链接) NEW
- [标题](链接) HOT
- 标题（无链接也可以）

标签说明：NEW = 新发布，HOT = 热门
"""
    news_result = obsidian_api("PUT", "/vault/学术动态.md", {"content": news_template})
    if "error" not in news_result:
        created.append("学术动态.md")

    return jsonify({"created": created, "errors": errors})


# ── API: CHGIS 真实数据 ─────────────────────────────────

@app.route("/api/chgis/regime", methods=["GET"])
def chgis_regime():
    """加载真实 CHGIS 政权边界数据"""
    geojson_path = os.path.join(CHGIS_DATA_DIR, "geojson", "Regime_Bou.geojson")
    if not os.path.exists(geojson_path):
        return jsonify({"error": "Regime_Bou.geojson 不存在"}), 404

    # 支持按年份范围过滤
    beg_year = request.args.get("beg_year", type=int)
    end_year = request.args.get("end_year", type=int)

    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 如果有过滤条件，按年份筛选
        if beg_year is not None or end_year is not None:
            filtered = []
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                feat_beg = props.get("BEG_YR", 0)
                feat_end = props.get("END_YR", 9999)
                if beg_year is not None and feat_end < beg_year:
                    continue
                if end_year is not None and feat_beg > end_year:
                    continue
                filtered.append(feat)
            data = {"type": "FeatureCollection", "features": filtered}

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 启动预热 ────────────────────────────────────────────
def _cbdb_warmup():
    """后台预热：冷启动后首个 CBDB 查询要 ~79s（Access 打开 613MB mdb 冷文件 +
    坐标缓存全量加载）。desktop.py 是 `from app import app` 同进程起服务，
    所以钩子必须在模块级（__main__ 守卫在生产版不会触发）。
    预热与用户点开窗口的操作重叠，失败不影响使用（首个查询按需加载）。"""
    import time as _time
    try:
        t0 = _time.time()
        conn = CBDBConnection.get_conn()
        if not conn:
            print("[warmup] CBDB 连接失败，跳过预热", flush=True)
            return
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ADDR_CODES")
        cur.fetchone()
        CBDBConnection._addr_coords()  # 顺便装反查坐标缓存（单飞锁防并发重复）
        print(f"[warmup] CBDB 预热完成（连接 + 坐标缓存，{_time.time() - t0:.1f}s）", flush=True)
    except Exception as e:
        print(f"[warmup] CBDB 预热失败（不影响使用）: {e}", flush=True)

# WERKZEUG_RUN_MAIN 守卫：debug 重载模式下只在子进程预热一次
if os.environ.get("WERKZEUG_RUN_MAIN") in (None, "true"):
    threading.Thread(target=_cbdb_warmup, daemon=True).start()

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

@app.route("/api/zotero/status", methods=["GET"])
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

@app.route("/api/zotero/recent", methods=["GET"])
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

@app.route("/api/zotero/search", methods=["GET"])
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
            if v.get("path", "").endswith(OBSIDIAN_VAULT):
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

@app.route("/api/zotero/item/<key>/attachments", methods=["GET"])
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

@app.route("/api/obsidian/zotero-note", methods=["POST"])
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

# ── Zotero 附件 PDF 直读(内嵌阅读器用)────────────────────
def _activity_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    d = os.path.join(base, "JuneXi")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "activity.jsonl")

def _log_activity(act, label):
    """轻量本地足迹: jsonl 追加, 只存本机不外发"""
    try:
        rec = {"t": __import__("time").time(), "act": act, "label": (label or "")[:80]}
        with open(_activity_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

@app.route("/api/activity/recent", methods=["GET"])
def activity_recent():
    limit = min(int(request.args.get("limit", 6)), 20)
    try:
        path = _activity_path()
        if not os.path.isfile(path):
            return jsonify({"ok": True, "items": []})
        lines = open(path, encoding="utf-8", errors="ignore").readlines()[-60:]
        items = []
        for ln in reversed(lines):
            ln = ln.strip()
            if not ln:
                continue
            try:
                items.append(json.loads(ln))
            except Exception:
                pass
            if len(items) >= limit:
                break
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]})

_RECENTLY_READ_CACHE = {"t": 0, "items": []}

@app.route("/api/zotero/recently-read", methods=["GET"])
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
            s, data = _zotero_get("/api/users/0/items/%s" % att_key)
            ad = data.get("data", {})
            parent = ad.get("parentItem")
            if parent:
                s2, pdata = _zotero_get("/api/users/0/items/%s" % parent)
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

@app.before_request
def _activity_hook():
    """CBDB 检索 / 存笔记 自动记足迹(读论文在 pdf 路由里记, 那边有标题)"""
    try:
        path = request.path
        if path == "/api/obsidian/zotero-note" and request.method == "POST":
            body = request.get_json(force=True, silent=True) or {}
            _log_activity("note", "存笔记：" + (body.get("title") or "")[:40])
        elif path == "/api/cbdb/persons" and request.args.get("q"):
            _log_activity("search", "CBDB 查人：" + request.args.get("q", "")[:30])
        elif path == "/api/cbdb/offices/search" and request.args.get("q"):
            _log_activity("search", "CBDB 查官：" + request.args.get("q", "")[:30])
        elif path == "/api/cbdb/places/search" and request.args.get("q"):
            _log_activity("search", "CBDB 查地：" + request.args.get("q", "")[:30])
    except Exception:
        pass

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

@app.route("/api/zotero/pdf/<att_key>", methods=["GET"])
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

# ── 外部协议调起(WebView2 点 zotero:// obsidian:// 不响应, 走后端调起系统)──
def _launch_uri(u):
    """调起 zotero:// / obsidian://。
    os.startfile 对部分会话/失效注册表报'找不到应用程序';
    策略: 注册表 shell\open\command -> 校验 exe 真实存在 -> 失效则常见路径兜底 -> 最后才 startfile。"""
    import subprocess as _sp
    import re as _re
    scheme = u.split(":", 1)[0]
    exe, args = None, []
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, scheme + r"\shell\open\command")
        tpl = winreg.QueryValue(k, "")
        m = _re.match(r'"([^"]+)"\s*(.*)', tpl)
        if m and os.path.isfile(m.group(1)):
            exe = m.group(1)
            arg = m.group(2).replace('"%1"', u).replace("%1", u).strip()
            args = arg.split() if arg else []
    except Exception:
        pass
    if not exe:
        cands = []
        if scheme == "zotero":
            cands = [r"C:\Program Files\Zotero\zotero.exe",
                     r"C:\Program Files (x86)\Zotero\zotero.exe",
                     os.path.expanduser(r"~\AppData\Local\Zotero\zotero.exe")]
        elif scheme == "obsidian":
            cands = [os.path.expanduser(r"~\AppData\Local\Programs\Obsidian\Obsidian.exe"),
                     os.path.expanduser(r"~\AppData\Local\Obsidian\Obsidian.exe"),
                     r"C:\Program Files\Obsidian\Obsidian.exe"]
        for c in cands:
            if os.path.isfile(c):
                exe = c
                if scheme == "zotero":
                    args = ["-url", u]
                else:
                    args = [u]
                break
    if exe:
        _sp.Popen([exe] + args)
        return True
    os.startfile(u)
    return True

@app.route("/api/open-url", methods=["GET"])
def open_external_url():
    u = request.args.get("u", "").strip()
    if not u:
        return jsonify({"ok": False, "error": "empty url"}), 400
    if not (u.startswith("zotero://") or u.startswith("obsidian://")
            or u.startswith("http://") or u.startswith("https://")):
        return jsonify({"ok": False, "error": "scheme not allowed"}), 400
    try:
        if u.startswith(("zotero://", "obsidian://")):
            _launch_uri(u)
        else:
            import webbrowser
            webbrowser.open(u)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]})

# ── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("HISTORIA_PORT", "5000"))
    debug = os.environ.get("HISTORIA_DEBUG", "0") == "1"
    print("=" * 50)
    print("六月息 · 历史学学术面板")
    print("=" * 50)
    print(f"访问地址: http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="127.0.0.1", port=port, debug=debug)
