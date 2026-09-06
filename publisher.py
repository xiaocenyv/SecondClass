# -*- coding: utf-8 -*-
"""发布入口：python publisher.py [--smoke]"""
import ctypes
import sys

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import messagebox

from gui.publish_window import PublishWindow


def main() -> int:
    smoke = "--smoke" in sys.argv
    try:
        root = tk.Tk()
        root.withdraw()  # 直接打开发布窗口，不显示空主窗口
        PublishWindow(root)
        if smoke:
            def _quit():
                root.destroy()
            root.after(1500, _quit)
        root.mainloop()
        return 0
    except Exception as e:
        try:
            messagebox.showerror("启动失败", "发布助手启动失败：{}".format(repr(e)))
        except Exception:
            pass
        print("启动失败：{}".format(repr(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
