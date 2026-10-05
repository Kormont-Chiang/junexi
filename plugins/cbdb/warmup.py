# -*- coding: utf-8 -*-
"""CBDB 预热: 后台线程建连接+坐标缓存(原 app.py 预热段迁入)。"""
import os


def _cbdb_warmup():
    """后台预热：冷启动后首个 CBDB 查询要 ~79s（Access 打开 613MB mdb 冷文件 +
    坐标缓存全量加载）。失败不影响使用（首个查询按需加载）。"""
    import time as _time
    import importlib
    _mod = importlib.import_module("jx_plugin_cbdb")
    CBDBConnection = _mod.CBDBConnection
    try:
        t0 = _time.time()
        conn = CBDBConnection.get_conn()
        if not conn:
            print("[warmup] CBDB 连接失败，跳过预热", flush=True)
            return
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ADDR_CODES")
        cur.fetchone()
        CBDBConnection._addr_coords()
        print(f"[warmup] CBDB 预热完成（连接 + 坐标缓存，{_time.time() - t0:.1f}s）", flush=True)
    except Exception as e:
        print(f"[warmup] CBDB 预热失败（不影响使用）: {e}", flush=True)


def run(app=None):
    """manifest warmup 钩子: 模块级线程预热(与 app 启动重叠)。"""
    import threading
    if os.environ.get("WERKZEUG_RUN_MAIN") in (None, "true"):
        threading.Thread(target=_cbdb_warmup, daemon=True).start()
