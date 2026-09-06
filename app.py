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
    from core.config import Config
    from core.daily import run_daily
    try:
        result = run_daily(Config())
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "completed" else 1
    except Exception as e:
        print(json.dumps({"status": "failed", "detail": repr(e)},
                         ensure_ascii=False))
        return 1


def run_selfcheck() -> int:
    """零依赖自检：验证打包后全部核心依赖可用（无 GUI，仅输出结果）。"""
    ok_checks = []
    try:
        from core.config import Config
        from core.api_client import ApiClient
        from core.answer_engine import AnswerEngine
        from core.daily import run_daily
        from core.scheduler import register, query
        from core.notify import notify
        ok_checks.append("core 模块导入")
    except Exception as e:
        print("FAIL core: {}".format(repr(e)))
        return 1
    try:
        from capture import certgen, proxy_ctl
        from capture.proxy import ProxyService, _parse_headers
        certgen.ensure_ca()
        key_pem, cert_pem = certgen.issue_cert("selfcheck.example.com")
        assert b"PRIVATE KEY" in key_pem and b"CERTIFICATE" in cert_pem
        p = ProxyService(port=0)
        ok_checks.append("内置代理（cryptography 证书）")
    except Exception as e:
        print("FAIL proxy: {}".format(repr(e)))
        return 1
    try:
        import webbrowser  # noqa
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
        ok_checks.append("tkinter GUI")
    except Exception as e:
        print("FAIL tk: {}".format(repr(e)))
        return 1
    print("SELFCHECK OK: " + " / ".join(ok_checks))
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

        from core.config import Config
        from gui.main_window import MainWindow

        root = tk.Tk()
        config = Config()
        MainWindow(root, config)
        if smoke:
            # 自检模式：1.5 秒后自动关闭；GUI 能正常构建即通过
            def _quit():
                root.destroy()
            root.after(1500, _quit)
        root.mainloop()
        return 0
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
