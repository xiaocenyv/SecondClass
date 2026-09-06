# -*- coding: utf-8 -*-
"""验证：注册每日自动任务计划 + 查询（构建辅助）。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.scheduler import register, query

prefix = '"{}" "{}"'.format(sys.executable, os.path.join(ROOT, "app.py"))
for m in register(prefix, True, True, "12:30"):
    print(m)
print("query:", query())
