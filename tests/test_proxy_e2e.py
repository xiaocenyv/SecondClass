# -*- coding: utf-8 -*-
"""端到端测试：本地 HTTPS 服务器 + 内置 MITM 代理 + requests 走代理捕获凭据。"""
import asyncio
import http.server
import os
import socket
import ssl
import tempfile
import threading
import time
import unittest
from pathlib import Path

import requests

from capture import certgen, proxy_ctl
from capture.proxy import ProxyService


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body) + 2))
        self.end_headers()
        self.wfile.write(b"OK:" + body)
        self.connection.close()  # 单请求连接，方便代理双向泵送结束

    def log_message(self, *a):
        pass


class TestProxyE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self.tmp.name
        self.srv_port = _free_port()
        self.proxy_port = _free_port()
        # HTTPS echo server（用本 CA 签发 localhost 证书）
        certgen.ensure_ca()
        key_pem, cert_pem = certgen.issue_cert("localhost")
        td = tempfile.mkdtemp()
        kp = Path(td) / "k.pem"
        cp = Path(td) / "c.pem"
        kp.write_bytes(key_pem)
        cp.write_bytes(cert_pem)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cp, kp)
        self.httpd = http.server.HTTPServer(("127.0.0.1", self.srv_port), _EchoHandler)
        self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.captured = []
        self.proxy = ProxyService(host_filter="localhost", port=self.proxy_port,
                                  on_credentials=lambda ks, sec: self.captured.append((ks, sec)),
                                  verify_upstream=False)
        self.proxy.start()
        time.sleep(0.8)

    def tearDown(self):
        self.proxy.stop(timeout=3)
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.old is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self.old
        self.tmp.cleanup()

    def test_capture_via_proxy(self):
        proxies = {"https": "http://127.0.0.1:{}".format(self.proxy_port)}
        try:
            r = requests.post("https://localhost:{}/x".format(self.srv_port),
                              json={"a": 1},
                              headers={"key_session": "KS-E2E", "secret": "SEC-E2E",
                                       "User-Agent": "test"},
                              proxies=proxies, verify=False, timeout=15)
            self.assertEqual(r.status_code, 200)
        except requests.RequestException:
            pass  # 转发链路故障不影响捕获断言
        deadline = time.time() + 10
        while time.time() < deadline and not self.captured:
            time.sleep(0.2)
        self.assertTrue(self.captured, "代理应捕获到凭据")
        self.assertEqual(self.captured[0], ("KS-E2E", "SEC-E2E"))
        # 凭据文件也已保存
        cap = Path(self.tmp.name) / "SecondClass" / "captured.json"
        self.assertTrue(cap.exists())


if __name__ == "__main__":
    unittest.main()
