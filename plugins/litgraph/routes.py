# -*- coding: utf-8 -*-
"""文献图谱(litgraph)插件路由: 页面伺服 + 导入解析 + 图谱持久化。
数据存 %LOCALAPPDATA%\\JuneXi\\litgraph\\ (可用 JX_LITGRAPH_DIR 覆盖, 测试用)。
"""
import json
import os
import time

from flask import Blueprint, jsonify, request

import importlib.util
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "jx_plugin_litgraph_parser", os.path.join(_HERE, "parser.py"))
_parser = importlib.util.module_from_spec(spec)
sys.modules["jx_plugin_litgraph_parser"] = _parser
spec.loader.exec_module(_parser)

bp = Blueprint("litgraph", __name__)


def _data_dir():
    d = os.environ.get("JX_LITGRAPH_DIR") or os.path.join(
        os.path.expandvars("%LOCALAPPDATA%"), "JuneXi", "litgraph")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path():
    return os.path.join(_data_dir(), "index.json")


def _index_load():
    try:
        return json.loads(open(_index_path(), encoding="utf-8").read())
    except Exception:
        return []


def _index_save(items):
    tmp = _index_path() + ".tmp"
    json.dump(items, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, _index_path())


_PAGE_HTML = u"""<div class="lit-wrap">
<style>
.lit-wrap{display:flex;gap:12px;height:calc(100vh - 170px);min-height:420px}
.lit-left{width:340px;flex:none;overflow-y:auto;padding-right:4px}
.lit-left h3{margin:4px 0 8px}
.lit-hint{font-size:12px;color:#888;line-height:1.6;margin-bottom:10px}
.lit-left label{display:block;font-size:12px;color:#555;margin:8px 0 3px}
.lit-left input,.lit-left textarea{width:100%;box-sizing:border-box;font-size:12px;
  padding:5px 7px;border:1px solid #ccc;border-radius:5px;background:#fff;color:#222}
.lit-left textarea{height:88px;resize:vertical;font-family:Consolas,monospace}
.lit-build{margin-top:10px;width:100%;padding:7px 0;border:0;border-radius:6px;
  background:#d4af37;color:#fff;font-size:14px;cursor:pointer}
.lit-stats{font-size:12px;color:#555;margin-top:8px;line-height:1.7;white-space:pre-wrap}
.lit-saved{margin-top:10px;font-size:12px}
.lit-saved a{color:#2e5e8c;cursor:pointer;display:inline-block;margin:0 6px 4px 0}
.lit-right{flex:1;display:flex;gap:10px;min-width:0}
#litGraph{flex:1;min-width:0;border:1px solid #e3e0d8;border-radius:8px;background:#fdfcf8}
#litPanel{width:280px;flex:none;border:1px solid #e3e0d8;border-radius:8px;padding:12px;
  overflow-y:auto;font-size:13px;display:none}
#litPanel h4{margin:0 0 8px;font-size:14px;line-height:1.5}
#litPanel .lit-meta{color:#555;font-size:12px;line-height:1.8;margin-bottom:10px;white-space:pre-wrap}
#litPanel a.btn{display:block;text-align:center;margin-top:6px;padding:6px 0;border-radius:5px;
  background:#f4f1e8;color:#333;text-decoration:none;font-size:12px;border:1px solid #d8d3c4}
#litPanel a.btn:hover{background:#ece7d8}
</style>
<div class="lit-left">
  <h3>🕸 文献图谱 · 顺藤摸瓜</h3>
  <div class="lit-hint">知网(机构登录)或国社科文献中心: 文献页/检索页勾文献 → 导出与分析 →
  复制 <b>Refworks</b> 或 <b>GB/T 7714</b> 文本粘贴到下面。① = 种子引用了谁, ② = 谁引用了种子。</div>
  <label>种子文献标题</label>
  <input id="litSeed" placeholder="如: 北魏洛阳城的形制与布局">
  <label>① 参考文献导出(种子 → 这些)</label>
  <textarea id="litRefs" placeholder="[1] 作者. 标题[J]. 刊名, 年.  或 Refworks 块"></textarea>
  <label>② 引证文献导出(这些 → 种子)</label>
  <textarea id="litCitedby" placeholder="同上, 来自知网'引证文献'页"></textarea>
  <button class="lit-build" id="litBuild">生成图谱</button>
  <div class="lit-stats" id="litStats"></div>
  <div class="lit-saved" id="litSaved"></div>
</div>
<div class="lit-right">
  <div id="litGraph"></div>
  <div id="litPanel"></div>
</div>
</div>"""


@bp.route("/plugin/litgraph/page")
def litgraph_page():
    return _PAGE_HTML


@bp.route("/api/litgraph/import", methods=["POST"])
def litgraph_import():
    d = request.get_json(silent=True) or {}
    seed_title = (d.get("seed_title") or "").strip()
    if not seed_title:
        return jsonify({"error": "缺种子标题"}), 400
    refs = _parser.parse_any(d.get("refs") or "")
    citedby = _parser.parse_any(d.get("citedby") or "")
    seed_id, nodes, edges = _parser.build_graph(seed_title, refs, citedby)
    if not seed_id:
        return jsonify({"error": "种子标题无效"}), 400
    gid = "%d" % int(time.time())
    graph = {
        "gid": gid, "seed_id": seed_id, "seed_title": seed_title,
        "nodes": nodes, "edges": edges,
        "stats": {
            "n_ref": len(refs), "n_citedby": len(citedby),
            "n_nodes": len(nodes), "n_edges": len(edges),
            "n_merged": sum(1 for nd in nodes if nd.get("n", 0) > 1),
        },
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_note": u"知网/国社科导出文本解析; 同名标题跨框合并; 题录以原文页为准",
    }
    gpath = os.path.join(_data_dir(), gid + ".json")
    json.dump(graph, open(gpath, "w", encoding="utf-8"), ensure_ascii=False)
    items = _index_load()
    items.insert(0, {"gid": gid, "seed_title": seed_title, "ts": graph["ts"],
                     "n_nodes": graph["stats"]["n_nodes"]})
    _index_save(items[:50])
    return jsonify({"ok": True, "graph": graph})


@bp.route("/api/litgraph/list")
def litgraph_list():
    return jsonify({"ok": True, "items": _index_load()})


@bp.route("/api/litgraph/graph/<gid>")
def litgraph_graph(gid):
    if not gid.replace("_", "").isalnum():
        return jsonify({"error": "bad gid"}), 400
    gpath = os.path.join(_data_dir(), gid + ".json")
    try:
        return jsonify({"ok": True, "graph": json.loads(open(gpath, encoding="utf-8").read())})
    except Exception:
        return jsonify({"error": "not found"}), 404


@bp.route("/api/litgraph/delete/<gid>", methods=["POST"])
def litgraph_delete(gid):
    if not gid.replace("_", "").isalnum():
        return jsonify({"error": "bad gid"}), 400
    try:
        os.remove(os.path.join(_data_dir(), gid + ".json"))
    except OSError:
        pass
    items = [it for it in _index_load() if it.get("gid") != gid]
    _index_save(items)
    return jsonify({"ok": True})
