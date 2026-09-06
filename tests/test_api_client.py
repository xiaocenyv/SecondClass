# -*- coding: utf-8 -*-
"""API 客户端测试：请求头组装与异常分类（mock，不联网）。"""
import unittest
from unittest.mock import MagicMock, patch

from core import api_client
from core.api_client import ApiClient, ApiError


class TestApiClient(unittest.TestCase):
    def test_headers(self):
        client = ApiClient("KS", "SEC")
        h = client.session.headers
        self.assertEqual(h["key_session"], "KS")
        self.assertEqual(h["secret"], "SEC")
        self.assertIn("MicroMessenger", h["User-Agent"])
        self.assertIn("dekt.hfut.edu.cn", h["Host"])

    def test_http_error(self):
        client = ApiClient("KS", "SEC")
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "boom"
        resp.json.side_effect = ValueError()
        with patch.object(client.session, "request", return_value=resp):
            with self.assertRaises(ApiError) as ctx:
                client.get_json("/x")
            self.assertEqual(ctx.exception.kind, "http")

    def test_timeout_retry_then_fail(self):
        import requests
        client = ApiClient("KS", "SEC", timeout=5)
        mock = MagicMock(side_effect=requests.Timeout("t"))
        with patch.object(client.session, "request", mock):
            with self.assertRaises(ApiError) as ctx:
                client.get_json("/x")
            self.assertEqual(ctx.exception.kind, "timeout")
            self.assertEqual(mock.call_count, 2)  # 重试了一次

    def test_connection_retry_once_then_ok(self):
        import requests
        client = ApiClient("KS", "SEC")
        good_resp = MagicMock(status_code=200)
        good_resp.json.return_value = {"data": {"list": []}}
        mock = MagicMock(side_effect=[requests.ConnectionError("x"), good_resp])
        with patch.object(client.session, "request", mock):
            data = client.get_json("/ok")
            self.assertEqual(data["data"]["list"], [])

    def test_check_credentials_ok(self):
        client = ApiClient("KS", "SEC")
        data_resp = MagicMock(status_code=200)
        data_resp.json.return_value = {"data": {"list": []}}
        with patch.object(client.session, "request", return_value=data_resp):
            ok, msg = client.check_credentials()
            self.assertTrue(ok)

    def test_check_credentials_bad_structure(self):
        client = ApiClient("KS", "SEC")
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"error": "not login"}
        with patch.object(client.session, "request", return_value=resp):
            ok, msg = client.check_credentials()
            self.assertFalse(ok)
            self.assertIn("结构异常", msg)


if __name__ == "__main__":
    unittest.main()
