# -*- coding: utf-8 -*-
"""通知反馈：横幅 / 弹窗 / 仅记录 三种形式（Windows）。"""
import json
import os
import subprocess
import time
from pathlib import Path

from .config import data_dir, log_to_file

# 通知模式：banner(默认) / popup / log
MODES = ("banner", "popup", "log")


def _escape_xml(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def _toast(title: str, body: str):
    """Windows 通知横幅（PowerShell WinRT，无第三方依赖）。"""
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
        "ContentType = WindowsRuntime] | Out-Null\n"
        "$tpl = @\"\n<toast><visual><binding template='ToastGeneric'>"
        "<text>{}</text><text>{}</text>"
        "</binding></visual></toast>\n\"@\n"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        "$xml.LoadXml($tpl)\n"
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)\n"
        "[Windows.UI.Notifications.ToastNotificationManager]::"
        "CreateToastNotifier('SecondClass').Show($toast)\n"
    ).format(_escape_xml(title), _escape_xml(body))
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-Command", script], timeout=15,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def _popup(title: str, body: str):
    """系统弹窗（无 GUI 也能弹）。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, body, title, 0x40)  # MB_OK | MB_ICONINFORMATION
    except Exception:
        pass


def notify(title: str, body: str, mode: str = "banner", record: bool = True) -> None:
    """按模式发送通知；始终记录到日志。失败静默降级。"""
    if mode not in MODES:
        mode = "banner"
    if record:
        try:
            log_to_file("notify", "{} | {}".format(title, body))
            rec = os.path.join(data_dir(), "daily_result.json")
            with open(rec, "a", encoding="utf-8") as f:  # 追加一行记录
                f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "title": title, "body": body},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
    if mode == "banner":
        _toast(title, body)
    elif mode == "popup":
        _popup(title, body)
    # mode == "log": 仅记录
