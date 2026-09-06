# -*- coding: utf-8 -*-
"""自动登录相关测试：AES 加密正确性与表单解析（不联网）。"""
import base64
import unittest

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from core.auto_login import (_extract_field, _extract_form_action,
                             _extract_login_error, aes_ecb_encrypt)


class TestAesEncrypt(unittest.TestCase):
    def test_matches_independent_impl(self):
        key = "0123456789abcdef"  # 16 字节
        plain = "myPass123"
        ours = aes_ecb_encrypt(key, plain)
        # 独立实现对照
        cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
        expect = base64.b64encode(cipher.encrypt(pad(plain.encode("utf-8"), 16))).decode()
        self.assertEqual(ours, expect)

    def test_wrong_key_length_raises(self):
        with self.assertRaises(Exception):
            aes_ecb_encrypt("short", "x")


class TestParsers(unittest.TestCase):
    def test_execution(self):
        html = ('<form method="post" action="login">'
                '<input type="hidden" name="execution" value="e1s1"/></form>')
        self.assertEqual(_extract_field(html, "execution"), "e1s1")

    def test_form_action(self):
        html = '<form method="post" class="x" action="login">'
        self.assertEqual(_extract_form_action(html, "https://one.hfut.edu.cn/cas/login"),
                         "https://one.hfut.edu.cn/cas/login")
        html2 = '<form method="post" action="/cas/login">'
        self.assertEqual(_extract_form_action(html2, "https://one.hfut.edu.cn/cas/login"),
                         "https://one.hfut.edu.cn/cas/login")

    def test_login_error(self):
        html = ('<div id="errorpassword">验证码错误</div>')
        self.assertEqual(_extract_login_error(html), "验证码错误")
        self.assertEqual(_extract_login_error("<html>ok</html>"), "")


if __name__ == "__main__":
    unittest.main()
