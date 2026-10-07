# -*- coding: utf-8 -*-
"""启动预热示例：manifest "warmup": "warmup.py:run" 时启动即执行。
放预连接/缓存预热等一次性工作；保持幂等，失败不致命（加载器会记日志跳过）。
"""


def run():
    import sys
    m = sys.modules.get("app")
    log = getattr(m, "_log_activity", None) if m else None
    if log:
        log("plugin", "my-plugin 预热完成")
