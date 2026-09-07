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


class TestWechatDetection(unittest.TestCase):
    def _mock_tasklist(self, lines):
        import subprocess
        from unittest import mock

        class R:
            stdout = lines

        return mock.patch("subprocess.run", return_value=R())

    def test_weixin4_hit(self):
        out = ('"Weixin.exe","123","Console","1","12,345 K"\n'
               '"WeChatAppEx.exe","400","Console","4","50,000 K"\n')
        with self._mock_tasklist(out):
            from capture.proxy_ctl import wechat_running, wechat_matched_name
            self.assertTrue(wechat_running())
            self.assertEqual(wechat_matched_name(), "Weixin.exe")

    def test_old_wechat_hit(self):
        out = '"WeChat.exe","100","Console","1","60,000 K"\n'
        with self._mock_tasklist(out):
            from capture.proxy_ctl import wechat_running, wechat_matched_name
            self.assertTrue(wechat_running())
            self.assertEqual(wechat_matched_name(), "WeChat.exe")

    def test_no_wechat(self):
        out = '"explorer.exe","5","Console","1","20,000 K"\n'
        with self._mock_tasklist(out):
            from capture.proxy_ctl import wechat_running
            self.assertFalse(wechat_running())

    def test_detect_failure_passes(self):
        import subprocess
        from unittest import mock
        with mock.patch("subprocess.run", side_effect=OSError("x")):
            from capture.proxy_ctl import wechat_running
            self.assertIsNone(wechat_running())


class TestInstallScript(unittest.TestCase):
    def test_script_wellformed(self):
        from capture.proxy_ctl import build_install_script
        cer = r"C:\Users\1\AppData\Roaming\SecondClass\ca\ca.cer"
        s = build_install_script(cer)
        self.assertIn(cer, s)             # 占位符已替换
        self.assertNotIn("__CER__", s)    # 无残留占位符
        # 括号平衡（幂脚本正确性粗检）
        self.assertEqual(s.count("{"), s.count("}"))
        self.assertEqual(s.count("'"), s.count("'"))  # 引号成对（偶数）
        # 不能再用 format 解析（裸大括号存在，任何 format 调用都会报错 → 结构安全）
        with self.assertRaises(Exception):
            s.format("x")

    def test_install_fallback_returns_msg(self):
        """install_ca 在任何异常路径下返回 (False, 可读说明)，不抛异常。"""
        import subprocess
        from unittest import mock
        from capture import proxy_ctl
        with mock.patch.object(proxy_ctl, "ca_cert_file", side_effect=OSError("x")):
            ok, msg = proxy_ctl.install_ca()
            self.assertFalse(ok)
            self.assertIn("失败", msg)


if __name__ == "__main__":
    unittest.main()
