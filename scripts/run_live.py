# -*- coding: utf-8 -*-
"""真机全量刷题：用捕获的凭据真实跑一遍（会真实提交答案）。"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.api_client import ApiClient
from core.answer_engine import AnswerEngine
from core.config import AnswerCache, Config

base = os.environ.get("APPDATA") or os.path.expanduser("~")
cap = Path(base) / "SecondClass" / "captured.json"
data = json.load(open(cap, "r", encoding="utf-8"))
ks, secret = data["key_session"], data["secret"]

cfg = Config()
engine = AnswerEngine(
    ApiClient(ks, secret),
    cfg,
    AnswerCache(),
    on_log=lambda level, text: print("[{}] {}".format(level.upper(), text)),
)
stats = engine.run()
print()
print(stats.summary())
