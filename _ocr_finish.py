# -*- coding: utf-8 -*-
"""OCR 完工一键流水线：同步脚本→解析→清洗(--full 直入 repo)→召回复测→报告
用法：venv\\python _ocr_finish.py        （在 repo 根跑）
"""
import sys, os, shutil, subprocess, time
sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "references", "toolbooks")
PY = os.path.join(BASE, "venv", "Scripts", "python.exe")

def run(name, args, env_extra=None, cwd=None):
    env = dict(os.environ)
    env["DIMING_DATA"] = DATA
    env["DIMING_REPO"] = BASE
    if env_extra:
        env.update(env_extra)
    env["PYTHONIOENCODING"] = "utf-8"
    print("=== %s ===" % name)
    t0 = time.time()
    r = subprocess.run([PY] + args, cwd=cwd or BASE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode("utf-8", "replace")
    tail = "\n".join(out.strip().splitlines()[-25:])
    print(tail)
    print("--- exit %d, %.1fs ---" % (r.returncode, time.time() - t0))
    return r.returncode == 0, out

# 1) 同步 repo 脚本到数据目录（运行时副本；parse_diming 另存无下划线版供 recall import）
for fn in ("parse_diming.py", "clean_diming.py", "recall_v3.py", "miss_attr.py"):
    shutil.copy2(os.path.join(BASE, "tooling", "diming", fn),
                 os.path.join(DATA, "_" + fn))
shutil.copy2(os.path.join(BASE, "tooling", "diming", "parse_diming.py"),
             os.path.join(DATA, "parse_diming.py"))
print("scripts synced to", DATA)

ok1, _ = run(u"解析 parse_diming", [os.path.join(DATA, "_parse_diming.py")])
ok2, _ = run(u"清洗 clean_diming --full", [os.path.join(DATA, "_clean_diming.py"), "--full"])
ok3, out3 = run(u"召回复测 recall_v3", [os.path.join(DATA, "_recall_v3.py")], cwd=DATA)

dst = os.path.join(BASE, "data", "toolbooks", "diming_clean.jsonl")
n = 0
if os.path.isfile(dst):
    with open(dst, encoding="utf-8") as f:
        n = sum(1 for _ in f)
print(u"\n===== 汇总 =====")
print(u"diming_clean.jsonl 条数：%d" % n)
print(u"召回测试输出尾部已见上")
print(u"入包路径：%s" % dst)
print(u"RESULT %s" % ("OK" if (ok1 and ok2 and ok3 and n > 50000) else "CHECK"))
