# -*- coding: utf-8 -*-
"""mitmproxy addon：从第二课堂小程序流量中提取 key_session / secret。

用法（由抓包助手拉起）：
    mitmdump -p 8080 -s capture/addon.py
抓取成功后把凭据写入 %APPDATA%/SecondClass/captured.json 并退出进程，
GUI 侧检测退出后自动还原系统代理。
"""
import datetime
import json
import os
import sys
from pathlib import Path

# 控制台输出统一 UTF-8（Windows GBK 终端下避免 UnicodeEncodeError）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _out_path() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = Path(base) / "SecondClass"
    d.mkdir(parents=True, exist_ok=True)
    return d / "captured.json"


def save_credentials(key_session: str, secret: str) -> Path:
    path = _out_path()
    payload = {
        "key_session": key_session,
        "secret": secret,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


class CredentialCatcher:
    """匹配目标域名的请求，捕获含 key_session 与 secret 的请求头。"""

    def __init__(self, host: str = "dekt.hfut.edu.cn"):
        self.host = host
        self.found = False

    def finish(self) -> None:
        """捕获完成后的退出动作（测试可覆写）。"""
        os._exit(0)

    def request(self, flow) -> None:
        if self.found:
            return
        req = flow.request
        try:
            if req.host != self.host:
                return
        except Exception:
            return
        ks = req.headers.get("key_session", "")
        secret = req.headers.get("secret", "")
        if ks and secret:
            self.found = True
            path = save_credentials(ks, secret)
            print("\n" + "=" * 56)
            print("  ✅ 已捕获凭据：key_session / secret")
            print("  保存至：{}".format(path))
            print("=" * 56 + "\n", flush=True)
            # 抓取完成即退出 mitmdump，由抓包助手还原代理
            self.finish()


addons = [CredentialCatcher()]
