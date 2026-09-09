# -*- coding: utf-8 -*-
"""单实例锁与代理残留检测测试。"""
import unittest

from capture.proxy_ctl import _proxy_stale_detect
from core.applock import AppLock


class TestAppLock(unittest.TestCase):
    def test_mutex(self):
        a = AppLock(39551)
        b = AppLock(39551)
        self.assertTrue(a.acquire())
        self.assertFalse(b.acquire())
        a.release()
        self.assertTrue(b.acquire())
        b.release()

    def test_activate_signal(self):
        import threading
        got = threading.Event()
        holder = AppLock(39552)
        caller = AppLock(39552)

        def on_activate():
            got.set()

        self.assertTrue(holder.acquire(on_activate=on_activate))
        self.assertFalse(caller.acquire())
        self.assertTrue(got.wait(timeout=3), "第二实例应触发唤起回调")
        holder.release()


class TestProxyStale(unittest.TestCase):
    def test_stale(self):
        # 代理指向 8080 且无监听 = 残留
        self.assertTrue(_proxy_stale_detect(1, "http://127.0.0.1:8080", False))
        self.assertTrue(_proxy_stale_detect(1, "http://localhost:8080", False))

    def test_live(self):
        # 8080 有服务在听 = 正常抓包中，不算残留
        self.assertFalse(_proxy_stale_detect(1, "http://127.0.0.1:8080", True))

    def test_other(self):
        # 其它代理（如 Clash 7897）不动
        self.assertFalse(_proxy_stale_detect(1, "http://127.0.0.1:7897", False))
        self.assertFalse(_proxy_stale_detect(0, "http://127.0.0.1:8080", False))


if __name__ == "__main__":
    unittest.main()
