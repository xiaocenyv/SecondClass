# -*- coding: utf-8 -*-
"""更新检查与日志落盘测试。"""
import os
import tempfile
import unittest

from core.updater import parse_version


class TestParseVersion(unittest.TestCase):
    def test_common(self):
        self.assertEqual(parse_version("v2.0.0"), (2, 0, 0))
        self.assertEqual(parse_version("2.1.3"), (2, 1, 3))
        self.assertEqual(parse_version("v1.0"), (1, 0, 0))

    def test_garbage(self):
        self.assertEqual(parse_version(""), (0, 0, 0))
        self.assertEqual(parse_version("v"), (0, 0, 0))
        self.assertEqual(parse_version("v2.0.0-beta"), (2, 0, 0))


class TestLogToFile(unittest.TestCase):
    def test_write(self):
        from core import config
        with tempfile.TemporaryDirectory() as tmp:
            # 重定向数据目录后再调用
            orig = config.data_dir
            try:
                import datetime
                config.data_dir = lambda: tmp
                config.log_to_file("info", "测试消息")
                day = datetime.date.today().strftime("%Y%m%d")
                path = os.path.join(tmp, "logs", day + ".log")
                self.assertTrue(os.path.exists(path))
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("测试消息", content)
                self.assertIn("[info]", content)
            finally:
                config.data_dir = orig


if __name__ == "__main__":
    unittest.main()
