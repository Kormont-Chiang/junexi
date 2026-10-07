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
APP_VERSION = "0.2.3"
APP_REPO = "Kormont-Chiang/junexi"
OBSIDIAN_API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"  # 默认模型

# 可选 AI 模型注册表: chat 端点按客户端传来的 model 分发
AI_MODELS = [
    {"id": "deepseek-chat", "name": "DeepSeek 对话", "desc": "日常问答与写作,响应快", "via": "deepseek", "model": "deepseek-chat"},
    {"id": "deepseek-reasoner", "name": "DeepSeek 深思", "desc": "复杂推理/长链条论证,慢但深", "via": "deepseek", "model": "deepseek-reasoner"},
    {"id": "openclaw", "name": "OpenClaw 网关", "desc": "走本机网关,模型取决于 OpenClaw 配置", "via": "openclaw", "model": "kimi-coding/k2p6"},
]

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

def _model_cfg(model_id):
    """按 id 查模型配置; 未知 id 退回默认。"""
    for m in AI_MODELS:
        if m["id"] == model_id:
            return m
    return AI_MODELS[0]


def deepseek_chat(messages, stream=False, model_id=None):
    """按 model_id 分发: deepseek=直连官方API, openclaw=本机网关。fallback 逻辑保留。"""
    cfg = _model_cfg(model_id)
    model_name = cfg.get("model", DEEPSEEK_MODEL)
    via = cfg.get("via", "deepseek")

    # DeepSeek 官方: 有 API key 时优先直连，更快更稳
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if via == "deepseek" and api_key:
        try:
            r = requests.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model_name, "messages": messages, "stream": stream},
                timeout=120)
            if r.status_code == 200:
                return r.json()
        except:
            pass

    # OpenClaw 本地 gateway(对 deepseek-reasoner 等也可兜底)
    try:
        r = requests.post("http://127.0.0.1:8642/v1/chat/completions",
            json={"model": model_name, "messages": messages, "stream": stream},
            timeout=60)
        if r.status_code == 200:
            return r.json()
    except:
        pass

    if via == "deepseek" and not api_key:
        return {"error": "未配置 DeepSeek API Key"}
    return {"error": "模型服务暂不可用（直连与 gateway 均失败）"}

# ── Routes: 页面 ────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory(app.static_folder, path)

# ── API: Obsidian ───────────────────────────────────────

def _vault_resolve(filepath):
    """vault 内安全解析路径, 防目录穿越; 返回绝对路径或 None"""
    vault = _vault_path()
    if not vault:
        return None
    fp = os.path.realpath(os.path.join(vault, filepath))
    if not fp.startswith(os.path.realpath(vault) + os.sep) and fp != os.path.realpath(vault):
        return None
    return fp

@app.route("/api/obsidian/notes", methods=["GET"])
def obsidian_list_notes():
    """列出 Obsidian 笔记（REST 优先, 文件系统兜底）"""
    query = request.args.get("q", "")
    folder = request.args.get("folder", "")

    if query:
        result = obsidian_api("GET", f"/search/simple/?query={quote(query)}")
        if isinstance(result, dict) and "matches" in result:
            return jsonify(result["matches"])
        # 兜底: 文件名+正文扫描
        vault = _vault_path()
        hits = []
        if vault:
            q = query.lower()
            for root, _dirs, files in os.walk(vault):
                if len(hits) >= 50:
                    break
                for fn in files:
                    if not fn.endswith('.md') or fn.startswith('.'):
                        continue
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, vault).replace('\\', '/')
                    hit = q in fn.lower()
                    if not hit:
                        try:
                            if q in open(full, encoding='utf-8', errors='ignore').read(80000).lower():
                                hit = True
                        except Exception:
                            pass
                    if hit:
                        hits.append({"path": rel, "basename": fn})
        return jsonify(hits)

    result = obsidian_api("GET", f"/vault/{quote(folder)}/" if folder else "/vault/")
    if isinstance(result, dict) and "files" in result:
        files = [f for f in result["files"] if not f.startswith('.') and f != 'README.md']
        return jsonify(files)
    # 兜底: 直扫 vault 目录
    vault = _vault_path()
    if not vault:
        return jsonify([])
    base = os.path.join(vault, folder) if folder else vault
    items = []
    try:
        for root, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith('.md') and not fn.startswith('.') and fn != 'README.md':
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, vault).replace('\\', '/')
                    items.append({"basename": fn, "path": rel})
    except Exception:
        pass
    return jsonify(items)

@app.route("/api/obsidian/search", methods=["GET"])
def obsidian_search_alias():
    """兼容旧前端调用的搜索别名(等同 notes?q=)"""
    return obsidian_list_notes()

@app.route("/api/obsidian/note/<path:filepath>", methods=["GET"])
def obsidian_get_note(filepath):
    """读取 Obsidian 笔记内容（REST 优先, 文件系统兜底）"""
    result = obsidian_api("GET", f"/vault/{filepath}")
    if "error" not in result:
        return jsonify(result)
    fp = _vault_resolve(filepath)
    if fp and os.path.isfile(fp):
        try:
            return jsonify({"content": open(fp, encoding='utf-8', errors='ignore').read()})
        except Exception as e:
            return jsonify({"error": str(e)})
    return jsonify({"error": "文件不存在或 Obsidian 未连接"})

@app.route("/api/obsidian/note/<path:filepath>", methods=["PUT"])
def obsidian_update_note(filepath):
    """更新/创建 Obsidian 笔记（REST 优先, 文件系统兜底）"""
    data = request.json or {}
    content = data.get("content", "")
    result = obsidian_api("PUT", f"/vault/{filepath}", {"content": content})
    if "error" not in result:
        return jsonify(result)
    fp = _vault_resolve(filepath)
    if not fp:
        return jsonify({"error": "vault 不可用或路径非法"})
    try:
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return jsonify({"ok": True, "path": fp})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/obsidian/note/<path:filepath>", methods=["DELETE"])
def obsidian_delete_note(filepath):
    """删除 Obsidian 笔记（REST 优先; 兜底=移入 vault/.trash）"""
    result = obsidian_api("DELETE", f"/vault/{filepath}")
    if "error" not in result:
        return jsonify(result)
    fp = _vault_resolve(filepath)
    if not fp or not os.path.isfile(fp):
        return jsonify({"error": "文件不存在"})
    try:
        import shutil as _sh
        vault = _vault_path()
        trash = os.path.join(vault, '.trash')
        os.makedirs(trash, exist_ok=True)
        _sh.move(fp, os.path.join(trash, os.path.basename(fp)))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})

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
    stats = {"total_files": 0, "total_folders": 0, "folders": {}, "root_files": [], "total_chars": 0}

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
    elif not (isinstance(result, dict) and "files" in result):
        # 兜底: 直扫 vault 文件系统
        vault = _vault_path()
        if vault:
            top = {}
            for root, dirs, files in os.walk(vault):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                rel = os.path.relpath(root, vault)
                depth = 0 if rel == '.' else rel.count(os.sep) + 1
                if depth > 2:
                    dirs[:] = []
                    continue
                md = [f for f in files if f.endswith('.md') and not f.startswith('.')]
                for _fn in md:
                    try:
                        stats["total_chars"] += len(open(os.path.join(root, _fn), encoding='utf-8', errors='ignore').read())
                    except Exception:
                        pass
                if rel == '.':
                    stats["root_files"] = md
                    stats["total_files"] += len(md)
                else:
                    key = rel.replace('\\', '/')
                    first = key.split('/')[0]
                    if first not in top:
                        top[first] = {"files": 0, "subfolders": -1}
                    top[first]["files"] += len(md)
                    if key == first:
                        top[first]["subfolders"] += len(dirs) + 1
            stats["folders"] = top
            stats["total_files"] = 0
            stats["total_folders"] = 0
            for k, v in top.items():
                stats["total_files"] += v["files"]
                stats["total_folders"] += max(0, v["subfolders"]) + 1

    # 兼容旧格式：仪表盘使用 论文/札记/人物/史料/日记 作为 key
    legacy = {}
    for folder in ["论文", "札记", "人物", "史料", "日记"]:
        legacy[folder] = stats["folders"].get(folder, {}).get("files", 0)
    stats["legacy"] = legacy

    return jsonify(stats)

# ── API: 学术动态 ─────────────────────────────────────


# ── API: DeepSeek AI ────────────────────────────────────

# ── 联合检索: 一次输入多库并行 ──
def _ctext_search(q):
    """ctext API 无全文检索入口(只按书名/URN 取文本), 返回网页搜索 deeplink。"""
    from urllib.parse import quote as _q
    return [{"title": "在 ctext 检索「%s」" % q,
             "link": "https://ctext.org/searchbooks.pl?if=gb&searchu=%s" % _q(q),
             "source": "ctext", "deeplink": True}]


def _kf_search(q):
    """Kanripo(汉籍 Repository, GitHub): 全库代码搜索, 无 auth 有 rate limit, 容错优先。"""
    try:
        r = requests.get("https://api.github.com/search/code",
                         params={"q": "%s+org:kanripo" % q, "per_page": 5},
                         headers={"Accept": "application/vnd.github+json"}, timeout=10)
        if r.status_code != 200:
            return {"error": "GitHub 速率限制或未命中"}
        items = r.json().get("items") or []
        return [{"title": it.get("name", ""), "link": it.get("html_url", ""), "repo": (it.get("repository") or {}).get("full_name", "")} for it in items]
    except Exception as e:
        return {"error": str(e)[:80]}


def _local_db_counts(q, base_url=""):
    """CBDB 计数经 HTTP 调 CBDB 插件内部端点(单向依赖: 核心→插件经 HTTP, 不 import 插件)。
    base_url 由请求线程传入——子线程无 request 上下文。"""
    try:
        from urllib.parse import quote as _q
        r = requests.get(base_url + "api/cbdb/_counts?q=" + _q(q), timeout=120)
        d = r.json()
        if not d.get("ok"):
            return {"cbdb_person": -1, "cbdb_office": -1, "cbdb_place": -1}
        return {"cbdb_person": d.get("person", -1), "cbdb_office": d.get("office", -1),
                "cbdb_place": d.get("place", -1)}
    except Exception:
        return {"cbdb_person": -1, "cbdb_office": -1, "cbdb_place": -1}


@app.route("/api/federated/search", methods=["GET"])
def federated_search():
    """联合检索: ctext + Kanripo 真联通; CBDB 本地计数; 订阅库 deeplink。"""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "q 不能为空"}), 400
    results = {"query": q, "ctext": [], "kanripo": None, "local": {}}
    errors = {}

    t1 = threading.Thread(target=lambda: results.__setitem__("ctext", _ctext_search(q)))
    t2 = threading.Thread(target=lambda: results.__setitem__("kanripo", _kf_search(q)))
    base = request.host_url  # 主线程取, 传给子线程(request 是线程本地)
    t3 = threading.Thread(target=lambda: results.__setitem__("local", _local_db_counts(q, base)))
    for t in (t1, t2, t3):
        t.start()
    for t in (t1, t2, t3):
        t.join(timeout=25)

    return jsonify({"ok": True, "results": results})


@app.route("/api/ai/models", methods=["GET"])
def ai_models():
    """可用模型清单(健康状态由前端实测, 这里只给注册表+默认)"""
    return jsonify({"ok": True, "default": AI_MODELS[0]["id"], "models": AI_MODELS})


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

    result = deepseek_chat(messages, stream, model_id=data.get("model"))
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
    """CBDB 状态经 HTTP 探活(插件提供 /api/cbdb/status/health)。"""
    try:
        r = requests.get(request.host_url + "api/cbdb/status/health", timeout=125)
        return r.status_code == 200 and bool(r.json().get("ok"))
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


# ── 插件加载(骨架: 只注册不改现有路由) ──
from plugin_loader import load_plugins, plugin_assets
_plugin_nav, _plugin_loaded, _plugin_skipped = load_plugins(app)

# ── OCR provider 注册（capabilities: ["ocr"] 插件，见 docs/OCR插件化方案.md）──
import ocr_service
ocr_service.discover_ocr_providers()


@app.route("/api/ocr/providers", methods=["GET"])
def ocr_providers():
    return jsonify(ocr_service.providers_status())


@app.route("/api/ocr/run", methods=["POST"])
def ocr_run():
    """对本地图片跑一次 OCR。body: {"path": "<本地路径>"}，限 %TEMP% 或 JuneXi 用户数据目录内。"""
    body = request.get_json(silent=True) or {}
    p = (body.get("path") or "").strip()
    if not p:
        return jsonify({"ok": False, "error": "empty path"}), 400
    ap = os.path.abspath(p)
    allowed = [os.path.abspath(os.path.expandvars(r"%TEMP%")),
               os.path.abspath(ocr_service and os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JuneXi"))]
    if not any(ap.startswith(pre) for pre in allowed):
        return jsonify({"ok": False, "error": "path outside allowed dirs"}), 403
    if not os.path.isfile(ap):
        return jsonify({"ok": False, "error": "file not found"}), 404
    try:
        provider, lines = ocr_service.run_ocr(ap)
    except ocr_service.OCRUnavailable as e:
        return jsonify({"ok": False, "error": "no provider: %s" % e}), 503
    return jsonify({"ok": True, "provider": provider, "lines": lines})


@app.route("/api/ocr/upload", methods=["POST"])
def ocr_upload():
    """浏览器上传图片 → 存 %TEMP% → OCR → 清理。multipart 字段名 file。"""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no file"}), 400
    ext = os.path.splitext(f.filename)[1].lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"):
        return jsonify({"ok": False, "error": "unsupported type %s" % ext}), 400
    import time as _time
    ap = os.path.join(os.path.abspath(os.path.expandvars(r"%TEMP%")), "jx_upload_%d%s" % (int(_time.time() * 1000), ext))
    f.save(ap)
    try:
        provider, lines = ocr_service.run_ocr(ap)
    except ocr_service.OCRUnavailable as e:
        return jsonify({"ok": False, "error": "no provider: %s" % e}), 503
    finally:
        try:
            os.remove(ap)
        except Exception:
            pass
    return jsonify({"ok": True, "provider": provider, "lines": lines})


def _scan_plugin_manifests():
    """扫描全部插件目录(用户目录优先,去重)生成清单(含未加载/已停用的), 带目录来源。"""
    import glob as _glob
    from plugin_loader import load_overrides, effective_enabled, all_plugin_dirs, user_plugins_dir
    items = []
    _ov = load_overrides()
    _seen = set()
    _updir = os.path.abspath(user_plugins_dir())
    for _base in all_plugin_dirs():
        _src = "user" if os.path.abspath(_base) == _updir else "builtin"
        for mf in sorted(_glob.glob(os.path.join(_base, "*", "manifest.json"))):
            try:
                m = json.load(open(mf, encoding="utf-8"))
                pid = m.get("id") or os.path.basename(os.path.dirname(mf))
                if pid in _seen:
                    continue
                _seen.add(pid)
                items.append({
                    "id": pid,
                    "name": m.get("name", pid),
                    "version": m.get("version", "?"),
                    "desc": m.get("desc", ""),
                    "icon": m.get("icon", ""),
                    "enabled": effective_enabled(m, pid, _ov),
                    "loaded": pid in _plugin_loaded,
                    "source": _src,
                    "skip_reason": dict(_plugin_skipped).get(pid, "") if not effective_enabled(m, pid, _ov) else "",
                })
            except Exception as e:
                items.append({"id": os.path.basename(os.path.dirname(mf)), "name": "?", "version": "?", "desc": "", "enabled": False, "loaded": False, "skip_reason": "manifest 解析失败: %s" % str(e)[:80]})
    return items


@app.route("/api/plugins", methods=["GET"])
def api_plugins_list():
    return jsonify({"ok": True, "plugins": _scan_plugin_manifests(), "nav": _plugin_nav,
                    "assets": plugin_assets()})


@app.route("/api/plugins/<pid>/toggle", methods=["POST"])
def api_plugins_toggle(pid):
    """开关写入用户数据目录的 plugin-overrides.json(frozen 下 manifest 只读)。"""
    import glob as _glob
    from plugin_loader import load_overrides, save_overrides, effective_enabled
    _pbase = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    for mf in _glob.glob(os.path.join(_pbase, "plugins", "*", "manifest.json")):
        try:
            m = json.load(open(mf, encoding="utf-8"))
            if m.get("id") == pid or os.path.basename(os.path.dirname(mf)) == pid:
                ov = load_overrides()
                cur = effective_enabled(m, pid, ov)
                ov.setdefault(pid, {})["enabled"] = not cur
                save_overrides(ov)
                return jsonify({"ok": True, "id": pid, "enabled": (not cur), "note": "重启后生效"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:120]}), 500
    return jsonify({"ok": False, "error": "插件不存在"}), 404


@app.route("/api/plugins/<pid>/uninstall", methods=["POST"])
def api_plugins_uninstall(pid):
    """卸载用户目录插件(内置插件拒绝)。删目录+清开关覆盖。"""
    import shutil as _sh
    from plugin_loader import user_plugins_dir, load_overrides, save_overrides
    pdir = os.path.join(user_plugins_dir(), pid)
    if not os.path.isdir(pdir):
        return jsonify({"ok": False, "error": "只能卸载用户目录的插件（内置插件随包分发，不可卸载）"}), 400
    try:
        _sh.rmtree(pdir, ignore_errors=True)
        ov = load_overrides()
        if pid in ov:
            del ov[pid]
            save_overrides(ov)
        return jsonify({"ok": True, "id": pid, "note": "已卸载，重启后彻底移除"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]}), 500


# ── 应用版本 & 更新检查 ─────────────────────────────────
@app.route("/api/app/version", methods=["GET"])
def app_version():
    return jsonify({"ok": True, "version": APP_VERSION, "repo": APP_REPO})

@app.route("/api/update/check", methods=["GET"])
def update_check():
    """查 GitHub latest release 对比当前版本。网络不通时优雅降级。"""
    import urllib.request as _ur
    import re as _re
    try:
        req = _ur.Request("https://api.github.com/repos/%s/releases/latest" % APP_REPO,
                          headers={"User-Agent": "JuneXi-UpdateCheck/1.0", "Accept": "application/vnd.github+json"})
        with _ur.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        tag = (d.get("tag_name") or "").lstrip("vV")
        latest = tag or ""
        cur = APP_VERSION
        def _tp(v):
            return tuple(int(x) for x in _re.findall(r"\d+", v)[:3]) if v else (0,)
        avail = _tp(latest) > _tp(cur) if latest else False
        return jsonify({"ok": True, "current": cur, "latest": latest,
                        "update_available": avail,
                        "url": d.get("html_url", ""),
                        "published_at": (d.get("published_at") or "")[:10],
                        "body": (d.get("body") or "")[:300]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:100], "current": APP_VERSION})

@app.route("/api/update/download", methods=["POST"])
def update_download():
    """下载最新 Release 的 zip 到 %LOCALAPPDATA%/JuneXi/updates/，返回本地路径。"""
    import urllib.request as _ur
    try:
        req = _ur.Request("https://api.github.com/repos/%s/releases/latest" % APP_REPO,
                          headers={"User-Agent": "JuneXi-UpdateCheck/1.0", "Accept": "application/vnd.github+json"})
        with _ur.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        asset = None
        for a in (d.get("assets") or []):
            if (a.get("name") or "").endswith(".zip"):
                asset = a
                break
        if not asset:
            return jsonify({"ok": False, "error": "latest release 没有 zip 附件"}), 404
        updir = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "JuneXi", "updates")
        os.makedirs(updir, exist_ok=True)
        dst = os.path.join(updir, asset["name"])
        req2 = _ur.Request(asset["browser_download_url"],
                           headers={"User-Agent": "JuneXi-UpdateCheck/1.0"})
        with _ur.urlopen(req2, timeout=120) as r2, open(dst, "wb") as f:
            while True:
                chunk = r2.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
        import hashlib as _hl
        h = _hl.sha256(open(dst, "rb").read()).hexdigest()
        return jsonify({"ok": True, "path": dst, "size": os.path.getsize(dst),
                        "sha256": h, "tag": (d.get("tag_name") or "")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]}), 500


# ── 插件市场: 安装(本机文件/URL) ─────────────────────────
_PLUGIN_ID_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9\-_]{1,40}$")


def _install_plugin_zip(zf, expect_sha=None):
    """校验+解压插件包到用户插件目录。返回 (ok, info, err)。"""
    import zipfile
    import shutil
    import hashlib
    raw = open(zf, "rb").read()
    if expect_sha:
        h = hashlib.sha256(raw).hexdigest()
        if h.lower() != expect_sha.lower():
            return False, None, "SHA-256 校验失败(期望 %s, 实际 %s)" % (expect_sha[:16], h[:16])
    try:
        z = zipfile.ZipFile(__import__("io").BytesIO(raw))
    except Exception as e:
        return False, None, "zip 打不开: %s" % str(e)[:80]
    # 防路径穿越 + 找 manifest
    names = z.namelist()
    root_prefix = None
    manifest_name = None
    for n in names:
        norm = n.replace("\\", "/").lstrip("/")
        if ".." in norm.split("/"):
            return False, None, "zip 含路径穿越条目: %s" % norm[:60]
        parts = [p for p in norm.split("/") if p]
        if len(parts) == 2 and parts[1] == "manifest.json":
            manifest_name = norm
            root_prefix = parts[0]
    if not manifest_name or not root_prefix:
        # 单文件夹扁平: manifest.json 在根
        if "manifest.json" in [n.replace("\\", "/") for n in names]:
            manifest_name = "manifest.json"
            root_prefix = ""
        else:
            return False, None, "zip 根下找不到 <插件文件夹>/manifest.json"
    try:
        m = json.loads(z.read(manifest_name).decode("utf-8"))
    except Exception as e:
        return False, None, "manifest.json 解析失败: %s" % str(e)[:80]
    pid = (m.get("id") or root_prefix or "").strip()
    if not _PLUGIN_ID_RE.match(pid):
        return False, None, "插件 id 非法(%r): 需小写字母/数字/中划线, 2-40 字符" % pid[:40]
    from plugin_loader import user_plugins_dir
    dest = os.path.join(user_plugins_dir(), pid)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    n_files = 0
    prefix = (root_prefix + "/") if root_prefix else ""
    for n in names:
        norm = n.replace("\\", "/")
        if not norm.startswith(prefix):
            continue
        rel = norm[len(prefix):]
        if not rel or norm.endswith("/"):
            continue
        target = os.path.join(dest, rel)
        if not os.path.abspath(target).startswith(os.path.abspath(dest)):
            return False, None, "解压路径越界: %s" % rel[:60]
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f_out:
            f_out.write(z.read(n))
        n_files += 1
    return True, {"id": pid, "name": m.get("name", pid), "version": m.get("version", "?"),
                  "files": n_files, "permissions": m.get("permissions", ["未声明"])}, None


@app.route("/api/plugins/install", methods=["POST"])
def api_plugins_install():
    """从 URL 或本机路径安装 .jxplugin(zip)。装完需重启生效。"""
    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    sha = (body.get("sha256") or "").strip() or None
    tmp = os.path.join(os.path.expandvars("%TEMP%"), "_jx_install_%d.zip" % __import__("time").time())
    try:
        if url:
            if not (url.startswith("http://") or url.startswith("https://")):
                return jsonify({"ok": False, "error": "仅支持 http(s) URL"}), 400
            import urllib.request as _ur
            req = _ur.Request(url, headers={"User-Agent": "JuneXi-PluginInstaller/1.0"})
            with _ur.urlopen(req, timeout=30) as r:
                open(tmp, "wb").write(r.read())
        elif body.get("local_path"):
            lp = body["local_path"].strip().strip('"')
            if not os.path.isfile(lp):
                return jsonify({"ok": False, "error": "本机文件不存在: %s" % lp[:80]}), 400
            import shutil as _sh
            _sh.copyfile(lp, tmp)
        else:
            return jsonify({"ok": False, "error": "需要 url 或 local_path"}), 400
        ok, info, err = _install_plugin_zip(tmp, sha)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True, "installed": info, "note": "重启 JuneXi 后生效"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]}), 500
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

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

@app.route("/api/activity", methods=["POST"])
def activity_log():
    """前端轻量上报足迹"""
    body = request.get_json(force=True, silent=True) or {}
    act = (body.get("type") or "misc")[:20]
    label = (body.get("label") or "")[:80]
    _log_activity(act, label)
    return jsonify({"ok": True})

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

# ── 工具书数据: 年号考条目检索(李崇智《中国历代年号考》OCR结构化) ──
_NIANHAO_BOOK = []
_NIANHAO_BOOK_LOADED = False
_T2S_MAP = None
# 检索折叠：常见 OCR 形近误字组（已/己、癸/葵、卯/卵），与 T2S 叠加使用
_FOLD_PAIRS = {u'已': u'己', u'葵': u'癸', u'卵': u'卯'}

def _load_t2s():
    global _T2S_MAP
    if _T2S_MAP is None:
        try:
            fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "toolbooks", "t2s_map.json")
            _T2S_MAP = json.load(open(fp, encoding="utf-8"))
        except Exception:
            _T2S_MAP = {}
    return _T2S_MAP

def _fold_key(s):
    """繁简统一 + 形近折叠 → 检索键（用于工具书原书检索的命中判定，不影响显示原文）"""
    if not s:
        return ""
    t2s = _load_t2s()
    return "".join(_FOLD_PAIRS.get(t2s.get(c, c), t2s.get(c, c)) for c in s)

def _vault_path():
    """Obsidian vault 路径: 读 obsidian.json 选最近使用的 vault（插件化拆分时核心侧副本）。"""
    cfg = os.path.expanduser(r"~\AppData\Roaming\obsidian\obsidian.json")
    try:
        d = json.load(open(cfg, encoding="utf-8"))
        best = None
        for v in d.get("vaults", {}).values():
            if v.get("path", "").endswith(OBSIDIAN_VAULT):
                return v["path"]
            if best is None or v.get("ts", 0) > best.get("ts", 0):
                best = v
        return best["path"] if best else None
    except Exception:
        return None

def _load_nianhao_book():
    global _NIANHAO_BOOK, _NIANHAO_BOOK_LOADED
    if _NIANHAO_BOOK_LOADED:
        return
    _NIANHAO_BOOK_LOADED = True
    import json as _json
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "toolbooks", "nianhao_clean.jsonl")
    try:
        for ln in open(fp, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                _NIANHAO_BOOK.append(_json.loads(ln))
    except Exception:
        pass

@app.route("/api/tools/era/book", methods=["GET"])
def tools_era_book():
    """年号原书条目检索: q 命中 ruler/era/note 即返，带书页码溯源"""
    _load_nianhao_book()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "empty q", "total": 0, "items": []})
    q_l = _fold_key(q.lower())
    q_year = q.isdigit() and 1 <= len(q) <= 4
    hits = []
    for e in _NIANHAO_BOOK:
        score = 0
        if q_l and q_l in _fold_key((e.get("ruler") or "").lower()):
            score += 3
        for era in e.get("eras", []):
            if q_l and q_l in _fold_key(era.lower()):
                score += 5
        if q_l in (e.get("year_span") or "").lower():
            score += 2
            if q_year:
                score += 4  # 纯数字年份查询:区间命中额外加权
        if q_l and q_l in _fold_key((e.get("note") or "").lower()):
            score += 1
        if score:
            hits.append((score, e))
    hits.sort(key=lambda x: -x[0])
    items = []
    for score, e in hits[:20]:
        items.append({
            "ruler": e.get("ruler", ""), "eras": e.get("eras", []),
            "year_span": e.get("year_span", ""), "note": e.get("note", "")[:400],
            "page": e.get("page"), "score": score,
        })
    return jsonify({"ok": True, "total": len(hits), "items": items,
                    "source": u"李崇智《中国历代年号考》（修订本），中华书局 2001，PDF 书页"})

# ── 历史地名大辞典（OCR 管线产物，数据就绪前端点优雅降级）──────────
_DIMING_BOOK = []
_DIMING_BOOK_LOADED = False

def _load_diming_book():
    global _DIMING_BOOK, _DIMING_BOOK_LOADED
    if _DIMING_BOOK_LOADED:
        return
    _DIMING_BOOK_LOADED = True
    import json as _json
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "toolbooks", "diming_clean.jsonl")
    try:
        for ln in open(fp, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                _DIMING_BOOK.append(_json.loads(ln))
    except Exception:
        pass

@app.route("/api/tools/diming/book", methods=["GET"])
def tools_diming_book():
    """地名原书条目检索: q 命中 head/note，复用 _fold_key 繁简+形近折叠；数据未就绪返回 404 pending"""
    _load_diming_book()
    if not _DIMING_BOOK:
        return jsonify({"ok": False, "error": "diming data pending", "total": 0, "items": []}), 404
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "empty q", "total": 0, "items": []})
    q_l = _fold_key(q.lower())
    hits = []
    for e in _DIMING_BOOK:
        score = 0
        if q_l and q_l in _fold_key((e.get("head") or "").lower()):
            score += 5
        if q_l and q_l in _fold_key((e.get("note") or "").lower()):
            score += 1
        if score:
            hits.append((score, e))
    hits.sort(key=lambda x: -x[0])
    items = []
    for score, e in hits[:20]:
        items.append({
            "head": e.get("head", ""), "note": e.get("note", "")[:400],
            "page": e.get("page"), "score": score,
        })
    return jsonify({"ok": True, "total": len(hits), "items": items,
                    "source": u"史为乐《中国历史地名大辞典》，中国社会科学出版社 2005，PDF 书页"})

# ── 学术写作技巧面板 ──────────────────────────────────────
WRITING_TIPS = [
    ("史料长编", "动手写论文先做史料长编：把相关史料按类别或年代辑出、条理，再逐步分析，从中检出最能说明问题的材料。", "前言"),
    ("目录", "进一个领域先摸史志目录，丛书目录、佛道藏经目录、类书都是翻检古籍的门径，先摸清史料家底再谈选题。", "第一讲"),
    ("石刻", "别只守着传世文献——新出土石刻常改写认识，要学会用石刻资料目录跟踪收集。", "第二讲"),
    ("简牍文书", "简牍与敦煌吐鲁番文书是中古史的新史料富矿，熟悉它们的目录和录文集是基本功。", "第三、四讲"),
    ("版本", "引用古籍先明版本：标点本有价值也有问题，关键引文务必核对影印底本。", "第五讲"),
    ("校勘", "底本异文可能影响论证——重要段落用校勘方法比勘各本，别让点校者的取舍替你下结论。", "第五讲"),
    ("考古追踪", "定期翻检考古新资料和刊物：新出墓志、简牍、文书，往往直接关涉你的课题。", "第六讲"),
    ("图像", "图像材料提供想象空间——书画著录、图录、画家词典，都是可用的史料。", "第七讲"),
    ("学术史", "动手前查论著目录、研究综述和博硕士论文；写学术史要呈出问题链：前人做了什么、怎么做的、哪里还有余地。", "第八、十讲"),
    ("刊物", "定期翻检期刊（含港台与外文），知道学界此刻在讨论什么，也知道自己能插什么话。", "第九讲"),
    ("标题", "标题要具体——让人一看便知你研究什么材料、什么问题；大而无当的标题撑不起一篇论文。", "第十讲"),
    ("结构", "篇章结构跟着论证走：引言交代问题与路径，正文一段一意层层推进，结论回到问题本身。", "第十讲"),
    ("书评", "书评先准确复述、后评论——没读懂就评是失礼；称呼与分寸有讲究，书评本身就是训练。", "第十二讲"),
    ("注释体例", "注释体例与参考文献格式按目标刊物的规定来——体例统一、信息完备，细节处见功力。", "第十四讲"),
    ("论文类型", "期刊论文、会议论文、学位论文写法不同：先弄清给谁看、在哪发，再定篇幅与结构。", "第十一讲"),
    ("翻译", "专业中英文互译先解决专名问题：人名、地名、官名有约定译法，全文统一，不可临场 invented。", "第十五讲"),
]

TIPS_SOURCE = "据荣新江《学术训练与学术规范：中国古代史研究入门》"

# 知识库: 按该书前言+十五讲整理 (要点为自撰总结, 非原文引录)
KNOWLEDGE_BASE = {
    "source": "荣新江《学术训练与学术规范：中国古代史研究入门》（北京大学出版社2022年第二版）",
    "themes": [
        {"key": "zhixue", "name": "治学根本", "icon": "\u2726", "color": "#c9a96e"},
        {"key": "shiliao", "name": "史料世界", "icon": "\u2739", "color": "#8fb6a8"},
        {"key": "jiansuo", "name": "检索之道", "icon": "\u2317", "color": "#7ea3c4"},
        {"key": "lunwen", "name": "论文写作", "icon": "\u270e", "color": "#c4887a"},
        {"key": "shuping", "name": "书评札记", "icon": "\u270d", "color": "#a58cc7"},
        {"key": "guifan", "name": "规范体例", "icon": "\u00a7", "color": "#7fb8a0"},
        {"key": "daode", "name": "学术道德", "icon": "\u2696", "color": "#c97e8a"},
    ],
    "entries": [
        # ── 治学根本 ─────────────────────────
        {"id": 1, "theme": "zhixue", "src": "前言",
         "text": "史料搜集要竭泽而渔：传世文献、出土文献（简牍文书石刻）、文物图像，尽可能没有遗漏。这是专业学术训练的第一要义。"},
        {"id": 2, "theme": "zhixue", "src": "第一讲",
         "text": "先做史料长编再动笔：把所有相关史料按类别或年代辑出条理，逐步分析，从中检出最能说明问题的材料。李焘编《续资治通鉴长编》即此法；博士论文尤其应当先编长编。"},
        {"id": 3, "theme": "zhixue", "src": "第一讲",
         "text": "带着问题去翻阅：泛览中发现问题，然后带着问题重检已翻过的书，从中辑出研究主题要用的材料。没有问题意识的读书只是抄书。"},
        {"id": 4, "theme": "zhixue", "src": "第一讲",
         "text": "精读与泛览结合：面对如此大量的古籍，不可能本本精读，也不能所有书只知其大概而不求甚解。两种读书方式要配合。"},
        {"id": 5, "theme": "zhixue", "src": "前言",
         "text": "学术贵在创新：有了新材料、新方法、新问题（陈寅恪语意），才能写论文。写出的论文一定要遵守学术规范，才有学术价值和流传价值。"},
        {"id": 6, "theme": "zhixue", "src": "第一讲",
         "text": "研究生阶段是积累的黄金期：年轻时翻阅的书、归拢的材料多，工作后时间相对少，靠的就是这时的积累。历史学在某种程度上靠积累。"},
        {"id": 7, "theme": "zhixue", "src": "第二讲",
         "text": "做学问要细致：西文字体、括号、编号……都要手动一个个改动，百分之九十五的工作电脑做了，剩下必须自己做的不能省。"},
        # ── 史料世界 ─────────────────────────
        {"id": 8, "theme": "shiliao", "src": "第一讲",
         "text": "史志目录是古籍的家底账：《汉书·艺文志》奠定目录学基础，《隋书·经籍志》首次按四部分类、了解魏晋南北朝学术的钥匙；研究唐史还要熟悉两《唐书》经籍艺文志、《日本国见在书目录》、《郡斋读书志》、《直斋书录解题》。"},
        {"id": 9, "theme": "shiliao", "src": "第一讲",
         "text": "《四库全书》的两面性：编纂既是保存古籍也是毁灭古籍——有碍清朝统治的著作被排除销毁，收入者也多经删改。用《四库总目提要》要配余嘉锡《四库提要辨证》、李裕民《订误》；《简明目录》不收存目书，查存目要用中华书局整理本《总目》。"},
        {"id": 10, "theme": "shiliao", "src": "第一讲",
         "text": "丛书检索用《中国丛书综录》倒查法：从第三册书名/作者索引 → 第二册子目 → 第一册总目。使用时还要查《补正》《广录》《续编》三种增补。"},
        {"id": 11, "theme": "shiliao", "src": "第一讲",
         "text": "佛道藏各有独立目录：佛藏先熟悉《开元释教录》，用童玮《二十二种大藏经通检》查某经在哪个藏；道藏只有明正续《道藏》传世，用施舟人《道藏索引》。引《中华道藏》要核对三家影印本原文。"},
        {"id": 12, "theme": "shiliao", "src": "第一讲",
         "text": "类书保存大量佚书：中古史研究尤其重要——《册府元龟》多整篇收录唐五代诏令奏议可勘史籍，《太平广记》引书四百七十五种大半佚散，《永乐大典》中还能辑出《旧五代史》《宋会要》。不翻类书，学问不完整。"},
        {"id": 13, "theme": "shiliao", "src": "第二讲",
         "text": "石刻学入门：先读叶昌炽《语石》（柯昌泗增订本），再看赵超《中国古代石刻概论》。墓志是墓葬组成部分，看墓志要观照同墓出土的其他资料，和考古学结合。"},
        {"id": 14, "theme": "shiliao", "src": "第二讲",
         "text": "新出墓志的史学价值：唐墓志的传记资料远多于两《唐书》史料；妇女、地方士人、下层民众等不见经传的人物，恰是新史学关注的社会群体。"},
        {"id": 15, "theme": "shiliao", "src": "第二讲",
         "text": "用石刻必须核对：各家录文大多没有校记、材料来源交代不清，拓本质量有天壤之别（如《康敬本墓志》残泐本与善拓差别巨大）。重要材料要对照图版、核对数家录文，择善而从。"},
        {"id": 16, "theme": "shiliao", "src": "第二讲",
         "text": "查墓志收录情况：用气贺泽保规《唐代墓志所在总合目录》，看一方墓志收入哪些图版录文集；只见于最新图录的很可能是新材料。馆藏目录（如陕师大墓志拓片目）能提示未刊资料。"},
        {"id": 17, "theme": "shiliao", "src": "第三讲",
         "text": "简牍检索路径：每批简都有整理报告和专门网站，先查正式整理本，再追新公布材料；有简牍学专刊和相关学会。先秦秦汉魏晋简牍各有所重（秦简是制度史一手档案，汉简关乎边郡行政，吴简是基层社会史料）。"},
        {"id": 18, "theme": "shiliao", "src": "第四讲",
         "text": "敦煌文书浏览：散藏英法俄日及国图，IDP（国际敦煌项目）在线可看英藏等原件影像；吐鲁番文书以《吐鲁番出土文书》录文本与图文本两种为核心。录文要核对图版——录文者的补字改字可能影响你的论证。"},
        {"id": 19, "theme": "shiliao", "src": "第六讲",
         "text": "考古发现三大刊：《文物》《考古》《考古学报》定期翻检；考古简报先于正式报告发表；《中国文物报》和新发现通报是速递。用图录选拓本清晰、说明可靠的。"},
        {"id": 20, "theme": "shiliao", "src": "第七讲",
         "text": "图像材料的使用边界：壁画绢画器物提供传世文献不载的物质生活细节，但用图像先问年代与摹本问题——后世摹本不能直接当一手材料。"},
        {"id": 21, "theme": "shiliao", "src": "第九讲",
         "text": "建立自己的核心刊物清单：大陆、港台、外文刊物定期翻检目录，相关的剪存或记入卡片。知道学界此刻在讨论什么，才知道自己该插什么话。"},
        # ── 检索之道 ─────────────────────────
        {"id": 22, "theme": "jiansuo", "src": "第一讲",
         "text": "目录是入手的钥匙：先熟悉古籍和丛书目录、提要，知道某朝某类有哪些书、哪些与自己的专业关系密切，再开始阅读。目录互补——官私藏目录、佛道藏目录、海内外目录、解题目录、佚书目录都要用。"},
        {"id": 23, "theme": "jiansuo", "src": "第五讲",
         "text": "电子全文检索是线索不是依据：底本不明的电子文本只能提供线索，不能当引用依据。关键引文必须回到可靠版本核对。"},
        {"id": 24, "theme": "jiansuo", "src": "第五讲",
         "text": "点校本与影印本：中华书局点校本权威但偶有失误，关键引文要核对影印底本；整理出土的文书简帛更要追原始图版。"},
        {"id": 25, "theme": "jiansuo", "src": "第五讲",
         "text": "校勘四法：对校、本校、他校、理校（陈垣《校勘学释例》）。校勘先选好底本，底本不佳则校记无意义。"},
        {"id": 26, "theme": "jiansuo", "src": "第八讲",
         "text": "检索词要变换：异体字、同义词、甚至日文读法都试一遍。漏检是综述的大敌——题目没检全，学术史就站不住。"},
        {"id": 27, "theme": "jiansuo", "src": "第八讲",
         "text": "今人论著与研究综述：先查专题论著索引（含日本《东洋学文献类目》），看《中国史研究动态》和各断代年鉴；博硕士论文库里有最新未刊成果。电子版检索的便利不能替代对刊物本身的定期翻检。"},
        # ── 论文写作 ─────────────────────────
        {"id": 28, "theme": "lunwen", "src": "第十讲",
         "text": "标题要短而具体：让读者一看知道讨论什么时代什么问题，历史论文要有朝代或时间提示。研究生不像成名学者，题目可以稍长以明确范围。"},
        {"id": 29, "theme": "lunwen", "src": "第十讲",
         "text": "不用「试论」「述论」：要论就论到底；如果只是「试论」，那就暂且不要发表，等研究透彻再来。「述论」给人综述的印象，博硕论文要的是论不是述。"},
        {"id": 30, "theme": "lunwen", "src": "第十讲",
         "text": "题目要有限制：写论文前就要考虑论题限制，以便按时完成。题目涵盖超出实际论述是研究生论文通病，易被匿名评审挑剔——写到开元天宝就不能叫「唐代的岭南」。"},
        {"id": 31, "theme": "lunwen", "src": "第十讲",
         "text": "拟题时同时拟英文题目：现在投稿都要英文题名，自己拟好免得外行人随意翻译闹笑话。中英文双拟还能互相检验表述。"},
        {"id": 32, "theme": "lunwen", "src": "第十一讲",
         "text": "硕士论文以小见大：从小处入手但能联系大问题的题目最好；不宜过早定题把自己局限在很专的范围里，硕士阶段要广泛阅读打厚基础。硕士只是训练过程，不要写得过长过大。"},
        {"id": 33, "theme": "lunwen", "src": "第十一讲",
         "text": "博士论文早定题、早布局：十万字以上不能一蹴而就，早确定题目才能不断积累素材；早安排篇章结构，有计划地分类收集资料撰写初稿，不要什么都放到最后。"},
        {"id": 34, "theme": "lunwen", "src": "第十讲",
         "text": "学术史三件事：搜集要全（中外正反都不能漏）、分期分类叙述、指出缺失——缺失处正是你的论文起点。学术史写不好，论文价值立不住。"},
        {"id": 35, "theme": "lunwen", "src": "前言",
         "text": "学术史的前提是穷尽前人成果：前人研究不论国内国外、论文还是专著，都要检索到并充分利用。漠视前人研究成果的存在是学术失范。"},
        {"id": 36, "theme": "lunwen", "src": "第十讲",
         "text": "篇章结构跟论证走：立意构思先于动笔，论文是提出并解决问题，不是材料的堆积。长引文后的讨论要顶格，段落未结束不缩进。"},
        # ── 书评札记 ─────────────────────────
        {"id": 37, "theme": "shuping", "src": "第十二讲",
         "text": "书评五方面内容：内容简介让读者了解全书；从学术史角度看选题价值与新材料新方法；指出不足要举证据；补正（订错补缺）一定要有十分把握才写；古籍整理类要校勘错字以免贻误后人。"},
        {"id": 38, "theme": "shuping", "src": "第十二讲",
         "text": "评书不评人：可以说这本书如何好如何差，绝不可说作者如何；不写人情稿，不人身攻击，也不吹捧。了解作者的学术出身有助于判断书的水平，但书评里不做作者传。"},
        {"id": 39, "theme": "shuping", "src": "第十二讲",
         "text": "不用出书后的新材料批评作者：要站在和作者同样的起跑线上写书评——作者完成书稿在前，你看到的后出材料只能做补充，不能据以批评人家。"},
        {"id": 40, "theme": "shuping", "src": "第十二讲",
         "text": "不能以偏概全：发现硬伤可以指出，但不揪住不放，更不因此否定全书的其他贡献。礼貌用词，不用「怪圈」一类伤人字眼，用事实说话——有分量的书评最容易引起反批评，事实足则反批评无力。"},
        {"id": 41, "theme": "shuping", "src": "第十二讲",
         "text": "「瑕不掩瑜」「金无足赤」式八股是大忌：写了百分之九十九的好话最后一句套话，说了等于没说。西方书评往往按页码顺序一一挑错，读起来像喝咖啡一样精神一振。"},
        {"id": 42, "theme": "shuping", "src": "第十二讲",
         "text": "书评是年轻学者发挥学术思想的文体：你不可能像陈寅恪那样早给别人写序写审查报告，但可以用书评表达写刻板专题论文时不能表达的学术观点。书评既为读者提供全书信息，也为自己树立学术声音。"},
        {"id": 43, "theme": "shuping", "src": "第十二讲",
         "text": "札记是积累的重要方法：抓住读书中的灵感心得翻检材料写成札记，期刊欢迎短小精悍的文章。札记按一个系统排列归到一本书或主题下，免得零散被遗忘——钱大昕《廿二史考异》、周一良《魏晋南北朝史札记》是样板。"},
        {"id": 44, "theme": "shuping", "src": "第十二讲",
         "text": "西方书评制度值得了解：出版社寄书给期刊，主编约请该领域专家撰写，不接受投稿、不在本刊发反批评。杂志把书评水准看作自身学术水准。中国正在创造性建立自己的书评制度，中青年学者有实力写也敢于写。"},
        # ── 规范体例 ─────────────────────────
        {"id": 45, "theme": "guifan", "src": "第十三讲",
         "text": "标题层级与段落：层级用 一、→(一)→1.→(1)；段落长短适中，太短显凌乱、太长显沉闷。自然段要给文章美观的样子。"},
        {"id": 46, "theme": "guifan", "src": "第十三讲",
         "text": "引文规范：直接引述（前有冒号）句号在引号内；间接摘引标点放在引号外。长引文另起行，首行缩进四格、次行起二格，不再用引号（原有单引号此时改双引号）。引用书名刊名文章名均用《》，书名号内再有书篇名用单书名号〈〉。"},
        {"id": 47, "theme": "guifan", "src": "第十三讲",
         "text": "缺字与订正符号：引用古文缺字要补，补字用中文六角括号〔〕如「神灵〔相〕助」；订正别字错字，正字用圆括号写在后面如「西城（域）人也」。"},
        {"id": 48, "theme": "guifan", "src": "第十三讲",
         "text": "数字与年代规则：源于西文的用阿拉伯数字（公元、页码、期卷号、统计数），源于中文的用汉字（年号、古籍卷数叶数）；年号第一次出现括注公元、括号中不写「年」字，再次出现不必再注；卷数作「卷一八一」不写「卷一百八十一」。"},
        {"id": 49, "theme": "guifan", "src": "第十三讲",
         "text": "繁简转换的坑：简体转繁体后，云（说话）不能转雲、度量衡斗不能转鬥、历（历史）曆（日历）要分、范（姓）範（范围）要分；转换体系是台湾惯用字（裡/為），大陆规范繁体要改回（裏/爲）。电脑转完必须人工逐一改订，直接交稿是不合格的。"},
        {"id": 50, "theme": "guifan", "src": "第十三讲",
         "text": "注号位置：注号一般放在标点符号前面；引完整句（句号在引号内）注号放最后，引短句（标点在外）注号放引号和标点之间。西文字母用 Times New Roman，括号用中式。"},
        {"id": 51, "theme": "guifan", "src": "第十四讲",
         "text": "注释基本顺序：作者、文章名、书刊名、第几卷第几期、出版地、出版社、年代、页码。古籍注作者、书名、卷数、版本、叶数（或页码）；中华标点本同普通书注页码。线装书一叶两面，注「叶一正/叶一背」不作「页」。"},
        {"id": 52, "theme": "guifan", "src": "第十四讲",
         "text": "再次引用要简化：书刊再次出现时删掉出版社和年代只留作者篇名页码。整篇论文中同一注释不允许反复粘贴重复——电脑复制方便，但所有注释都一模一样是完全违规的。"},
        {"id": 53, "theme": "guifan", "src": "第十四讲",
         "text": "出版地可以省略：中国大多数出版社只有一家，「上海：上海古籍出版社」属重复；只有中华书局（京港台三家）、三联（京沪港）这类才需注地。日本学术注释一般不加出版地。《唐研究》体例：除非有重复或稀见出版社才加地名。"},
        {"id": 54, "theme": "guifan", "src": "第十四讲",
         "text": "参考文献编排：最重要原则是前后一致、不自相矛盾。古籍与今人著作分列；古籍按书名拼音排（作者名佚或成书年代不明时按人名排会出问题），今人按作者拼音，西文按姓的拉丁字母序、姓名间用逗号。"},
        {"id": 55, "theme": "guifan", "src": "第十四讲",
         "text": "缩略语的使用：反复出现三次以上的长书名才用缩略语——西文作 KT, IV 或 Trombert 2000，中文作「唐长孺1962」式。中日人名短不必缩成单姓（唐长孺唐耕耦都缩成「唐」就分不清了）。圈内有固定缩略语（如于阗研究的 KT）随众使用。"},
        {"id": 56, "theme": "guifan", "src": "第十四讲",
         "text": "投稿以目标刊物体例为准：给《唐研究》投稿就用《唐研究》规范，否则退稿重来。自己编学位参考文献，通篇一致即可——最怕前后不一致。"},
        {"id": 57, "theme": "guifan", "src": "第十五讲",
         "text": "汉学家名字用本人汉名：沙畹、戴密微、薛爱华、施舟人——绝不能从词典姓名表找音译抄上，也不能自己音译，要用学者自起、学界通用的汉名。工具书：《近代来华外国人名辞典》《北美汉学家辞典》《美国中国学手册》《欧洲中国学》。"},
        {"id": 58, "theme": "guifan", "src": "第十五讲",
         "text": "日本学者名字不能音译：英文书刊中 Egami Namio=江上波夫、Ikeda On=池田温，要按日文发音还原汉字，万万不能按英文读音音译成汉字。"},
        {"id": 59, "theme": "guifan", "src": "第十五讲",
         "text": "华裔与早期中国学者拼写要还原准确：威妥玛式拼法（Jao Tsong-yi=饶宗颐）与汉语拼音不同，转写回来必须准确——不懂这些道理，很可能把一个人弄成两个人。梅维恒用威妥玛式把荣新江写成 Jung Hsin-chiang。"},
        {"id": 60, "theme": "guifan", "src": "第十五讲",
         "text": "人名对照随手积累：遇到可靠书籍上的人名对照就记录下来，建立自己的译名卡片。有些名字至今无解（如 Arthur Waley 的汉名），学界约定俗成的也未必正确。"},
        {"id": 61, "theme": "guifan", "src": "第十五讲",
         "text": "引外文论著要核对原文：英译汉时注意汉学家的固定译名和专业术语的对应；汉译英时年号官名地名的译法要全文统一（先拟好对照表）。外文注释直接用外文原文，便于读者核对。"},
        # ── 学术道德 ─────────────────────────
        {"id": 62, "theme": "daode", "src": "前言",
         "text": "不能一稿两投：论文要一步到位做好，争取时间早日发表；只有译成外文才可以分别投。一稿多投是学术失范。"},
        {"id": 63, "theme": "daode", "src": "前言",
         "text": "谨慎使用电脑的 Copy 功能：所有拷贝的材料要随手注明出处，防止可能发生的无意抄袭。从收集资料起就注到页码，以后一劳永逸。"},
        {"id": 64, "theme": "daode", "src": "前言",
         "text": "预防变相抄袭：除非教材之类，引用其他人的观点一般都要注明出处。不是自己的观点和材料都要出注——通过通信、Email、网聊、电话、谈话获得的观点和材料也要出注。"},
        {"id": 65, "theme": "daode", "src": "前言",
         "text": "正确面对学术批评：年轻学子应当学习写书评，通过纯学术的批评矫正学术失范；也要正确面对别人对自己的批评，在纯学术的范围内对待学术批评。以文会友，批评换来的是更亲切的友情。"},
        {"id": 66, "theme": "daode", "src": "前言",
         "text": "中国要有自己的芝加哥手册：现代学术规范带着西方文化特点，中国长期没有统一规定。在没有统一规范之前，要从我做起，大家共同努力——建立规范是每一个学者的责任。"},
    ],
}

@app.route("/api/writing-kb", methods=["GET"])
def writing_kb():
    return jsonify({"ok": True, "source": KNOWLEDGE_BASE["source"], "themes": KNOWLEDGE_BASE["themes"], "entries": KNOWLEDGE_BASE["entries"]})

@app.route("/api/writing-tips", methods=["GET"])
def writing_tips():
    import random as _rnd
    n = min(int(request.args.get("n", 3)), 6)
    if request.args.get("refresh"):
        picks = _rnd.sample(WRITING_TIPS, min(n, len(WRITING_TIPS)))
    else:
        day_seed = int(__import__("time").strftime("%Y%m%d"))
        rnd = _rnd.Random(day_seed)
        picks = rnd.sample(WRITING_TIPS, min(n, len(WRITING_TIPS)))
    return jsonify({"ok": True, "source": TIPS_SOURCE, "items": [{"tag": t[0], "text": t[1], "lecture": t[2]} for t in picks]})

# ── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("HISTORIA_PORT", "5000"))
    debug = os.environ.get("HISTORIA_DEBUG", "0") == "1"
    print("=" * 50)
    print("六月息 · 历史学学术面板")
    print("=" * 50)
    print(f"访问地址: http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="127.0.0.1", port=port, debug=debug, threaded=True)
