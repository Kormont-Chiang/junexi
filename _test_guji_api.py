# -*- coding: utf-8 -*-
"""句读服务回归 v2：状态机（dev 环境 jiayan 已装）/ toy 模型（绕 kenlm 训练特征）/ 端点"""
import sys, os, json, tempfile, shutil
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("PASS" if ok else "FAIL"), label, extra)
    fails += 0 if ok else 1

fake = tempfile.mkdtemp(prefix="jx_guji_test_")
os.environ["LOCALAPPDATA"] = fake

import guji_punct
guji_punct.reset_for_test()

# 1) dev 环境 jiayan 已装 → 状态 no_models（模型缺席）
st = guji_punct.status()
check("state no_models", st["state"] == "no_models", st["state"])

# 2) 未就绪标点 → RuntimeError
try:
    guji_punct.punctuate_text(u"天下大乱")
    check("punctuate raises", False)
except RuntimeError:
    check("punctuate raises", True)

# 3) toy 模型：训练时 pmi/ttest 特征打桩（kenlm C++ 无编译，推理路径不触）
mdir = os.path.join(fake, "JuneXi", "jiayan_models")
os.makedirs(mdir)
from jiayan import CRFSentencizer, CRFPunctuator

sent_train = u"天下大乱，贤圣不明，道德不一，天下多得一察焉以自好，譬如耳目，皆有所明，不能相通，犹百家众技也，皆有所长，时有所用，虽然，不该不遍，一之士也，判天地之美，析万物之理，察古人之全，寡能备于天地之美，称神之容，是故内圣外王之道，暗而不明，郁而不发，天下之人各为其所欲焉以自为方，悲夫，百家往而不反，必不合矣，后世之学者，不幸不见天地之纯，古之大体，道术将为天下裂"

cut_lines = []
for seg in sent_train.replace(u"。", u"，").split(u"，"):
    seg = seg.strip()
    if not seg:
        continue
    cs = list(seg)
    tags = [u"M"] * len(cs)
    tags[0] = u"B"
    tags[-1] = u"E"
    cut_lines.append(u" ".join(u"%s %s" % (c, t) for c, t in zip(cs, tags)))
cut_path = os.path.join(fake, "cut_train.txt")
open(cut_path, "w", encoding="utf-8").write(u"\n".join(cut_lines))

def _parse_tagged(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        chars, tags = parts[::2], parts[1::2]
        rows.append((u"".join(chars), tags))
    return rows

cut_rows = _parse_tagged(cut_path)
s = CRFSentencizer(None)
s.get_pmi = lambda seg: u"0"
s.get_ttest = lambda seg: u"0"
X = [s.sent2features(sent, tags) for sent, tags in cut_rows]
Y = [tags for _, tags in cut_rows]
trained_cut = False
try:
    CRFSentencizer.train(s, X, Y, os.path.join(mdir, "cut_model"))
    trained_cut = os.path.isfile(os.path.join(mdir, "cut_model"))
except Exception as e:
    print("cut train err:", e)
check("cut model trained", trained_cut)

punc_ok = False
if trained_cut:
    p = CRFPunctuator(None, os.path.join(mdir, "cut_model"))
    p.get_pmi = lambda seg: u"0"
    p.get_ttest = lambda seg: u"0"
    XP = [p.sent2features(sent, tags) for sent, tags in cut_rows]
    YP = [[u"D" if t == u"E" else u"O" for t in tags] for _, tags in cut_rows]
    try:
        CRFPunctuator.train(p, XP, YP, os.path.join(mdir, "punc_model"))
        punc_ok = os.path.isfile(os.path.join(mdir, "punc_model"))
    except Exception as e:
        print("punc train err:", e)
check("punc model trained", punc_ok)

# 4) 全链：模型在位 → ready → punctuate（含繁体检出）
guji_punct.reset_for_test()
st2 = guji_punct.status()
check("state ready", st2["state"] == "ready", st2["state"] + " " + str(st2["error"]))
if st2["state"] == "ready":
    out, trad = guji_punct.punctuate_text(u"天下大乱贤圣不明道德不一")
    check("punctuate runs", isinstance(out, str) and any(p in out for p in u"，。！？"), out[:40])
    out2, trad2 = guji_punct.punctuate_text(u"天下大亂賢聖不明道德不一")
    check("traditional detected", trad2 is True, out2[:30])
else:
    check("punctuate runs", False, "chain blocked")

# 5) 端点
from app import app
c = app.test_client()
r = c.get("/api/guji/status")
check("endpoint status", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/api/guji/punctuate", data=json.dumps({"text": u"天下大乱"}), content_type="application/json")
check("endpoint punctuate", r.status_code in (200, 503), str(r.status_code))
r = c.post("/api/guji/punctuate", data=json.dumps({"text": ""}), content_type="application/json")
check("endpoint empty 400", r.status_code == 400)

shutil.rmtree(fake, ignore_errors=True)
sys.exit(1 if fails else 0)
