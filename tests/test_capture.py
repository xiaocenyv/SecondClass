# -*- coding: utf-8 -*-
"""抓包助手核心逻辑测试（addon 提取，不启动真实代理）。"""
import os
import tempfile
import unittest
from pathlib import Path


class FakeHeaders:
    def __init__(self, d):
        self._d = d

    def get(self, name, default=""):
        return self._d.get(name, default)


class FakeRequest:
    def __init__(self, host, headers):
        self.host = host
        self.headers = FakeHeaders(headers)


class FakeFlow:
    def __init__(self, host, headers):
        self.request = FakeRequest(host, headers)


class FakeCatcher:
    """覆写 finish 避免 os._exit。"""

    def __init__(self, host="dekt.hfut.edu.cn"):
        from capture.addon import CredentialCatcher
        self.inner = CredentialCatcher(host)
        self.exited = False
        self.inner.finish = self._fake_finish

    def _fake_finish(self):
        self.exited = True

    def request(self, flow):
        self.inner.request(flow)


class TestAddon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self.old
        self.tmp.cleanup()

    def test_captures_credentials(self):
        c = FakeCatcher()
        c.request(FakeFlow("dekt.hfut.edu.cn",
                           {"key_session": "KS1", "secret": "SEC1"}))
        self.assertTrue(c.exited)
        path = Path(self.tmp.name) / "SecondClass" / "captured.json"
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["key_session"], "KS1")
        self.assertEqual(data["secret"], "SEC1")

    def test_ignores_other_host(self):
        c = FakeCatcher()
        c.request(FakeFlow("other.example.com",
                           {"key_session": "K", "secret": "S"}))
        self.assertFalse(c.exited)

    def test_ignores_missing_secret(self):
        c = FakeCatcher()
        c.request(FakeFlow("dekt.hfut.edu.cn", {"key_session": "K"}))
        self.assertFalse(c.exited)

    def test_only_once(self):
        c = FakeCatcher()
        c.request(FakeFlow("dekt.hfut.edu.cn",
                           {"key_session": "A", "secret": "B"}))
        c.request(FakeFlow("dekt.hfut.edu.cn",
                           {"key_session": "C", "secret": "D"}))
        import json
        with open(Path(self.tmp.name) / "SecondClass" / "captured.json",
                  "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["key_session"], "A")


if __name__ == "__main__":
    unittest.main()
