# -*- coding: utf-8 -*-
"""配置与答案缓存测试（临时目录隔离，不碰真实数据）。"""
import os
import tempfile
import unittest

from core.config import AnswerCache, Config


class TestConfig(unittest.TestCase):
    def test_defaults_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            cfg = Config(path=path)
            self.assertEqual(cfg.get("pages"), 2)
            self.assertEqual(cfg.get("key_session"), "")
            cfg.patch(key_session="abc", secret="def", pages=5)
            cfg.save()
            cfg2 = Config(path=path)
            self.assertEqual(cfg2.get("key_session"), "abc")
            self.assertEqual(cfg2.get("secret"), "def")
            self.assertEqual(cfg2.get("pages"), 5)

    def test_corrupt_file_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("not json {{{")
            cfg = Config(path=path)
            self.assertEqual(cfg.get("pages"), 2)  # 回到默认值，不崩溃

    def test_unknown_keys_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"pages": 7, "hack": "x"}')
            cfg = Config(path=path)
            self.assertEqual(cfg.get("pages"), 7)
            self.assertIsNone(cfg.get("hack", None))


class TestAnswerCache(unittest.TestCase):
    def test_set_get_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.json")
            c = AnswerCache(path=path)
            c.set("s1", "k1", "art1", "q1", ["o1", "o2"])
            self.assertEqual(c.get("s1", "k1", "art1", "q1"), ["o1", "o2"])
            c2 = AnswerCache(path=path)
            self.assertEqual(c2.get("s1", "k1", "art1", "q1"), ["o1", "o2"])

    def test_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = AnswerCache(path=os.path.join(tmp, "cache.json"))
            c.set("secretA", "keyA", "art1", "q1", ["oX"])
            self.assertIsNone(c.get("secretB", "keyB", "art1", "q1"))
            self.assertEqual(c.get("secretA", "keyA", "art1", "q1"), ["oX"])

    def test_clear_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = AnswerCache(path=os.path.join(tmp, "cache.json"))
            c.set("s", "k", "art", "q", ["o"])
            c.clear_question("s", "k", "art", "q")
            self.assertIsNone(c.get("s", "k", "art", "q"))


if __name__ == "__main__":
    unittest.main()
