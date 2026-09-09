# -*- coding: utf-8 -*-
"""托盘诊断脚本：逐步执行 RegisterClassW / CreateWindowExW / Shell_NotifyIcon 并输出错误码。"""
import ctypes
import sys
from ctypes import wintypes

U = ctypes.WinDLL("user32", use_last_error=True)
S = ctypes.WinDLL("shell32", use_last_error=True)
K = ctypes.WinDLL("kernel32", use_last_error=True)
K.SetLastError(0)


def gerr(tag):
    code = ctypes.get_last_error()
    print("[{}] GetLastError = {} (0x{:08X})".format(tag, code, code))
    return code


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


def wnd_proc(hwnd, msg, wp, lp):
    return U.DefWindowProcW(hwnd, msg, wp, lp)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
    ]


print("python:", sys.executable)
hinst = K.GetModuleHandleW(None)
print("hInstance =", hinst)

cls = WNDCLASSW()
cls.lpfnWndProc = WNDPROC(wnd_proc)
cls.hInstance = hinst
cls.lpszClassName = "ScTrayDiagWnd"
atom = U.RegisterClassW(ctypes.byref(cls))
print("RegisterClassW atom =", atom)
gerr("RegisterClassW")

hwnd = U.CreateWindowExW(0, "ScTrayDiagWnd", "ScTray", 0, 0, 0, 0, 0, 0, 0, hinst, 0)
print("CreateWindowExW hwnd =", hwnd)
gerr("CreateWindowExW")
if not hwnd:
    sys.exit(1)

# 图标（对桌面 SecondClass.exe 提取）—— ExtractIconExW 在 shell32！
target = os.path.expandvars(r"%USERPROFILE%\Desktop\SecondClass.exe")
if not os.path.exists(target):
    target = sys.executable
print("图标来源:", target)
big = wintypes.HICON()
small = wintypes.HICON()
ok = S.ExtractIconExW(target, 0, ctypes.byref(big), ctypes.byref(small), 1)
print("ExtractIconExW 返回 =", ok, "| big =", big.value, "| small =", small.value)
gerr("ExtractIconExW")

nid = NOTIFYICONDATAW()
nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
nid.hWnd = hwnd
nid.uID = 1
nid.uFlags = 0x1 | 0x2 | 0x4  # MESSAGE|ICON|TIP
nid.uCallbackMessage = 0x8000 + 1
nid.hIcon = big.value or small.value
nid.szTip = "SecondClass 托盘诊断"
added = S.Shell_NotifyIconW(0, ctypes.byref(nid))  # NIM_ADD
print("Shell_NotifyIconW(NIM_ADD) =", added)
gerr("NIM_ADD")

import time
print("已添加（约 3 秒后清理）……")
time.sleep(3)
removed = S.Shell_NotifyIconW(2, ctypes.byref(nid))  # NIM_DELETE
print("NIM_DELETE =", removed)
print("诊断完成。")
