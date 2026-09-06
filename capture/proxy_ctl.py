# -*- coding: utf-8 -*-
"""Windows 系统代理控制与 mitmproxy CA 证书管理（仅 Windows）。"""
import ctypes
import os
import shutil
import subprocess
import time
from pathlib import Path

import winreg

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


def read_proxy() -> dict:
    """读取当前系统代理设置（用于备份）。"""
    out = {"enable": 0, "server": "", "auto": ""}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET_KEY, 0, winreg.KEY_READ) as k:
            for name, default in (("ProxyEnable", 0), ("ProxyServer", ""),
                                  ("AutoConfigURL", "")):
                try:
                    out[name.lower()] = winreg.QueryValueEx(k, name)[0]
                except OSError:
                    out[name.lower()] = default
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


# ---------------- CA 证书 ----------------

def ca_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".mitmproxy"


def ca_cert_file() -> Path:
    return ca_dir() / "mitmproxy-ca-cert.cer"


def find_mitmdump() -> str | None:
    """找到 mitmdump 可执行文件（优先 PATH，再扫 %LOCALAPPDATA%\\Python 安装）。"""
    exe = shutil.which("mitmdump")
    if exe and os.path.exists(exe):
        return exe
    la = os.environ.get("LOCALAPPDATA", "")
    base = os.path.join(la, "Python") if la else ""
    if os.path.isdir(base):
        for child in sorted(os.listdir(base)):
            cand = os.path.join(base, child, "Scripts", "mitmdump.exe")
            if os.path.exists(cand):
                return cand
            # pythoncore-3.14-64 这类目录再往里找
            cand2 = os.path.join(base, child, "pythoncore-3.14-64",
                                 "Scripts", "mitmdump.exe")
            if os.path.exists(cand2):
                return cand2
    return None


class MitmNotFound(Exception):
    """未找到 mitmdump 可执行文件。"""


def ensure_ca_cert(wait_seconds: float = 4.0) -> bool:
    """确保 CA 证书已生成（首次运行 mitmdump 会在 ~/.mitmproxy 生成）。"""
    if ca_cert_file().exists():
        return True
    exe = find_mitmdump()
    if not exe:
        return False
    try:
        # 短跑几秒让 mitmproxy 初始化并写证书，然后结束进程
        proc = subprocess.Popen([exe, "-p", "8099", "-q"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=wait_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    except Exception:
        return False
    return ca_cert_file().exists()


def is_ca_trusted() -> bool:
    """检查 mitmproxy CA 是否已加入本机受信任根（用户证书库）。"""
    cer = ca_cert_file()
    if not cer.exists():
        return False
    try:
        out = subprocess.run(["certutil", "-user", "-store", "Root"],
                             capture_output=True, text=True,
                             errors="replace", timeout=15).stdout or ""
    except Exception:
        return False
    # 输出含 "mitmproxy" 字样即认为已信任
    return "mitmproxy" in out.lower()


def install_ca() -> tuple[bool, str]:
    """安装 mitmproxy CA 到当前用户受信任根（优先免 UAC）。"""
    cer = ca_cert_file()
    if not cer.exists():
        return False, "证书文件未生成，请重试"
    try:
        r = subprocess.run(["certutil", "-user", "-addstore", "-f", "Root", str(cer)],
                           capture_output=True, text=True, errors="replace",
                           timeout=30)
        if r.returncode == 0:
            return True, "证书已安装"
    except Exception:
        pass
    # 备用：弹出 UAC 以管理员安装
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          "Start-Process certutil -ArgumentList "
                          "'-addstore','-f','Root','{}' -Verb RunAs -Wait".format(cer)])
        return False, "已请求管理员确认（请在弹出的 UAC 窗口点「是」），完成后重试"
    except Exception:
        return False, "证书安装失败，请手动安装：{}".format(cer)


def start_dump(addon: Path, port: int = PROXY_PORT, logfile: Path | None = None):
    """启动 mitmdump（返回 Popen 对象）；未安装时抛 MitmNotFound。"""
    exe = find_mitmdump()
    if not exe:
        raise MitmNotFound(
            "未找到 mitmdump，请先执行：pip install -r requirements-capture.txt")
    cmd = [exe, "-p", str(port), "-q", "-s", str(addon)]
    if logfile:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        f = open(logfile, "wb")
        return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(addon.parent))
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_dump(proc) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
