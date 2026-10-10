# -*- coding: utf-8 -*-
"""六月息装版常驻热替换 watcher（持久版）：
- 等 JuneXi 退出后，仅当 dist 的 JuneXi.exe 比上次换过的更新才 robocopy 镜像
- 换完继续待命（下一轮构建+下一次退出自动再换），7 天无事件自毁
- 结果写 %TEMP%\\jx_deploy_result.txt
"""
import os
import subprocess
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _winutil import proc_exists  # 纯 ctypes，零弹窗

SRC = r"C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\dist\JuneXi"
DST = os.path.join(os.environ["LOCALAPPDATA"], r"Programs\JuneXi")
MARK = os.path.join(os.environ["TEMP"], "jx_deploy_result.txt")


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def jx_running():
    try:
        return proc_exists("JuneXi.exe")
    except Exception:
        return True


def src_mtime():
    try:
        return os.path.getmtime(os.path.join(SRC, "JuneXi.exe"))
    except Exception:
        return 0.0


def swap():
    os.makedirs(DST, exist_ok=True)
    r = subprocess.run(
        ["robocopy", SRC, DST, "/MIR", "/NFL", "/NDL", "/NJH", "/R:3", "/W:3"],
        capture_output=True, text=True)
    return r.returncode


def main():
    last = 0.0
    log("persistent deploy watcher start; JuneXi running=%s" % jx_running())
    life = time.time() + 7 * 24 * 3600
    while time.time() < life:
        # 等一次"运行中→退出"的完整周期
        saw = jx_running()
        while jx_running() and time.time() < life:
            saw = True
            time.sleep(20)
        if jx_running():
            break
        if not saw:
            # 没在运行：dist 有更新就直接换
            pass
        time.sleep(3)
        if jx_running():
            log("restarted in swap window, abort this round")
            continue
        mt = src_mtime()
        if mt <= last:
            time.sleep(30)
            continue
        rc = swap()
        if rc <= 7:
            last = mt
            open(MARK, "w", encoding="utf-8").write(
                "done: deployed %s (rc=%d)" % (time.strftime("%Y-%m-%d %H:%M"), rc))
            log("deployed rc=%d" % rc)
        else:
            open(MARK, "w", encoding="utf-8").write("fail: robocopy rc=%d" % rc)
            log("robocopy fail rc=%d" % rc)
            time.sleep(120)
    open(MARK, "a", encoding="utf-8").write("\nwatcher exit %s" % time.strftime("%H:%M:%S"))
    log("watcher exit")


if __name__ == "__main__":
    main()
