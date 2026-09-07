# -*- coding: utf-8 -*-
"""Windows 系统代理控制与本地 MITM CA 证书管理（仅 Windows）。"""
import ctypes
import subprocess
import winreg
from pathlib import Path

from . import certgen

INET_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
PROXY_PORT = 8080
INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37


def _wininet_refresh() -> None:
    try:
        ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
    except Exception:
        pass


# 微信相关进程名（微信 3.x / 4.x 及小程序运行时，大小写不敏感）
WECHAT_PROCESSES = ("WeChat.exe", "Weixin.exe", "WeChatAppEx.exe",
                    "WeixinAppEx.exe", "WeChatProxy.exe")


def wechat_running() -> bool | None:
    """检测电脑版微信是否在运行（抓包必要前提）。

    返回 (bool, matched_name) 由调用方按需读取：None 表示检测失败（按运行处理）。
    """
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=10).stdout or ""
    except Exception:
        return None
    for name in WECHAT_PROCESSES:
        if name.lower() in out.lower():
            return True  # 已命中（附带进程名由调用方打印）
    return False


def wechat_matched_name() -> str:
    """返回命中的微信进程名（无则空串）。"""
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=10).stdout or ""
    except Exception:
        return ""
    for name in WECHAT_PROCESSES:
        if name.lower() in out.lower():
            return name
    return ""


def read_proxy() -> dict:
    """读取当前系统代理设置（用于备份）。"""
    out = {"enable": 0, "server": "", "auto": ""}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET_KEY, 0, winreg.KEY_READ) as k:
            for name in ("ProxyEnable", "ProxyServer", "AutoConfigURL"):
                try:
                    out[name.lower()] = winreg.QueryValueEx(k, name)[0]
                except OSError:
                    pass
    except OSError:
        pass
    return out


def apply_proxy(host: str = "127.0.0.1", port: int = PROXY_PORT) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET_KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ,
                          "http://{}:{}".format(host, port))
    _wininet_refresh()


def restore_proxy(backup: dict) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET_KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD,
                          int(backup.get("enable", 0)))
        # 无论备份是否有值都写回，避免残留抓包代理地址
        winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ,
                          str(backup.get("server", "")))
        if backup.get("auto"):
            winreg.SetValueEx(k, "AutoConfigURL", 0, winreg.REG_SZ,
                              str(backup.get("auto")))
    _wininet_refresh()


# ---------------- 本地 MITM CA 证书 ----------------

def ca_cert_file() -> Path:
    """CA 证书文件（certutil 安装用 .cer）。"""
    certgen.ensure_ca()
    return certgen.ca_cer_path()


def is_ca_trusted() -> bool:
    """通过指纹检查 CA 是否已加入当前用户受信任根。"""
    try:
        fp = certgen.ca_fingerprint()
    except Exception:
        return False
    try:
        out = subprocess.run(["certutil", "-user", "-store", "Root", fp],
                             capture_output=True, text=True, errors="replace",
                             timeout=15).stdout or ""
    except Exception:
        return False
    return fp in out.upper() or "SecondClass" in out


def install_ca() -> tuple[bool, str]:
    """安装本地 CA 到当前用户受信任根（-user 免 UAC；失败则 UAC 提权兜底）。"""
    cer = ca_cert_file()
    try:
        r = subprocess.run(["certutil", "-user", "-addstore", "-f", "Root", str(cer)],
                           capture_output=True, text=True, errors="replace", timeout=30)
        if r.returncode == 0:
            return True, "证书已安装"
    except Exception:
        pass
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          "Start-Process certutil -ArgumentList "
                          "'-addstore','-f','Root','{}' -Verb RunAs -Wait".format(cer)])
        return False, "已请求管理员确认（请在弹出的 UAC 窗口点「是」），完成后重试"
    except Exception:
        return False, "证书安装失败，请手动安装：{}".format(cer)
