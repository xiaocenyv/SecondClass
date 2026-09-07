# -*- coding: utf-8 -*-
"""SecondClass v2 入口：python app.py [--smoke] [--daily]"""
import ctypes
import json
import sys

# 高 DPI 感知：避免 Windows 缩放导致界面模糊
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def run_daily_mode() -> int:
    """静默自动刷题模式（任务计划调用）：无 GUI，通知后退出。"""
    from core.applock import AppLock, DAILY_LOCK_PORT
    from core.config import Config
    from core.daily import run_daily
    lock = AppLock(DAILY_LOCK_PORT)
    if not lock.acquire():
        # 已有 --daily 在运行，避免重复刷题
        return 0
    try:
        result = run_daily(Config())
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "completed" else 1
    except Exception as e:
        print(json.dumps({"status": "failed", "detail": repr(e)},
                         ensure_ascii=False))
        return 1
    finally:
        lock.release()


def run_selfcheck() -> int:
    """零依赖自检：验证打包后全部核心依赖可用（--windowed 下写日志文件）。"""
    import os
    import traceback

    log_path = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")),
                            "SecondClass_selfcheck.log")

    def fail(stage: str, exc: Exception):
        msg = "SELFCHECK FAIL [{}]: {}\n{}".format(stage, repr(exc),
                                                  traceback.format_exc())
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        print(msg)
        return 1

    try:
        from core.config import Config
        from core.api_client import ApiClient
        from core.answer_engine import AnswerEngine
        from core.daily import run_daily
        from core.scheduler import register, query
        from core.notify import notify
        ok_checks = ["core 模块导入"]
    except Exception as e:
        return fail("core", e)
    try:
        from capture import certgen, proxy_ctl
        from capture.proxy import ProxyService, _parse_headers
        certgen.ensure_ca()
        key_pem, cert_pem = certgen.issue_cert("selfcheck.example.com")
        assert b"PRIVATE KEY" in key_pem and b"CERTIFICATE" in cert_pem
        p = ProxyService(port=0)
        ok_checks.append("内置代理（cryptography 证书）")
    except Exception as e:
        return fail("proxy", e)
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
        ok_checks.append("tkinter GUI")
    except Exception as e:
        return fail("tk", e)
    msg = "SELFCHECK OK: " + " / ".join(ok_checks)
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass
    print(msg)
    return 0


def main() -> int:
    if "--selfcheck" in sys.argv:
        return run_selfcheck()
    if "--daily" in sys.argv:
        return run_daily_mode()
    smoke = "--smoke" in sys.argv
    try:
        import tkinter as tk
        from tkinter import messagebox

        from core.applock import AppLock, GUI_LOCK_PORT
        from core.config import Config
        from gui.main_window import MainWindow

        # 单实例锁：重复启动时提示并退出（防双窗口/双代理/双向导）
        lock = AppLock(GUI_LOCK_PORT)
        if not lock.acquire() and not smoke:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("SecondClass 已在运行",
                                "SecondClass 已经在运行了。\n请查看任务栏/任务管理器中的窗口；"
                                "本次启动已取消（避免重复弹窗与抓包冲突）。")
            root.destroy()
            return 0
        try:
            root = tk.Tk()
            config = Config()
            MainWindow(root, config, enable_tray=not smoke)
            if smoke:
                # 自检模式：1.5 秒后自动关闭；GUI 能正常构建即通过
                def _quit():
                    root.destroy()
                root.after(1500, _quit)
            root.mainloop()
            return 0
        finally:
            lock.release()
    except Exception as e:
        try:
            from tkinter import messagebox
            messagebox.showerror("启动失败", "程序启动失败：{}".format(repr(e)))
        except Exception:
            pass
        print("启动失败：{}".format(repr(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
