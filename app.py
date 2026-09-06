# -*- coding: utf-8 -*-
"""SecondClass v2 入口：python app.py [--smoke]"""
import ctypes
import sys

# 高 DPI 感知：避免 Windows 缩放导致界面模糊
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from tkinter import messagebox

from core.config import Config
from gui.main_window import MainWindow


def main() -> int:
    smoke = "--smoke" in sys.argv
    try:
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
            messagebox.showerror("启动失败", "程序启动失败：{}".format(repr(e)))
        except Exception:
            pass
        print("启动失败：{}".format(repr(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
