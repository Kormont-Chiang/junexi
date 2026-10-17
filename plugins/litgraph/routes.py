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

spec_f = importlib.util.spec_from_file_location(
    "jx_plugin_litgraph_fetcher", os.path.join(_HERE, "fetcher.py"))
_fetcher = importlib.util.module_from_spec(spec_f)
sys.modules["jx_plugin_litgraph_fetcher"] = _fetcher
spec_f.loader.exec_module(_fetcher)

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
.lit-wrap{display:flex;gap:14px;height:calc(100vh - 170px);min-height:440px}
.lit-left{width:350px;flex:none;overflow-y:auto;padding:2px 4px 12px 2px}
.lit-card{background:var(--bg-card);border:1px solid var(--border);border-radius:14px;padding:14px 16px;margin-bottom:12px}
.lit-card h3{margin:0 0 3px;font-size:15px;letter-spacing:.4px}
.lit-card-sub{font-size:11.5px;color:var(--text-muted);line-height:1.6;margin-bottom:10px}
.lit-card label.lit-lab{display:block;font-size:12px;color:var(--text-muted);margin:9px 0 4px}
.lit-card input,.lit-card textarea{width:100%;box-sizing:border-box;font-size:12.5px;
  padding:7px 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text)}
.lit-card textarea{height:64px;resize:vertical;font-family:Consolas,monospace;margin-bottom:2px}
.lit-go{margin-top:11px;width:100%;padding:8px 0;border:0;border-radius:9px;
  background:linear-gradient(135deg,#d4b47e,#c9a96e);color:#fff;font-size:13.5px;letter-spacing:2px;cursor:pointer;transition:filter .15s,transform .1s}
.lit-go:hover{filter:brightness(1.06)}
.lit-go:active{transform:scale(.99)}
.lit-go:disabled{opacity:.55;cursor:default}
.lit-go.lit-go-blue{background:linear-gradient(135deg,#4a7c9e,#3a6a8a)}
.lit-row{display:flex;gap:7px}
.lit-row input{flex:1}
.lit-row button{flex:none;padding:7px 14px;border:1px solid var(--border);border-radius:8px;background:var(--bg);cursor:pointer;font-size:12.5px;color:var(--text)}
.lit-row button:hover{background:var(--bg-card)}
.lit-hint{font-size:11.5px;color:var(--text-muted);line-height:1.65;margin-top:8px}
.lit-cand{display:block;padding:7px 9px;border:1px solid var(--border);border-radius:9px;margin-bottom:6px;cursor:pointer;transition:border-color .15s,background .15s}
.lit-cand:hover{border-color:#c9a96e;background:rgba(201,169,110,.07)}
.lit-cand input{margin-right:6px}
.lit-cand .t{font-size:12.5px;font-weight:600}
.lit-cand .s{font-size:11px;color:var(--text-muted);margin-top:2px}
.lit-cand .warn{color:#c07a6a;font-size:11px}
.lit-stats{font-size:11.5px;color:var(--text-muted);margin-top:9px;line-height:1.7;white-space:pre-wrap}
.lit-saved{margin-top:10px;font-size:12px}
.lit-saved a{color:#2e5e8c;cursor:pointer;display:inline-block;margin:0 6px 4px 0}
.lit-right{flex:1;display:flex;flex-direction:column;gap:8px;min-width:0}
.lit-legend{display:flex;gap:7px;flex-wrap:wrap;align-items:center;font-size:11.5px;color:var(--text-muted)}
.lit-legend .lg{display:inline-flex;align-items:center;gap:5px;padding:3px 11px;border-radius:999px;border:1px solid var(--border);background:var(--bg-card)}
.lit-legend .lg i{width:8px;height:8px;border-radius:50%;display:inline-block}
.lit-graphbox{flex:1;display:flex;gap:10px;min-height:0}
#litGraph{flex:1;min-width:0;border:1px solid var(--border);border-radius:12px;background:var(--bg-card);position:relative}
#litGraph.lit-empty::after{content:'← 左侧选种子建图, 文献网络将在这里展开';position:absolute;inset:0;
  display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:13px;
  letter-spacing:1.5px;pointer-events:none}
#litPanel{width:280px;flex:none;border:1px solid var(--border);border-radius:12px;padding:13px 14px;
  overflow-y:auto;font-size:13px;display:none;background:var(--bg-card)}
#litPanel h4{margin:0 0 8px;font-size:14px;line-height:1.5}
#litPanel .lit-meta{color:var(--text-muted);font-size:12px;line-height:1.8;margin-bottom:10px;white-space:pre-wrap}
#litPanel a.btn{display:block;text-align:center;margin-top:6px;padding:6px 0;border-radius:7px;
  background:var(--bg);color:var(--text);text-decoration:none;font-size:12px;border:1px solid var(--border)}
#litPanel a.btn:hover{border-color:#c9a96e}
</style>
<div class="lit-left">
  <div class="lit-card">
    <h3>🔎 OpenAlex 自动建图</h3>
    <div class="lit-card-sub">粘英文标题或 DOI，自动拉参考文献 + 被引 + 相关文献。英文文献首选此路。</div>
    <div class="lit-row">
      <input id="litOaQ" placeholder="标题 或 DOI, 如 10.1086/663830">
      <button id="litOaSearch">搜索</button>
    </div>
    <div id="litOaCands"></div>
    <button class="lit-go lit-go-blue" id="litOaBuild" style="display:none">用选中项生成图谱</button>
    <div class="lit-stats" id="litOaStats"></div>
  </div>
  <div class="lit-card">
    <h3>📋 知网 / 国社科导出</h3>
    <div class="lit-card-sub">中文文献引用关系只有中文库有。检索页勾文献 → 导出与分析 → 复制 <b>Refworks</b> 或 <b>GB/T 7714</b> 粘贴。① = 种子引用了谁，② = 谁引用了种子。</div>
    <label class="lit-lab">种子文献标题</label>
    <input id="litSeed" placeholder="如: 北魏洛阳城的形制与布局">
    <label class="lit-lab">① 参考文献（种子 → 这些）</label>
    <textarea id="litRefs" placeholder="[1] 作者. 标题[J]. 刊名, 年.  或 Refworks 块"></textarea>
    <label class="lit-lab">② 引证文献（这些 → 种子）</label>
    <textarea id="litCitedby" placeholder="同上, 来自知网'引证文献'页"></textarea>
    <button class="lit-go" id="litBuild">生成图谱</button>
  </div>
  <div class="lit-stats" id="litStats"></div>
  <div class="lit-saved" id="litSaved"></div>
</div>
<div class="lit-right">
  <div class="lit-legend" id="litLegend"></div>
  <div class="lit-graphbox">
    <div id="litGraph"></div>
    <div id="litPanel"></div>
  </div>
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


@bp.route("/api/litgraph/oa_search", methods=["POST"])
def litgraph_oa_search():
    d = request.get_json(silent=True) or {}
    q = (d.get("query") or "").strip()
    if not q:
        return jsonify({"error": "缺查询词"}), 400
    try:
        cands, total = _fetcher.search_works(q, limit=5)
    except Exception as e:
        return jsonify({"error": u"OpenAlex 请求失败: %s（当前网络可能不可达，可开代理或改用知网手动导出）" % e}), 502
    if not cands:
        return jsonify({"ok": True, "total": 0, "candidates": []})
    return jsonify({"ok": True, "total": total, "candidates": cands})


@bp.route("/api/litgraph/oa_expand", methods=["POST"])
def litgraph_oa_expand():
    d = request.get_json(silent=True) or {}
    oa_id = (d.get("openalex_id") or "").strip()
    seed_title = (d.get("seed_title") or "").strip()
    if not oa_id and not seed_title:
        return jsonify({"error": "缺种子"}), 400
    n_refs = max(1, min(int(d.get("n_refs") or 100), 200))
    n_citedby = max(1, min(int(d.get("n_citedby") or 50), 200))
    n_related = max(0, min(int(d.get("n_related") or 20), 50))
    # R115: 未显式传参时用插件配置的默认值
    try:
        import plugin_loader as _pl
        _cfg = _pl.get_plugin_config("litgraph")
        if not d.get("n_refs"):
            n_refs = int(_cfg.get("n_refs") or n_refs)
        if not d.get("n_citedby"):
            n_citedby = int(_cfg.get("n_citedby") or n_citedby)
        if not d.get("n_related"):
            n_related = int(_cfg.get("n_related") or n_related)
    except Exception:
        pass
    try:
        if oa_id:
            w = _fetcher.get_work(oa_id)
            seed = _fetcher.norm_work(w)
            refs_ids = w.get("referenced_works") or []
        else:
            cands, _ = _fetcher.search_works(seed_title, limit=1)
            if not cands:
                return jsonify({"error": u"OpenAlex 未找到该标题"}), 404
            w = _fetcher.get_work(cands[0]["oa_id"])
            seed = _fetcher.norm_work(w)
            refs_ids = w.get("referenced_works") or []
        if not seed or not seed.get("title"):
            return jsonify({"error": u"OpenAlex 未返回有效题录"}), 404
        seed_title = seed["title"]
        refs_all = _fetcher.get_works_batch(refs_ids)
        refs_items = refs_all[:n_refs]
        cb_total, cb_items = _fetcher.get_cited_by(oa_id or seed.get("oa_id"), limit=n_citedby)
        rel_items = _fetcher.get_related(oa_id or seed.get("oa_id"), limit=n_related) if n_related else []
    except Exception as e:
        return jsonify({"error": u"OpenAlex 扩展失败: %s" % e}), 502
    seed_id, nodes, edges = _parser.build_graph(seed_title, refs_items, cb_items, rel_items)
    # 种子节点的 OpenAlex 元数据塞回（供题录面板跳 OA/DOI + 后续识别）
    for nd in nodes:
        if nd["id"] == seed_id:
            nd["authors"] = seed.get("authors") or []
            for f in ("source", "year", "oa_id", "doi"):
                nd[f] = seed.get(f) or ""
            nd["cited_by_count"] = seed.get("cited_by_count") or 0
            nd["otype"] = seed.get("type") or ""
            break
    if not seed_id:
        return jsonify({"error": "种子标题无效"}), 400
    gid = "%d" % int(time.time())
    graph = {
        "gid": gid, "seed_id": seed_id, "seed_title": seed_title,
        "nodes": nodes, "edges": edges,
        "stats": {
            "n_ref": len(refs_items), "n_citedby": len(cb_items),
            "n_related": len(rel_items),
            "n_nodes": len(nodes), "n_edges": len(edges),
            "n_merged": sum(1 for nd in nodes if nd.get("n", 0) > 1),
            "n_ref_total": len(refs_ids),
            "n_citedby_total": cb_total,
            "n_refs_truncated": max(0, len(refs_ids) - len(refs_items)),
        },
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_note": u"OpenAlex 自动扩展; 参考文献前 %d/%d 条, 被引按引用数取 top %d(全库命中 %d), 相关 %d 条(虚线, 非引用关系); 覆盖以英文文献为主" % (
            len(refs_items), len(refs_ids), len(cb_items), cb_total, len(rel_items)),
    }
    gpath = os.path.join(_data_dir(), gid + ".json")
    json.dump(graph, open(gpath, "w", encoding="utf-8"), ensure_ascii=False)
    items = _index_load()
    items.insert(0, {"gid": gid, "seed_title": seed_title, "ts": graph["ts"],
                     "n_nodes": graph["stats"]["n_nodes"]})
    _index_save(items[:50])
    return jsonify({"ok": True, "graph": graph})


@bp.route("/api/litgraph/oa_expand_node", methods=["POST"])
def litgraph_oa_expand_node():
    """R111 节点级联扩展: 以图中某节点为中心再扩一层, 合并进当前图谱。
    新节点 kind='ext'(相对种子的二级扩展); 与中心已有边则去重。"""
    d = request.get_json(silent=True) or {}
    gid = (d.get("gid") or "").strip()
    node_id = (d.get("node_id") or "").strip()
    if not gid or not node_id:
        return jsonify({"error": "缺参数"}), 400
    gpath = os.path.join(_data_dir(), gid + ".json")
    if not os.path.exists(gpath):
        return jsonify({"error": "图谱不存在"}), 404
    graph = json.load(open(gpath, encoding="utf-8"))
    if node_id == graph.get("seed_id"):
        return jsonify({"error": "种子节点已全量扩展过, 换个二级节点"}), 400
    nodes = {nd["id"]: nd for nd in graph.get("nodes") or []}
    center = nodes.get(node_id)
    if not center:
        return jsonify({"error": "节点不在图谱中"}), 404
    oa_id = (center.get("oa_id") or "").strip()
    if not oa_id:
        return jsonify({"error": "该节点无 OpenAlex 标识(可能来自知网手动导出), 无法自动扩展"}), 400
    n_refs = max(1, min(int(d.get("n_refs") or 30), 100))
    n_citedby = max(1, min(int(d.get("n_citedby") or 20), 100))
    n_related = max(0, min(int(d.get("n_related") or 10), 30))
    # R115: 未显式传参时用插件配置的默认值(节点扩展档)
    try:
        import plugin_loader as _pl
        _cfg = _pl.get_plugin_config("litgraph")
        if not d.get("n_refs"):
            n_refs = max(1, min(int(_cfg.get("n_refs") or n_refs) // 3, 100))
        if not d.get("n_citedby"):
            n_citedby = max(1, min(int(_cfg.get("n_citedby") or n_citedby) // 3, 100))
        if not d.get("n_related"):
            n_related = max(0, min(int(_cfg.get("n_related") or n_related) // 2, 30))
    except Exception:
        pass
    try:
        w = _fetcher.get_work(oa_id)
        refs_ids = w.get("referenced_works") or []
        refs_items = _fetcher.get_works_batch(refs_ids)[:n_refs]
        cb_total, cb_items = _fetcher.get_cited_by(oa_id, limit=n_citedby)
        rel_items = _fetcher.get_related(oa_id, limit=n_related) if n_related else []
    except Exception as e:
        return jsonify({"error": u"OpenAlex 扩展失败: %s" % e}), 502
    edges = list(graph.get("edges") or [])
    have = {(e.get("s"), e.get("t")) for e in edges}
    added = {"nodes": 0, "edges": 0, "ref": 0, "citedby": 0, "related": 0}

    def _add(items, kind):
        for it in items:
            nid = _parser.norm_title(it.get("title"))
            if not nid or nid == node_id:
                continue
            nd = nodes.get(nid)
            if nd is None:
                nd = {
                    "id": nid, "title": it.get("title", ""), "authors": it.get("authors") or [],
                    "source": it.get("source", ""), "year": it.get("year", ""),
                    "oa_id": it.get("oa_id", ""), "doi": it.get("doi", ""),
                    "cited_by_count": it.get("cited_by_count", 0),
                    "otype": it.get("type", ""), "kind": "ext", "n": 1,
                }
                nodes[nid] = nd
                added["nodes"] += 1
            else:
                nd["n"] = nd.get("n", 0) + 1
                for f in ("source", "year", "oa_id", "doi", "cited_by_count", "otype"):
                    if not nd.get(f) and it.get(f):
                        nd[f] = it[f]
                if not nd.get("authors") and it.get("authors"):
                    nd["authors"] = it["authors"]
            e = {"s": node_id, "t": nid} if kind == "ref" else {"s": nid, "t": node_id}
            if kind == "related":
                e["dash"] = True
            if (e["s"], e["t"]) not in have:
                have.add((e["s"], e["t"]))
                edges.append(e)
                added["edges"] += 1
                added[kind] += 1

    _add(refs_items, "ref")
    _add(cb_items, "citedby")
    _add(rel_items, "related")
    graph["nodes"] = list(nodes.values())
    graph["edges"] = edges
    st = graph.setdefault("stats", {})
    st["n_nodes"] = len(graph["nodes"])
    st["n_edges"] = len(edges)
    st["n_ext"] = int(st.get("n_ext") or 0) + 1
    graph["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    mark = u"第 %d 轮扩展·以《%s》为中心 (+引用%d/被引%d/相关%d)" % (
        st["n_ext"], (center.get("title") or "")[:30],
        added["ref"], added["citedby"], added["related"])
    graph["source_note"] = (graph.get("source_note", "") + u"\n" + mark).strip()
    json.dump(graph, open(gpath, "w", encoding="utf-8"), ensure_ascii=False)
    items = _index_load()
    for it in items:
        if it.get("gid") == gid:
            it["n_nodes"] = st["n_nodes"]
            it["ts"] = graph["ts"]
    _index_save(items[:50])
    return jsonify({"ok": True, "graph": graph, "expanded_from": center.get("title", ""),
                    "added": added})


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
