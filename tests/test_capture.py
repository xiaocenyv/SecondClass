# -*- coding: utf-8 -*-
"""抓包助手核心逻辑测试：头部解析、凭据保存、证书生成（不启真实代理）。"""
import os
import tempfile
import unittest
from pathlib import Path

from capture import certgen
from capture.proxy import _parse_headers, save_credentials


class TestParseHeaders(unittest.TestCase):
    def test_basic(self):
        data = (b"GET /x HTTP/1.1\r\nHost: a.com\r\n"
                b"key_session: KS1\r\nsecret: SEC1\r\n")
        h = _parse_headers(data)
        self.assertEqual(h["key_session"], "KS1")
        self.assertEqual(h["secret"], "SEC1")
        self.assertEqual(h["host"], "a.com")

    def test_case_insensitive(self):
        h = _parse_headers(b"X-Key: AAAA:BBBB\r\n")
        self.assertEqual(h["x-key"], "AAAA:BBBB")


class TestSaveCredentials(unittest.TestCase):
    def test_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("APPDATA")
            os.environ["APPDATA"] = tmp
            try:
                path = save_credentials("K", "S")
                self.assertTrue(path.exists())
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["key_session"], "K")
                self.assertEqual(data["secret"], "S")
            finally:
                if old is None:
                    os.environ.pop("APPDATA", None)
                else:
                    os.environ["APPDATA"] = old


class TestCertGen(unittest.TestCase):
    def test_ca_and_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("APPDATA")
            os.environ["APPDATA"] = tmp
            try:
                key_pem, cert_pem = certgen.ensure_ca()
                self.assertIn("BEGIN CERTIFICATE", cert_pem)
                fp = certgen.ca_fingerprint()
                self.assertEqual(len(fp), 64)
                # 签发目标证书
                k, c = certgen.issue_cert("dekt.hfut.edu.cn")
                self.assertIn(b"PRIVATE KEY", k)
                self.assertIn(b"BEGIN CERTIFICATE", c)
            finally:
                if old is None:
                    os.environ.pop("APPDATA", None)
                else:
                    os.environ["APPDATA"] = old


if __name__ == "__main__":
    unittest.main()
