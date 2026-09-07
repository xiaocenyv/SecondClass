# -*- coding: utf-8 -*-
"""系统托盘模块测试（纯逻辑部分；Win32 API 不在单测内执行）。"""
import unittest

from core.tray import command_for_id, icon_source, MENU_ITEMS


class TestTrayLogic(unittest.TestCase):
    def test_menu_items(self):
        self.assertEqual([cid for cid, _ in MENU_ITEMS], [1, 2, 3, 4])

    def test_command_mapping(self):
        self.assertEqual(command_for_id(1), "open")
        self.assertEqual(command_for_id(2), "start")
        self.assertEqual(command_for_id(3), "toggle_auto")
        self.assertEqual(command_for_id(4), "quit")
        self.assertIsNone(command_for_id(999))
        self.assertIsNone(command_for_id(0))

    def test_icon_source(self):
        src = icon_source()
        self.assertTrue(src.endswith("app.ico") or src.lower().endswith(".exe"))


if __name__ == "__main__":
    unittest.main()
