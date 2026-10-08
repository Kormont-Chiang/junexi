# -*- coding: utf-8 -*-
"""灵眸 OCR 插件：状态查询 + 独立页面通道（/plugin/lingmu-ocr/page）
页面引 static/panel.js（经 manifest assets 注入）。
"""
from flask import Blueprint, jsonify, Response

bp = Blueprint("lingmu_ocr", __name__)

PAGE_HTML = u"""<div class="lingmu-wrap">
  <style>
    .lingmu-wrap{max-width:860px;margin:0 auto;padding:18px}
    .lm-card{background:var(--panel,#fff);border:1px solid var(--border,#e3e0d8);border-radius:10px;padding:16px;margin-bottom:14px}
    .lm-status{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--muted,#8a8577)}
    .lm-status b{color:var(--fg,#2b2924)}
    .lm-drop{border:2px dashed var(--border,#d8d4c8);border-radius:10px;padding:34px 16px;text-align:center;cursor:pointer;transition:.2s}
    .lm-drop:hover,.lm-drop.over{border-color:var(--accent,#4a7a68);background:rgba(74,122,104,.06)}
    .lm-drop p{margin:6px 0;font-size:14px}
    .lm-drop .lm-hint{font-size:12px;color:var(--muted,#8a8577)}
    .lm-drop input{display:none}
    .lm-run{margin-top:12px;text-align:right}
    .lm-btn{background:var(--accent,#4a7a68);color:#fff;border:0;border-radius:8px;padding:9px 22px;font-size:14px;cursor:pointer}
    .lm-btn:disabled{opacity:.5;cursor:default}
    .lm-result-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
    .lm-badge{font-size:12px;background:rgba(74,122,104,.12);color:var(--accent,#4a7a68);border-radius:20px;padding:2px 12px}
    .lm-lines{max-height:420px;overflow:auto;font-size:13px;line-height:1.7}
    .lm-line{display:flex;gap:10px;padding:3px 6px;border-radius:6px}
    .lm-line:nth-child(odd){background:rgba(0,0,0,.025)}
    .lm-conf{min-width:44px;text-align:right;font-size:11px;color:var(--muted,#8a8577)}
    .lm-text{flex:1}
    .lm-copy{background:none;border:1px solid var(--border,#d8d4c8);border-radius:6px;padding:4px 12px;font-size:12px;cursor:pointer}
    .lm-full{width:100%;margin-top:10px;font-size:12px;min-height:90px}
  </style>
  <div class="lm-card lm-status" id="lmStatus">加载 provider 状态…</div>
  <div class="lm-card">
    <div class="lm-drop" id="lmDrop">
      <p>📷 点击选择图片，或拖拽图片到此处</p>
      <p class="lm-hint">本地推理（灵眸 PP-OCRv6 或内置引擎），图片不离开本机</p>
      <input type="file" id="lmFile" accept="image/*">
    </div>
    <div class="lm-run"><button class="lm-btn" id="lmRun" disabled>开始识别</button></div>
  </div>
  <div class="lm-card" id="lmResult" style="display:none">
    <div class="lm-result-head">
      <div><span class="lm-badge" id="lmProvider"></span>　<span id="lmMeta" style="font-size:12px;color:var(--muted,#8a8577)"></span></div>
      <button class="lm-copy" id="lmCopy">复制全文</button>
    </div>
    <div class="lm-lines" id="lmLines"></div>
    <textarea class="lm-full" id="lmFull" readonly></textarea>
  </div>
  <div class="lm-card" id="lmGuji" style="display:none">
    <div class="lm-result-head">
      <span>📜 句读标点（甲言 CRF 本地引擎，简体输入最佳；繁体自动转简标点后再转回）</span>
      <span><span class="lm-badge" id="lmGujiState">检查中…</span></span>
    </div>
    <div class="lm-run" style="text-align:left">
      <button class="lm-btn" id="lmGujiBtn" disabled>句读标点</button>
      <button class="lm-btn" id="lmGujiInstall" style="display:none;background:#8a6d3b">安装引擎（约1MB）</button>
    </div>
    <textarea class="lm-full" id="lmGujiOut" readonly style="margin-top:10px;min-height:140px"></textarea>
  </div>
</div>
<script src="/plugin/lingmu-ocr/static/panel.js"></script>
<script>if (window.lingmuPanelInit) window.lingmuPanelInit();</script>
"""


@bp.route("/plugin/lingmu-ocr/page", methods=["GET"])
def page():
    return Response(PAGE_HTML, mimetype="text/html; charset=utf-8")


@bp.route("/api/plugins/lingmu-ocr/status", methods=["GET"])
def status():
    pkg_ok = False
    pkg_err = None
    try:
        import rapidocr  # noqa: F401
        pkg_ok = True
    except Exception as e:
        pkg_err = "%s: %s" % (type(e).__name__, str(e)[:160])
    return jsonify({
        "ok": True,
        "engine": "RapidOCR PP-OCRv6",
        "pkg_available": pkg_ok,
        "error": pkg_err,
        "lazy": True,
    })
