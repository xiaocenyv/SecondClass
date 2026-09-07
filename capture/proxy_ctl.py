# -*- coding: utf-8 -*-
"""Windows 系统代理控制与本地 MITM CA 证书管理（仅 Windows）。"""
import ctypes
import socket
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
    """通过 X509Store Thumbprint 检查 CA 是否已加入当前用户受信任根。

    certutil 文本输出不含指纹（只有序列号），因此用 PowerShell 证书库
    按 Thumbprint 精确查询（与安装同一通道，ARM64 稳定）。
    """
    try:
        tp = certgen.ca_thumbprint_sha1()
    except Exception:
        return False
    script = (
        "$s = [System.Security.Cryptography.X509Certificates.X509Store]"
        "::new('Root','CurrentUser');"
        "$s.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly);"
        "foreach ($c in $s.Certificates) {"
        "if ($c.Thumbprint -eq '__TP__') { Write-Output 'YES'; break } }"
    ).replace("__TP__", tp)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", script], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return "YES" in (r.stdout or "")
    except Exception:
        return False


def build_install_script(cer_path: str) -> str:
    """构造安装证书的 PowerShell 脚本（占位符替换，禁用 format 防大括号误解析）。"""
    script = (
        "try {"
        "$c = [System.Security.Cryptography.X509Certificates.X509Certificate2]"
        "::new('__CER__');"
        "$s = [System.Security.Cryptography.X509Certificates.X509Store]"
        "::new('Root','CurrentUser');"
        "$s.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite);"
        "$s.Add($c);$s.Close();Write-Output 'OK'"
        "} catch { Write-Output ('ERR: ' + $_.Exception.Message) }"
    )
    return script.replace("__CER__", cer_path)


def install_ca() -> tuple[bool, str]:
    """安装本地 CA 到当前用户受信任根。

    首选 PowerShell X509Store API（免 UAC、免进程、ARM64 稳定），
    certutil 降级兜底。返回 (是否已信任, 说明)。任何异常转为可读消息。
    """
    try:
        cer = ca_cert_file()
    except Exception as e:
        return False, "证书文件生成失败：{}".format(repr(e))
    # 1) 已信任直接返回
    if is_ca_trusted():
        return True, "证书已信任"
    # 2) PowerShell X509Store（CurrentUser\Root）
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", build_install_script(str(cer))],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        out = r.stdout or ""
        if "OK" in out and is_ca_trusted():
            return True, "证书已安装（PowerShell）"
        if "ERR" in out:
            pass  # 走兜底
    except Exception:
        pass
    # 3) certutil -user 兜底
    try:
        r2 = subprocess.run(["certutil", "-user", "-addstore", "-f", "Root", str(cer)],
                            capture_output=True, text=True, errors="replace", timeout=30)
        if r2.returncode == 0 and is_ca_trusted():
            return True, "证书已安装（certutil）"
    except Exception:
        pass
    # 4) 最后兜底：提示手动安装
    return False, ("自动安装未生效，请手动安装证书：双击 {} 选择「安装证书」→ "
                   "当前用户 → 受信任的根证书颁发机构").format(cer)


def _proxy_stale_detect(enable: int, server: str, listening: bool) -> bool:
    """纯逻辑：代理指向本地 8080 但无服务在听 = 上次抓包残留。"""
    if not enable:
        return False
    if "127.0.0.1:8080" not in server and "localhost:8080" not in server:
        return False
    return not listening


def stale_proxy() -> bool:
    """检测是否存在残留抓包代理设置。"""
    st = read_proxy()
    try:
        s = socket.create_connection(("127.0.0.1", PROXY_PORT), timeout=0.4)
        s.close()
        listening = True
    except OSError:
        listening = False
    return _proxy_stale_detect(int(st.get("enable", 0) or 0), str(st.get("server", "")),
                               listening)


def cleanup_stale_proxy() -> bool:
    """清理残留代理（找到并清除返回 True）。"""
    if stale_proxy():
        restore_proxy({"enable": 0, "server": "", "auto": ""})
        return True
    return False
