# -*- coding: utf-8 -*-
"""纯 ctypes 版工具：进程枚举 + 本地账户锁定检测，全程零弹窗。"""
import ctypes
from ctypes import wintypes

TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def proc_exists(name):
    name = name.lower()
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1).value:
        return False
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    found = False
    try:
        if k32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.split("\x00", 1)[0].lower() == name:
                    found = True
                    break
                if not k32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        k32.CloseHandle(snap)
    return found


UF_LOCKOUT = 0x0010


def user_locked(username):
    """NetUserGetInfo level 3 → usri3_flags 的 UF_LOCKOUT 位。失败返回 None。"""
    netapi32 = ctypes.windll.netapi32
    buf = ctypes.c_void_p()
    rc = netapi32.NetUserGetInfo(None, username, 3, ctypes.byref(buf))
    if rc != 0 or not buf:
        return None
    try:
        # 64 位布局：usri3_flags 在偏移 40（3 指针×8 + 4 DWORD×4）
        flags = ctypes.cast(buf.value + 40, ctypes.POINTER(wintypes.DWORD))[0]
        return bool(flags & UF_LOCKOUT)
    finally:
        netapi32.NetApiBufferFree(buf)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("JuneXi:", proc_exists("JuneXi.exe"))
    print("lenovo locked:", user_locked("lenovo"))
