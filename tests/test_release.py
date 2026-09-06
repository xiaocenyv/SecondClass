# -*- coding: utf-8 -*-
"""发布编排基础逻辑测试（不触网、不执行 git 操作）。"""
import unittest

from core.release import DEFAULT_EXE, Publisher, find_gh


class TestPublisher(unittest.TestCase):
    def test_basic(self):
        pub = Publisher("MyRepo", "v2.0.0", "标题", "说明")
        self.assertEqual(pub.tag, "v2.0.0")
        self.assertEqual(pub.version, "2.0.0")

    def test_tag_strips_v(self):
        pub = Publisher("R", "2.1.0", "", "")
        self.assertEqual(pub.tag, "v2.1.0")

    def test_release_url(self):
        pub = Publisher("R", "1.0.0", "", "")
        pub.github_user = "alice"
        self.assertEqual(pub.release_url(),
                         "https://github.com/alice/R/releases/tag/v1.0.0")

    def test_default_exe(self):
        self.assertTrue(str(DEFAULT_EXE).endswith("SecondClass.exe"))

    def test_find_gh_type(self):
        # 环境可能有也可能没有 gh；只验证返回类型
        result = find_gh()
        self.assertTrue(result is None or isinstance(result, str))


if __name__ == "__main__":
    unittest.main()
