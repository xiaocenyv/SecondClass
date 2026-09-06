# -*- coding: utf-8 -*-
"""每日自动流程测试（mock 接口，不触网/不弹通知）。"""
import os
import tempfile
import unittest

from core.daily import check_today, run_daily
from core.config import Config


class FakeApi:
    def __init__(self, today_reach=False):
        self.today_reach = today_reach
        self.secret = "s"
        self.key_session = "k"

    def post_json(self, path, payload):
        if "/page/" in path:
            return {"data": {"list": [{"id": "a1", "videoUrl": "", "correct": ""}]}}
        if "/answer/" in path:
            return {"data": {"desc": "恭喜,获得积分"}}
        raise AssertionError("unexpected " + path)

    def get_json(self, path):
        if "/questions/" in path:
            return {"data": {"accquieCredit": False,
                             "todayReach": self.today_reach,
                             "questions": [{
                                 "id": "q1", "queType": 0,
                                 "optionList": [{"id": "o1", "optionContent": "A"},
                                                {"id": "o2", "optionContent": "B"}],
                             }]}}
        if "/netlearning/" in path:
            return {"data": {}}
        raise AssertionError("unexpected " + path)


class TestDaily(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self.tmp.name
        self.cfg = Config(path=os.path.join(self.tmp.name, "config.json"))

    def tearDown(self):
        if self.old is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self.old
        self.tmp.cleanup()

    def test_no_credentials(self):
        r = run_daily(self.cfg, mode="log")
        self.assertEqual(r["status"], "no-credentials")

    def test_already_reached_skips(self):
        self.cfg.patch(key_session="k", secret="s")
        api = FakeApi(today_reach=True)
        import core.daily as daily
        orig = daily.ApiClient
        daily.ApiClient = lambda ks, sec: api
        try:
            r = run_daily(self.cfg, mode="log")
        finally:
            daily.ApiClient = orig
        self.assertEqual(r["status"], "completed")
        self.assertIn("已达成", r["detail"])

    def test_runs_and_completes(self):
        self.cfg.patch(key_session="k", secret="s", wait_seconds=0, pages=1)
        api = FakeApi(today_reach=False)
        import core.daily as daily
        orig = daily.ApiClient
        daily.ApiClient = lambda ks, sec: api
        try:
            r = run_daily(self.cfg, mode="log")
        finally:
            daily.ApiClient = orig
        self.assertEqual(r["status"], "completed")
        self.assertEqual(r["articles"], 1)
        self.assertEqual(r["questions"], 1)


if __name__ == "__main__":
    unittest.main()
