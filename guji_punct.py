# -*- coding: utf-8 -*-
"""古语文后处理服务：jiayan CRF 断句/标点（本地离线，按需自装）。

两级"数据"分离：
- 引擎（~1MB）：jiayan 纯 python + python-crfsuite wheel + kenlm/sklearn 桩
  → 一键装到 %LOCALAPPDATA%\\JuneXi\\pylib（PyPI 直拉，免 pip，冻结应用可用）
- 模型（数 MB）：cut_model + punc_model
  → 用户自放 %LOCALAPPDATA%\\JuneXi\\jiayan_models\\（官方百度网盘码 p0sc）

kenlm 仅训练特征提取用（推理 PMI/T-test 特征已注释），sklearn 仅 eval 用，
两者皆以桩替代，免 C++ 编译、免 scipy 巨包。
简体-only 边界：繁体输入 OpenCC 转简体标点后再转回。
"""
import io
import json
import os
import sys
import threading
import urllib.request
import zipfile
import tarfile
import tempfile
import shutil

_PINS = {
    "python-crfsuite": "0.9.12",   # cp311 win_amd64 wheel
    "jiayan": "0.0.21",            # sdist 纯 python
}

_lock = threading.Lock()
_install_lock = threading.Lock()
_punctuator = None
_state = {"checked": False, "available": False, "error": None, "models_dir": None}
_install = {"running": False, "done": False, "step": "", "error": None}


def _user_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expandvars(r"%LOCALAPPDATA%"), "JuneXi")


def pylib_dir():
    return os.path.join(_user_dir(), "pylib")


def models_dir():
    return os.path.join(_user_dir(), "jiayan_models")


def _ensure_pylib_on_path():
    p = pylib_dir()
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)


def _write_shims(p):
    """kenlm / sklearn 最小桩：import 期形状齐全，真调用即报错（eval/训练路径）。"""
    with io.open(os.path.join(p, "kenlm.py"), "w", encoding="utf-8") as f:
        f.write(u"class LanguageModel:\n"
                u"    def __init__(self, *a, **k):\n"
                u"        raise RuntimeError('kenlm C++ ext unavailable (stub)')\n")
    sk = os.path.join(p, "sklearn")
    os.makedirs(sk, exist_ok=True)
    with io.open(os.path.join(sk, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(u"")
    with io.open(os.path.join(sk, "metrics.py"), "w", encoding="utf-8") as f:
        f.write(u"def classification_report(*a, **k):\n"
                u"    raise RuntimeError('sklearn stub: eval only')\n")
    with io.open(os.path.join(sk, "preprocessing.py"), "w", encoding="utf-8") as f:
        f.write(u"class LabelBinarizer:\n"
                u"    def __init__(self, *a, **k):\n"
                u"        raise RuntimeError('sklearn stub: eval only')\n")


def _pypi_fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "JuneXi-guji/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _fetch_release_files(pkg):
    meta_url = "https://pypi.org/pypi/%s/%s/json" % (pkg, _PINS[pkg])
    with urllib.request.urlopen(urllib.request.Request(meta_url, headers={"User-Agent": "JuneXi-guji/0.1"}), timeout=60) as r:
        meta = json.load(r)
    return meta["urls"]


def _step(msg):
    _install["step"] = msg


def install_engine():
    """后台线程：下载 jiayan 链到 pylib。返回启动是否成功（重复调用拒绝）。"""
    with _install_lock:
        if _install["running"]:
            return False
        _install.update(running=True, done=False, step="init", error=None)

    def work():
        tmp = tempfile.mkdtemp(prefix="jx_guji_")
        try:
            p = pylib_dir()
            os.makedirs(p, exist_ok=True)
            # 1) python-crfsuite wheel（二进制，挑 cp311 win_amd64）
            _step(u"查 python-crfsuite wheel…")
            files = _fetch_release_files("python-crfsuite")
            wheel = None
            for u in files:
                fn = u["filename"]
                if fn.endswith(".whl") and "cp311" in fn and "win_amd64" in fn:
                    wheel = u
                    break
            if not wheel:
                raise RuntimeError("no cp311 win_amd64 wheel for python-crfsuite")
            _step(u"下载 python-crfsuite…")
            wpath = os.path.join(tmp, wheel["filename"])
            _pypi_fetch(wheel["url"], wpath)
            _step(u"解压 python-crfsuite…")
            with zipfile.ZipFile(wpath) as z:
                z.extractall(p)
            # 2) jiayan sdist（纯 python）
            _step(u"查 jiayan sdist…")
            files = _fetch_release_files("jiayan")
            sdist = next((u for u in files if u["filename"].endswith(".tar.gz")), None)
            if not sdist:
                raise RuntimeError("no sdist for jiayan")
            _step(u"下载 jiayan…")
            spath = os.path.join(tmp, sdist["filename"])
            _pypi_fetch(sdist["url"], spath)
            _step(u"解压 jiayan…")
            with tarfile.open(spath) as t:
                for m in t.getmembers():
                    parts = m.name.split("/")
                    if len(parts) >= 2 and parts[1] == "jiayan":
                        m.name = "/".join(parts[1:])
                        t.extract(m, p, filter="data")
            # 3) 桩
            _step(u"写 kenlm/sklearn 桩…")
            _write_shims(p)
            _step(u"完成")
            _install.update(running=False, done=True)
        except Exception as e:
            _install.update(running=False, done=True, error="%s: %s" % (type(e).__name__, str(e)[:200]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    threading.Thread(target=work, daemon=True).start()
    return True


def _try_load():
    global _punctuator
    if _state["checked"]:
        return
    _state["checked"] = True
    _state["models_dir"] = models_dir()
    _ensure_pylib_on_path()
    try:
        import jiayan  # noqa: F401
    except Exception as e:
        _state["error"] = "engine not installed: %s: %s" % (type(e).__name__, str(e)[:120])
        return
    cut = os.path.join(models_dir(), "cut_model")
    punc = os.path.join(models_dir(), "punc_model")
    if not (os.path.isfile(cut) and os.path.isfile(punc)):
        _state["error"] = "models missing (cut_model + punc_model -> %s)" % models_dir()
        return
    try:
        from jiayan import CRFPunctuator
        pp = CRFPunctuator(None, cut)   # lm 仅训练期用，推理不触
        pp.load(punc)
        # 推理特征里 sentencizer 的 pmi/ttest 是活跃行（训练期喂真值），kenlm 缺席
        # → 返回训练分布外的 'NA'：CRF 对未登录特征值不触发，等效降权该特征，
        #    优于喂错误桶值（'0' 桶是有语义的 pmi<1，会主动误导）
        for obj in (pp, pp.sentencizer):
            obj.get_pmi = lambda seg: u"NA"
            obj.get_ttest = lambda seg: u"NA"
        _punctuator = pp
        _state["available"] = True
        _state["error"] = None
    except Exception as e:
        _state["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])


def status():
    with _lock:
        _ensure_pylib_on_path()
        _try_load()
        st = "ready" if _state["available"] else ("no_models" if _state["error"] and "models missing" in _state["error"] else ("not_installed" if _state["error"] and "not installed" in _state["error"] else "error"))
        return {
            "ok": True,
            "state": st,
            "available": _state["available"],
            "models_dir": _state["models_dir"],
            "pylib": pylib_dir(),
            "error": _state["error"],
            "install": dict(_install),
        }


def _looks_traditional(text):
    sample = text[:600]
    if not sample:
        return False
    # 只数「简繁形体不同」的繁体特征字；之也亦其者所焉等经学常字两体同形，勿入表
    marks = u"與為於無萬經書國學縣關門問聞間開陳陸陰陽雲車馬龍鳥魚讓認識話說讀寫舊時書畫點線練習組織結構緣故縱橫緊急緩慢繼續維持綱領辭職辯論農業這邊逝世適應選舉遺址遺憾遺跡遺產遺體迴避遮擋轟動轉變輪流辭典亂賢聖體聲學發龍鳳麼麽台臺灣廣東西醫藥處備單雙嚴喪"
    return sum(1 for ch in sample if ch in marks) >= 2


def punctuate_text(text):
    """文言文本 → 标点文本。未就绪抛 RuntimeError（面板转为提示）。"""
    with _lock:
        _ensure_pylib_on_path()
        _try_load()
        if not _punctuator:
            raise RuntimeError("guji not ready: %s" % _state["error"])
        from opencc import OpenCC
        trad = _looks_traditional(text)
        src = OpenCC("t2s").convert(text) if trad else text
        out = _punctuator.punctuate(src)
        return (OpenCC("s2t").convert(out) if trad else out), trad


def reset_for_test():
    """测试用：清状态强制重检。"""
    global _punctuator
    with _lock:
        _state.update(checked=False, available=False, error=None)
        _punctuator = None
