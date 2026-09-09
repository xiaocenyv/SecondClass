# -*- coding: utf-8 -*-
"""单步验证 ExtractIconExW 对桌面 exe 的图标提取。"""
import os
import sys
import ctypes
from ctypes import wintypes

S = ctypes.WinDLL("shell32", use_last_error=True)
target = os.path.expandvars(r"%USERPROFILE%\Desktop\SecondClass.exe")
print("target:", target, "| exists:", os.path.exists(target))
big = wintypes.HICON()
small = wintypes.HICON()
ok = S.ExtractIconExW(target, 0, ctypes.byref(big), ctypes.byref(small), 1)
print("ExtractIconExW ret:", ok, "| big:", big.value, "| small:", small.value)
print("GetLastError:", ctypes.get_last_error())
# 备选：LoadImage LR_LOADFROMFILE
h = S.LoadImageW(None, target, 1, 32, 32, 0x10)
print("LoadImageW LR_LOADFROMFILE:", h)
