# -*- coding: utf-8 -*-
"""自动触发管理：登录触发用注册表 Run 键（免 UAC），每日定时用任务计划。

两种触发统一指向一个无空格路径的 run_daily.cmd 包装脚本，
避免 Windows 命令行 schtasks /TR 的引号嵌套问题。
"""
import subprocess
import winreg
from pathlib import Path

from .config import data_dir

TASK_DAILY = "SecondClassDaily"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "SecondClassDailyOnLogon"


def _wrapper_path() -> Path:
    return Path(data_dir()) / "run_daily.cmd"


def _write_wrapper(cmd_prefix: str) -> Path:
    """生成 run_daily.cmd；cmd_prefix 为完整命令前缀（形如 "python.exe" "app.py"）。"""
    w = _wrapper_path()
    content = '@echo off\r\n{} --daily\r\n'.format(cmd_prefix)
    w.write_text(content, encoding="gbk", errors="replace")
    return w


def _run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "超时"
    except FileNotFoundError:
        return -1, "找不到命令"


def _create_task(name: str, wrapper: str, trigger_args: list[str]) -> tuple[bool, str]:
    """创建/覆盖一个任务；wrapper 为无空格路径的 cmd 脚本。"""
    cmd = ["schtasks", "/Create", "/F", "/TN", name,
           "/TR", wrapper, "/RL", "LIMITED"] + trigger_args
    rc, out = _run(cmd)
    if rc != 0:
        return False, "创建任务 {} 失败：{}".format(name, out.strip()[-200:])
    return True, "任务 {} 已注册".format(name)


def _delete_task(name: str) -> None:
    _run(["schtasks", "/Delete", "/F", "/TN", name])


def register(cmd_prefix: str, logon: bool, daily: bool,
             daily_time: str = "12:30") -> list[str]:
    """按配置注册自动触发（登录用 Run 键 / 定时用任务计划）。返回操作信息列表。"""
    msgs = []
    wrapper = str(_write_wrapper(cmd_prefix))
    # 登录触发：注册表 Run 键（无需管理员）
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if logon:
                winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, wrapper)
                msgs.append("✅ 已注册登录时自动刷（Run 键）")
            else:
                try:
                    winreg.DeleteValue(k, RUN_VALUE)
                except FileNotFoundError:
                    pass
                msgs.append("已取消登录触发")
    except OSError as e:
        msgs.append("❌ 登录触发设置失败：{}".format(e))
    # 每日定时：任务计划
    if daily:
        ok, msg = _create_task(TASK_DAILY, wrapper,
                               ["/SC", "DAILY", "/ST", daily_time])
        msgs.append(("✅" if ok else "❌") + " " + msg)
    else:
        _delete_task(TASK_DAILY)
        msgs.append("已取消每日定时任务")
    return msgs


def query() -> dict:
    """返回 {logon: bool, daily: bool}。"""
    out = {"logon": False, "daily": False}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ) as k:
            try:
                winreg.QueryValueEx(k, RUN_VALUE)
                out["logon"] = True
            except FileNotFoundError:
                pass
    except OSError:
        pass
    rc, _ = _run(["schtasks", "/Query", "/TN", TASK_DAILY])
    out["daily"] = rc == 0
    return out


def unregister_all() -> None:
    _delete_task(TASK_DAILY)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            try:
                winreg.DeleteValue(k, RUN_VALUE)
            except FileNotFoundError:
                pass
    except OSError:
        pass
