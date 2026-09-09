# -*- coding: utf-8 -*-
"""运行修复后 tray 模块的独立验证（远程分发用）。"""
import sys
import time

sys.path.insert(0, r"C:\Users\1\AppData\Local\Temp")
# 注意 tray.py 的 icon_source() 在源码模式找 assets/app.ico → 用运行时 hack 覆盖
try:
    import tray as _t
    _t.icon_source = lambda: r"C:\Users\1\Desktop\SecondClass.exe"

    t = _t.TrayIcon(on_command=lambda c: print("CMD:", c), tooltip="SecondClass 远程验证")
    ok = t.start()
    print("START_RESULT:", ok)
    print("LAST_ERROR:", repr(t.last_error))
    time.sleep(4)
    t.stop()
    print("STOPPED")
except Exception as e:
    import traceback
    traceback.print_exc()
