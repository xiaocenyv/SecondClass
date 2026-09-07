# -*- coding: utf-8 -*-
"""下载 Release 资产（构建辅助）：python requests 分块下载。"""
import os
import sys

import requests

url = "https://github.com/xiaocenyv/SecondClass/releases/download/v2.1.1/SecondClass.exe"
dst = os.path.join(os.environ.get("TEMP", "."), "sc211", "SecondClass.exe")
os.makedirs(os.path.dirname(dst), exist_ok=True)

with requests.get(url, stream=True, timeout=(20, 600)) as r:
    r.raise_for_status()
    total = int(r.headers.get("Content-Length", 0))
    got = 0
    with open(dst, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
            got += len(chunk)
print("downloaded:", dst, got, "bytes")
