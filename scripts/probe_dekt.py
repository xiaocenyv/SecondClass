# -*- coding: utf-8 -*-
"""无凭据接口探测：摸清 web 端学生接口是否存在（只读）"""
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://dekt.hfut.edu.cn"
ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
s = requests.Session()
s.headers.update({"User-Agent": ua,
                  "Accept": "application/json, text/plain, */*",
                  "Referer": BASE + "/"})

# 先访问首页拿会话
h = s.get(BASE + "/", timeout=10)
print("首页:", h.status_code, "| cookies:", [c.name for c in s.cookies])

paths = [
    "/scReports/login/isVerify",
    "/scReports/login",
    "/scReports/api/wx/netlearning/page/1/10",
    "/scReports/api/wx/netlearning/filter/condition",
    "/scReports/api/user/info",
    "/scReports/api/wx/user/info",
    "/scReports/api/menu/list",
    "/scReports/index/main",
    "/scReports/login/main",
    "/scReports/login/getCaptcha",
    "/scReports/login/captcha",
]
for p in paths:
    try:
        r = s.get(BASE + p, timeout=10)
        body = r.text[:100].replace("\n", " ").replace("\r", "")
        print("GET", p, "->", r.status_code, "|", r.headers.get("content-type", "")[:30], "|", body)
    except Exception as e:
        print("GET", p, "ERR", str(e)[:80])
