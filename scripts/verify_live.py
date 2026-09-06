# -*- coding: utf-8 -*-
"""真机只读探测：用捕获的凭据验证第二课堂接口真实结构（不提交任何答案）。"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.api_client import ApiClient, LIST_PAYLOAD, PATH_OPEN, PATH_PAGE, PATH_QUESTIONS

base = os.environ.get("APPDATA") or os.path.expanduser("~")
cap = Path(base) / "SecondClass" / "captured.json"
cfg_path = Path(base) / "SecondClass" / "config.json"

data = None
if cap.exists():
    data = json.load(open(cap, "r", encoding="utf-8"))
elif cfg_path.exists():
    cfg = json.load(open(cfg_path, "r", encoding="utf-8"))
    if cfg.get("key_session") and cfg.get("secret"):
        data = cfg
if not data:
    print("未找到凭据文件")
    sys.exit(2)

ks = data["key_session"]
secret = data["secret"]
print("凭据来源:", cap.name if cap.exists() else "config.json")
print("key_session: {}…{}（长度 {}）".format(ks[:4], ks[-4:], len(ks)))
print("secret:      {}…{}（长度 {}）".format(secret[:4], secret[-4:], len(secret)))

api = ApiClient(ks, secret)
ok, msg = api.check_credentials()
print("\n[1] 凭据测试:", "✅" if ok else "❌", msg)
if not ok:
    sys.exit(3)

print("\n[2] 文章列表（第 1 页）…")
import json as _j
data1 = api.post_json(PATH_PAGE.format(page=1, size=10), dict(LIST_PAYLOAD))
lst = (data1.get("data") or {}).get("list") or []
print("  共", len(lst), "篇文章；顶层 keys:", list(data1.keys()))
if lst:
    a0 = lst[0]
    print("  文章样例 keys:", list(a0.keys()))
    show = {k: (str(v)[:60]) for k, v in a0.items() if k in
            ("id", "title", "name", "videoUrl", "correct", "type", "category", "credit")}
    print("  样例字段:", json.dumps(show, ensure_ascii=False))
    # 打开第一篇未完成文章（只读）
    target = None
    for a in lst:
        if not a.get("videoUrl") and a.get("correct") != "已完成":
            target = a
            break
    if target is None:
        target = lst[0]
    aid = str(target.get("id"))
    print("\n[3] 打开文章 {}（{}）…".format(aid, str(target.get("title", target.get("name", "")))[:40]))
    try:
        open_resp = api.get_json(PATH_OPEN.format(article_id=aid))
        print("  打开响应 keys:", list(open_resp.keys()) if isinstance(open_resp, dict) else type(open_resp))
    except Exception as e:
        print("  打开异常:", e)
    print("\n[4] 取题 …")
    try:
        # 等待几秒再取，行为与真实用户一致一些（可选）
        q = api.get_json(PATH_QUESTIONS.format(article_id=aid))
        d = q.get("data") or {}
        print("  data keys:", list(d.keys()) if isinstance(d, dict) else d)
        print("  accquieCredit:", d.get("accquieCredit"), "| todayReach:", d.get("todayReach"))
        qs = d.get("questions") or []
        print("  题目数:", len(qs))
        for i, qitem in enumerate(qs[:3]):
            print("  --- 题目{} ---".format(i + 1))
            print("    keys:", list(qitem.keys()))
            print("    queType:", qitem.get("queType"), "| id:", qitem.get("id"))
            print("    title:", str(qitem.get("title", qitem.get("content", "")))[:80])
            opts = qitem.get("optionList") or []
            print("    选项数:", len(opts), "| 选项样例:", [(o.get("id"), str(o.get("optionContent", ""))[:30]) for o in opts[:4]])
            # 不提交答案！
    except Exception as e:
        print("  取题异常:", repr(e))
print("\n[只读探测完成] 未提交任何答案。")
