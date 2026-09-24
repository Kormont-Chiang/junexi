#!/usr/bin/env python3
"""
六月息 · 桌面版启动器
双击即开：自动启动本地服务并打开原生窗口，无需手动开浏览器。
"""
import os
import sys
import time
import socket
import ctypes
import threading
import traceback

def _bundle_dir() -> str:
    """模板/静态资源所在目录（PyInstaller 打包后指向 _internal）。"""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _writable_dir() -> str:
    """日志/用户数据目录：开发期在项目内，安装版在 %LOCALAPPDATA%\\JuneXi。"""
    if getattr(sys, "frozen", False):
        d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JuneXi")
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d


BASE_DIR = _bundle_dir()
os.chdir(_writable_dir())  # 确保 .env、桌面日志落在可写目录
LOG_FILE = os.path.join(_writable_dir(), "desktop.log")
APP_TITLE = "六月息 · 历史学学术工作台"


def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_server(url: str, timeout: float = 15.0) -> bool:
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url + "/", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.15)
    return False


def main():
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "JuneXi.SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log("已有实例在运行，本次启动退出")
        return
    log("===== 启动 =====")
    from app import app  # Flask 实例（加载 .env、路由、CBDB 配置）

    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    server.start()
    log(f"服务线程已启动: {url}")

    if not wait_for_server(url, timeout=15):
        log("错误：服务 15 秒内未就绪")
        raise RuntimeError("服务启动超时")

    import webview
    log("打开窗口…")
    webview.create_window(
        APP_TITLE,
        url,
        width=1440,
        height=900,
        min_size=(1024, 640),
    )
    webview.start()
    log("窗口已关闭，退出")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("启动失败:\n" + traceback.format_exc())
        sys.exit(1)
