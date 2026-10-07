# -*- coding: utf-8 -*-
"""OCR provider 注册与调度（OCR插件化方案 docs/OCR插件化方案.md）
- discover_ocr_providers(): 扫描插件 manifest capabilities.ocr，导入 ocr_page
- run_ocr(image_path): 按 priority 降序尝试各 provider；全部失败回落内置 v4
- 内置 v4 用 rapidocr_onnxruntime（与历史管线同引擎），未安装则抛 OCRUnavailable
插件 manifest 约定:
  "capabilities": ["ocr"], "ocr": {"priority": 100, "module": "ocr.py:ocr_page"}
"""
import os
import sys
import json
import importlib.util
import traceback

_PROVIDERS = []          # [(pid, priority, callable)]
_DISCOVERED = False


class OCRUnavailable(Exception):
    pass


def _import_ref(pdir, ref, pid):
    fname, var = ref.split(":")
    fpath = os.path.join(pdir, fname)
    spec = importlib.util.spec_from_file_location("jx_ocr_%s" % pid, fpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jx_ocr_%s" % pid] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, var)


def discover_ocr_providers():
    """扫描全部插件目录（用户目录优先，同名覆盖），收集 ocr capability。"""
    global _PROVIDERS, _DISCOVERED
    if _DISCOVERED:
        return list(_PROVIDERS)
    _DISCOVERED = True
    try:
        from plugin_loader import all_plugin_dirs, load_overrides, effective_enabled
    except Exception:
        return []
    overrides = load_overrides()
    seen = set()
    for base in all_plugin_dirs():
        if not os.path.isdir(base):
            continue
        for pid in sorted(os.listdir(base)):
            if pid in seen:
                continue
            seen.add(pid)
            mf = os.path.join(base, pid, "manifest.json")
            if not os.path.isfile(mf):
                continue
            try:
                manifest = json.load(open(mf, encoding="utf-8"))
            except Exception:
                continue
            if not effective_enabled(manifest, pid, overrides):
                continue
            caps = manifest.get("capabilities") or []
            if "ocr" not in caps:
                continue
            oconf = manifest.get("ocr") or {}
            ref = oconf.get("module", "ocr.py:ocr_page")
            try:
                fn = _import_ref(os.path.join(base, pid), ref, pid)
                if not callable(fn):
                    continue
                _PROVIDERS.append((pid, int(oconf.get("priority", 0)), fn))
            except Exception:
                traceback.print_exc()
    _PROVIDERS.sort(key=lambda x: -x[1])
    return list(_PROVIDERS)


def providers_status():
    """供 /api/ocr/providers：注册结果 + 内置兜底可用性。"""
    discover_ocr_providers()
    builtin = False
    try:
        import rapidocr  # noqa: F401
        builtin = True
    except Exception:
        pass
    return {
        "providers": [{"id": p, "priority": pr} for p, pr, _ in _PROVIDERS],
        "builtin": builtin,
    }


def _run_builtin(image_path):
    from rapidocr import RapidOCR
    engine = _run_builtin._engine
    if engine is None:
        engine = RapidOCR()
        _run_builtin._engine = engine
    res = engine(image_path)
    boxes = res.boxes if res.boxes is not None else []
    txts = res.txts if res.txts is not None else []
    scores = res.scores if res.scores is not None else []
    lines = []
    for box, t, c in zip(boxes, txts, scores):
        try:
            flat = [round(float(x), 1) for x in box.flatten().tolist()]
        except Exception:
            flat = []
        lines.append({"box": flat, "text": str(t), "conf": round(float(c), 3)})
    return lines


_run_builtin._engine = None


def run_ocr(image_path):
    """按优先级跑 provider；全败回落内置（rapidocr PP-OCRv6）；均无则抛 OCRUnavailable。"""
    discover_ocr_providers()
    errors = []
    for pid, _pr, fn in _PROVIDERS:
        try:
            return pid, fn(image_path)
        except Exception as e:
            errors.append("%s: %s" % (pid, type(e).__name__))
            traceback.print_exc()
    try:
        return "__builtin__", _run_builtin(image_path)
    except Exception as e:
        errors.append("builtin: %s" % type(e).__name__)
    raise OCRUnavailable("; ".join(errors) or "no ocr provider")


def reset_for_test():
    """测试用：清空注册表允许重新发现。"""
    global _PROVIDERS, _DISCOVERED
    _PROVIDERS = []
    _DISCOVERED = False
