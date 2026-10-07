# -*- coding: utf-8 -*-
"""百度 OCR provider（云端选配）。
未配置 key 时 ocr_page 抛异常 → 核心回落链继续；
配置经 /api/plugins/baidu-ocr/config 存用户数据目录（不进仓库、不进 git）。
token 缓存按 api_key 分桶，换 key 天然失效，无需手动清。
"""
import base64
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

_TOKENS = {}  # api_key -> {"value":..., "exp":...}


def _user_dir():
    return os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "JuneXi")


def _conf_path():
    return os.path.join(_user_dir(), "baidu_ocr.json")


def load_config():
    try:
        with open(_conf_path(), encoding="utf-8") as f:
            d = json.load(f)
        return {"api_key": d.get("api_key", ""), "secret_key": d.get("secret_key", "")}
    except Exception:
        return {"api_key": "", "secret_key": ""}


def save_config(api_key, secret_key):
    os.makedirs(_user_dir(), exist_ok=True)
    with open(_conf_path(), "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key, "secret_key": secret_key}, f, ensure_ascii=False)


def _get_token(api_key, secret_key):
    bucket = _TOKENS.setdefault(hashlib.md5(api_key.encode("utf-8")).hexdigest(), {})
    now = time.time()
    if bucket.get("value") and now < bucket.get("exp", 0):
        return bucket["value"]
    url = ("https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials"
           "&client_id=%s&client_secret=%s" % (urllib.parse.quote(api_key), urllib.parse.quote(secret_key)))
    with urllib.request.urlopen(url, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
    if "access_token" not in d:
        raise RuntimeError("baidu token error: %s" % str(d)[:120])
    bucket["value"] = d["access_token"]
    bucket["exp"] = now + max(0, int(d.get("expires_in", 2592000))) - 600
    return bucket["value"]


def ocr_page(image_path):
    cfg = load_config()
    if not cfg["api_key"] or not cfg["secret_key"]:
        raise RuntimeError("baidu-ocr: not configured (set keys via /api/plugins/baidu-ocr/config)")
    token = _get_token(cfg["api_key"], cfg["secret_key"])
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    body = urllib.parse.urlencode({"image": b64}).encode("utf-8")
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate?access_token=" + urllib.parse.quote(token)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    if "words_result" not in d:
        raise RuntimeError("baidu ocr error: %s" % str(d)[:120])
    out = []
    for w in d["words_result"]:
        loc = (w.get("location") or {})
        box = [[loc.get("left", 0), loc.get("top", 0)],
               [loc.get("left", 0) + loc.get("width", 0), loc.get("top", 0)],
               [loc.get("left", 0) + loc.get("width", 0), loc.get("top", 0) + loc.get("height", 0)],
               [loc.get("left", 0), loc.get("top", 0) + loc.get("height", 0)]] if loc else None
        out.append({"box": box, "text": w.get("words", ""), "conf": (w.get("probability", {}) or {}).get("average")})
    return out
