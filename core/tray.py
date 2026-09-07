# -*- coding: utf-8 -*-
"""系统托盘（ctypes 直调 Shell_NotifyIcon，零第三方依赖，仅 Windows）。

对外接口：
    TrayIcon(on_command, tooltip) -> start() / stop() / set_tooltip()
    on_command(cmd) 为回调 cmd in ("open", "start", "toggle_auto", "quit")，
    从托盘消息线程调用（线程安全处理由调用方负责，如转发到主线程队列）。

关键点：所有 Win32 API 均显式声明 argtypes/restype —— ARM64/x64 下句柄为
64 位，缺失声明会被当作 32 位参数导致溢出（CreateWindowExW 失败/回调异常）。
"""
import ctypes
import os
import sys
import threading
from ctypes import wintypes

USER32 = ctypes.WinDLL("user32", use_last_error=True)
SHELL32 = ctypes.WinDLL("shell32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

# 常量
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
TPM_RETURNCMD = 0x0100
MF_STRING = 0x0
CMD_OPEN, CMD_START, CMD_AUTO, CMD_QUIT = 1, 2, 3, 4
WM_QUIT = 0x0012
WM_TRAY_STOP = WM_APP + 2

AVAILABLE = sys.platform == "win32"


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeout", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


# ---------- Win32 签名声明（64 位安全） ----------

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


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


USER32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
USER32.RegisterClassW.restype = wintypes.ATOM
USER32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
USER32.CreateWindowExW.restype = wintypes.HWND
USER32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
USER32.DefWindowProcW.restype = ctypes.c_ssize_t
USER32.DestroyWindow.argtypes = [wintypes.HWND]
USER32.DestroyWindow.restype = wintypes.BOOL
USER32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
USER32.GetMessageW.restype = ctypes.c_ssize_t
USER32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
USER32.TranslateMessage.restype = wintypes.BOOL
USER32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
USER32.DispatchMessageW.restype = ctypes.c_ssize_t
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
USER32.PostMessageW.restype = wintypes.BOOL
USER32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
USER32.GetCursorPos.restype = wintypes.BOOL
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.SetForegroundWindow.restype = wintypes.BOOL
USER32.CreatePopupMenu.restype = wintypes.HMENU
USER32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t,
                               wintypes.LPCWSTR]
USER32.AppendMenuW.restype = wintypes.BOOL
USER32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                  ctypes.c_void_p]
USER32.TrackPopupMenu.restype = wintypes.UINT
USER32.DestroyMenu.argtypes = [wintypes.HMENU]
USER32.DestroyMenu.restype = wintypes.BOOL
USER32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
USER32.LoadImageW.restype = wintypes.HICON

SHELL32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                      ctypes.POINTER(NOTIFYICONDATAW)]
SHELL32.Shell_NotifyIconW.restype = wintypes.BOOL
SHELL32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                   ctypes.POINTER(wintypes.HICON),
                                   ctypes.POINTER(wintypes.HICON),
                                   wintypes.UINT]
SHELL32.ExtractIconExW.restype = wintypes.UINT

KERNEL32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
KERNEL32.GetModuleHandleW.restype = wintypes.HINSTANCE


# ---------- 纯逻辑（可单测） ----------
MENU_ITEMS = (
    (CMD_OPEN, "打开主窗口"),
    (CMD_START, "开始刷题"),
    (CMD_AUTO, "每日自动：切换开关"),
    (CMD_QUIT, "退出 SecondClass"),
)


def command_for_id(cmd_id: int) -> str | None:
    return {CMD_OPEN: "open", CMD_START: "start",
            CMD_AUTO: "toggle_auto", CMD_QUIT: "quit"}.get(cmd_id)


def icon_source() -> str:
    """返回托盘图标来源（frozen=exe 自身；源码=assets/app.ico）。"""
    if getattr(sys, "frozen", False):
        return sys.executable
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", "app.ico")


class TrayIcon:
    """托盘图标（仅 Windows；其它平台 AVAILABLE=False，start/stop 均安全）。"""

    def __init__(self, on_command=None, tooltip: str = "SecondClass"):
        self.on_command = on_command or (lambda cmd: None)
        self.tooltip = tooltip
        self._hwnd = 0
        self._wndproc = None  # 保持引用防 GC
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._msg = wintypes.MSG()
        self._hicon = 0
        self.last_error = ""

    # ---------- 生命周期 ----------

    def start(self) -> bool:
        if not AVAILABLE:
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._started.clear()
        t = threading.Thread(target=self._run, name="tray", daemon=True)
        t.start()
        if not self._started.wait(timeout=5):
            return False
        return self._hwnd != 0

    def stop(self):
        if not AVAILABLE or not self._hwnd:
            return
        try:
            nid = self._make_nid()
            SHELL32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        except Exception:
            pass
        try:
            USER32.PostMessageW(self._hwnd, WM_TRAY_STOP, 0, 0)
        except Exception:
            pass
        self._hwnd = 0

    def set_tooltip(self, tip: str):
        self.tooltip = tip
        if AVAILABLE and self._hwnd:
            try:
                nid = self._make_nid()
                SHELL32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
            except Exception:
                pass

    # ---------- 内部 ----------

    def _make_nid(self) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        nid.szTip = self.tooltip[:127]
        return nid

    def _load_icon(self):
        src = icon_source()
        try:
            if src.lower().endswith(".exe"):
                big = wintypes.HICON()
                small = wintypes.HICON()
                SHELL32.ExtractIconExW(src, 0, ctypes.byref(big),
                                       ctypes.byref(small), 1)
                self._hicon = big.value or small.value
            else:
                self._hicon = USER32.LoadImageW(
                    None, src, 1, 32, 32, 0x10)  # IMAGE_ICON | LR_LOADFROMFILE
            self._hicon = self._hicon or 0
        except Exception:
            self._hicon = 0

    def _run(self):
        try:
            hinst = KERNEL32.GetModuleHandleW(None)
            self._wndproc = WNDPROC(self._wnd_proc)
            cls = WNDCLASSW()
            cls.lpfnWndProc = self._wndproc
            cls.hInstance = hinst
            cls.lpszClassName = "SecondClassTrayWnd"
            if not USER32.RegisterClassW(ctypes.byref(cls)):
                self.last_error = "RegisterClassW 失败"
                self._started.set()
                return
            self._hwnd = USER32.CreateWindowExW(
                0, "SecondClassTrayWnd", "SecondClass", 0,
                0, 0, 0, 0, 0, 0, hinst, 0)
            if not self._hwnd:
                self.last_error = "CreateWindowExW 失败"
                self._started.set()
                return
            self._load_icon()
            nid = self._make_nid()
            if not SHELL32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
                self.last_error = "Shell_NotifyIconW(NIM_ADD) 失败"
            self._started.set()
            if self.last_error:
                return  # 无法管理图标，结束线程
            self._msg_loop()
        except Exception as e:
            self.last_error = repr(e)
            self._started.set()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            evt = lparam & 0xFFFF
            if evt == WM_RBUTTONUP:
                self._show_menu()
            elif evt == WM_LBUTTONUP:
                self.on_command("open")
        elif msg == WM_TRAY_STOP:
            USER32.PostQuitMessage(0)
            return 0
        return USER32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self):
        try:
            menu = USER32.CreatePopupMenu()
            for cid, label in MENU_ITEMS:
                USER32.AppendMenuW(menu, MF_STRING, cid, label)
            pt = wintypes.POINT()
            USER32.GetCursorPos(ctypes.byref(pt))
            USER32.SetForegroundWindow(self._hwnd)  # TrackPopupMenu 需要前台
            sel = USER32.TrackPopupMenu(menu, TPM_RETURNCMD,
                                        pt.x, pt.y, 0, self._hwnd, None)
            cmd = command_for_id(sel)
            if cmd:
                self.on_command(cmd)
            USER32.DestroyMenu(menu)
        except Exception:
            pass

    def _msg_loop(self):
        while True:
            ret = USER32.GetMessageW(ctypes.byref(self._msg), 0, 0, 0)
            if ret == 0 or ret == -1:
                break
            USER32.TranslateMessage(ctypes.byref(self._msg))
            USER32.DispatchMessageW(ctypes.byref(self._msg))
        try:
            USER32.DestroyWindow(self._hwnd)
        except Exception:
            pass
        self._hwnd = 0
