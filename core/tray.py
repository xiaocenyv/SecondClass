# -*- coding: utf-8 -*-
"""系统托盘（ctypes 直调 Shell_NotifyIcon，零第三方依赖，仅 Windows）。

对外接口：
    TrayIcon(on_command, tooltip) -> start() / stop() / set_tooltip()
    on_command(cmd) 为回调 cmd in ("open", "start", "toggle_auto", "quit")，
    从托盘消息线程调用（线程安全处理由调用方负责，如转发到主线程队列）。
"""
import ctypes
import os
import sys
import threading
from ctypes import wintypes

USER32 = ctypes.windll.user32
SHELL32 = ctypes.windll.shell32

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
    """托盘图标（仅 Windows；其它平台 AVAILABLE=False，stop/start 均安全）。"""

    def __init__(self, on_command=None, tooltip: str = "SecondClass"):
        self.on_command = on_command or (lambda cmd: None)
        self.tooltip = tooltip
        self._hwnd = 0
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._msg = ctypes.wintypes.MSG()
        self._hicon = 0

    # ---------- 生命周期 ----------

    def start(self):
        if not AVAILABLE:
            return False
        if self._thread and self._thread.is_alive():
            return True
        t = threading.Thread(target=self._run, name="tray", daemon=True)
        t.start()
        self._started.wait(timeout=5)
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
            USER32.PostMessageW(self._hwnd, WM_APP + 2, 0, 0)  # 退出循环
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
                USER32.ExtractIconExW(src, 0, ctypes.byref(big), ctypes.byref(small), 1)
                self._hicon = big.value or small.value
            else:
                self._hicon = USER32.LoadImageW(0, src, 1, 32, 32, 0x10)  # IMAGE_ICON | LR_LOADFROMFILE
        except Exception:
            self._hicon = 0

    def _run(self):
        # 注册窗口类并创建隐藏消息窗口
        cls = wintypes.WNDCLASSW()
        cls.lpfnWndProc = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM)(self._wnd_proc)
        cls.lpszClassName = "SecondClassTrayWnd"
        USER32.RegisterClassW(ctypes.byref(cls))
        self._hwnd = USER32.CreateWindowExW(
            0, "SecondClassTrayWnd", "SecondClass", 0,
            0, 0, 0, 0, 0, 0, 0, 0)
        if not self._hwnd:
            self._started.set()
            return
        self._load_icon()
        nid = self._make_nid()
        try:
            SHELL32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        except Exception:
            pass
        self._started.set()
        self._msg_loop()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            evt = lparam & 0xFFFF
            if evt == WM_RBUTTONUP:
                self._show_menu()
            elif evt == WM_LBUTTONUP:
                self.on_command("open")
        elif msg == WM_APP + 2:
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
            if ret <= 0:
                break
            USER32.TranslateMessage(ctypes.byref(self._msg))
            USER32.DispatchMessageW(ctypes.byref(self._msg))
        try:
            USER32.DestroyWindow(self._hwnd)
        except Exception:
            pass
        self._hwnd = 0
