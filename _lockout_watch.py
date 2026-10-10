# -*- coding: utf-8 -*-
"""账户锁定状态哨兵 v2：纯 ctypes 轮询，零弹窗。"""
import time, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _winutil import user_locked

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lockout_watch.log")


def main():
    last = None
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("=== watch v2 start %s ===\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        f.flush()
        while True:
            now = user_locked("lenovo")
            if now is None:
                now = "?"
            if now != last:
                f.write("%s  locked=%s\n" % (time.strftime("%H:%M:%S"), now))
                f.flush()
                last = now
            time.sleep(45)


if __name__ == "__main__":
    main()
