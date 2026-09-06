# -*- coding: utf-8 -*-
"""构建辅助：截取应用界面截图（assets/screens/*.png），需要桌面会话。

用法: python scripts/capture_screens.py
"""
import ctypes
import os
import sys
import time
import tkinter as tk

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 高 DPI 感知：与截图坐标一致
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PIL import ImageGrab

OUT = os.path.join(ROOT, "assets", "screens")


def grab_window(root: tk.Tk, path: str):
    root.update_idletasks()
    root.update()
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    if w <= 1 or h <= 1:
        print("窗口尺寸异常，跳过", path)
        return False
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(path)
    print("saved:", path, img.size)
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    root = tk.Tk()
    root.geometry("800x680+40+40")
    from core.config import Config
    from gui.main_window import MainWindow
    from gui.tutorial import TutorialWindow
    app = MainWindow(root, Config())
    root.after(600, lambda: None)
    # 等 UI 完整渲染
    for _ in range(10):
        root.update()
        time.sleep(0.05)
    # 关闭首次向导自动弹出的教程窗，保证主窗口截图干净
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()
    root.update()
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    time.sleep(0.3)
    ok1 = grab_window(root, os.path.join(OUT, "main.png"))

    # 教程窗口
    tut = TutorialWindow(root)
    tut.geometry("640x520+900+40")
    for _ in range(10):
        root.update()
        time.sleep(0.05)
    tut.lift()
    root.update()
    time.sleep(0.3)
    ok2 = grab_window(tut, os.path.join(OUT, "tutorial.png"))
    tut.destroy()

    # 抓包助手窗口
    from gui.capture_window import CaptureWindow
    cap = CaptureWindow(root, on_captured=lambda ks, s: None)
    cap.geometry("520x420+40+120")
    for _ in range(10):
        root.update()
        time.sleep(0.05)
    cap.lift()
    root.update()
    time.sleep(0.3)
    ok3 = grab_window(cap, os.path.join(OUT, "capture.png"))
    cap.destroy()
    root.destroy()
    print("done:", ok1, ok2, ok3)


if __name__ == "__main__":
    main()
