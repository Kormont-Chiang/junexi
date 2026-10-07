# -*- coding: utf-8 -*-
"""六月息装版热替换（等待运行实例退出后执行）
- 等 JuneXi 进程退出（最多等 24h）
- 退出后 3 秒窗口内确认无新实例，robocopy 镜像 dist -> 安装目录
- 成功写 done 标记；失败写 fail 标记（含原因）
"""
import os
import shutil
import subprocess
import sys
import time

SRC = r"C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\dist\JuneXi"
DST = os.path.join(os.environ["LOCALAPPDATA"], r"Programs\JuneXi")
MARK = os.path.join(os.environ["TEMP"], "jx_deploy_result.txt")

def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)

def jx_running():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process JuneXi -ErrorAction SilentlyContinue | Measure-Object).Count"],
        capture_output=True, text=True)
    try:
        return int(out.stdout.strip() or "0") > 0
    except Exception:
        return True

def main():
    log("deploy watcher start; JuneXi running=%s" % jx_running())
    deadline = time.time() + 24 * 3600
    while jx_running() and time.time() < deadline:
        time.sleep(30)
    if jx_running():
        open(MARK, "w").write("fail: timeout, JuneXi still running")
        log("timeout")
        return
    time.sleep(3)
    if jx_running():
        open(MARK, "w").write("fail: JuneXi restarted in swap window")
        log("restarted in window")
        return
    os.makedirs(DST, exist_ok=True)
    r = subprocess.run(
        ["robocopy", SRC, DST, "/MIR", "/NFL", "/NDL", "/NJH", "/R:2", "/W:2"],
        capture_output=True, text=True)
    if r.returncode <= 7:
        open(MARK, "w").write("done: deployed %s" % time.strftime("%Y-%m-%d %H:%M"))
        log("deployed rc=%d" % r.returncode)
    else:
        open(MARK, "w").write("fail: robocopy rc=%d\n%s" % (r.returncode, r.stdout[-800:]))
        log("robocopy fail rc=%d" % r.returncode)

if __name__ == "__main__":
    main()
