# -*- coding: utf-8 -*-
"""真实走一遍 guji_punct.install_engine()：PyPI 直拉 → pylib → 状态翻 no_models"""
import sys, os, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 用真实 LOCALAPPDATA（不动 fake）——这会真装到本机 JuneXi\pylib
import guji_punct
print("pylib =", guji_punct.pylib_dir())
st = guji_punct.status()
print("before:", st["state"], st["error"])

started = guji_punct.install_engine()
print("install started:", started)
t0 = time.time()
while True:
    time.sleep(2)
    s = guji_punct.status()
    ins = s["install"]
    if ins.get("running"):
        print("  [%5.1fs] %s" % (time.time() - t0, ins.get("step", "")))
        continue
    print("install done in %.1fs error=%s" % (time.time() - t0, ins.get("error")))
    break

guji_punct.reset_for_test()
st2 = guji_punct.status()
print("after:", st2["state"], "| models_dir =", st2["models_dir"])

# pylib 内容盘点
p = guji_punct.pylib_dir()
for root, dirs, files in os.walk(p):
    depth = root[len(p):].count(os.sep)
    if depth <= 1:
        for d in dirs:
            if d.endswith(".dist-info"):
                print("pkg:", d)
print("kenlm.py shim:", os.path.isfile(os.path.join(p, "kenlm.py")))
print("sklearn shim:", os.path.isdir(os.path.join(p, "sklearn")))
try:
    import pycrfsuite
    print("pycrfsuite import ok (from pylib on sys.path)" )
except Exception as e:
    print("pycrfsuite import FAIL:", e)
