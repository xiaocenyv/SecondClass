# -*- coding: utf-8 -*-
"""引擎核心逻辑测试：判定、组合、答题流程（使用假接口，不联网）。"""
import os
import unittest
from core.answer_engine import AnswerEngine, classify_desc, generate_combinations
from core.config import AnswerCache, Config


class FakeApi:
    """记录请求并返回预设数据的假接口。"""

    def __init__(self):
        self.secret = "testsecret"
        self.key_session = "testkey"
        self.posts = []   # (path, payload)
        self.gets = []    # (path,)
        self.page_data = []
        self.question_answers = {}  # qid -> [desc, ...] 依次弹出

    def post_json(self, path, payload):
        self.posts.append((path, payload))
        if path.startswith("/scReports/api/wx/netlearning/page/"):
            return {"data": {"list": list(self.page_data)}}
        if path.startswith("/scReports/api/wx/netlearning/answer/"):
            qid = path.rsplit("/", 1)[-1]
            descs = self.question_answers[qid]
            desc = descs.pop(0) if len(descs) > 1 else descs[0]
            return {"data": {"desc": desc}}
        raise AssertionError("unexpected post " + path)

    def get_json(self, path):
        self.gets.append((path,))
        if path.startswith("/scReports/api/wx/netlearning/questions/"):
            return self._questions
        if path.startswith("/scReports/api/wx/netlearning/"):
            return {"data": {}}
        raise AssertionError("unexpected get " + path)


def make_config(tmp, **over):
    import os
    cfg = Config(path=os.path.join(tmp, "config.json"))
    cfg.patch(pages=1, wait_seconds=0, **over)
    return cfg


class TestClassify(unittest.TestCase):
    def test_pass(self):
        for d in ("恭喜你答对了", "回答正确", "通过", "已通过"):
            self.assertEqual(classify_desc(d), "pass", d)

    def test_fail(self):
        for d in ("回答错误", "答案不正确", "答错了", "失败"):
            self.assertEqual(classify_desc(d), "fail", d)

    def test_unknown(self):
        self.assertEqual(classify_desc(""), "unknown")
        self.assertEqual(classify_desc("系统繁忙"), "unknown")


class TestCombinations(unittest.TestCase):
    def test_subset_count(self):
        self.assertEqual(len(generate_combinations(3)), 7)  # 2^3-1
        self.assertEqual(len(generate_combinations(4)), 15)

    def test_all_include_first(self):
        combos = generate_combinations(3)
        self.assertIn([1], combos)
        self.assertIn([1, 2, 3], combos)
        self.assertIn([2, 3], combos)
        self.assertNotIn([], combos)


class TestEngine(unittest.TestCase):
    def _engine(self, tmp, api, **over):
        cfg = make_config(tmp, **over)
        cache = AnswerCache(path=os.path.join(tmp, "cache.json"))
        logs = []

        def on_log(level, text):
            logs.append((level, text))

        engine = AnswerEngine(api, cfg, cache, on_log=on_log, should_stop=lambda: False)
        engine.stats = engine.stats
        return engine, cache, logs

    def test_single_choice_traverse_and_cache(self):
        import tempfile, os
        api = FakeApi()
        api.page_data = [{"id": "a1", "videoUrl": "", "correct": ""}]
        api._questions = {
            "data": {
                "accquieCredit": False, "todayReach": False,
                "questions": [{
                    "id": "q1", "queType": 0,
                    "optionList": [
                        {"id": "o1", "optionContent": "A"},
                        {"id": "o2", "optionContent": "B"},
                    ],
                }],
            }
        }
        api.question_answers = {"q1": ["答案错误", "恭喜回答正确"]}
        with tempfile.TemporaryDirectory() as tmp:
            engine, cache, _ = self._engine(tmp, api)
            stats = engine.run()
            self.assertEqual(stats.questions_passed, 1)
            self.assertEqual(stats.articles_done, 1)
            # 第一个组合失败后继续，第二个成功
            answers = [p for x in api.posts if "/answer/" in x[0] for p in [x[1]]]
            self.assertEqual(answers[0], ["o1"])
            self.assertEqual(answers[1], ["o2"])
            # 缓存已写入
            self.assertIsNotNone(cache.get("testsecret", "testkey", "a1", "q1"))
            self.assertEqual(cache.get("testsecret", "testkey", "a1", "q1"), ["o2"])

    def test_cache_hit_skips_traverse(self):
        import tempfile, os
        api = FakeApi()
        api.page_data = [{"id": "a1", "videoUrl": "", "correct": ""}]
        api._questions = {
            "data": {
                "accquieCredit": False, "todayReach": False,
                "questions": [{
                    "id": "q1", "queType": 0,
                    "optionList": [
                        {"id": "o1", "optionContent": "A"},
                        {"id": "o2", "optionContent": "B"},
                    ],
                }],
            }
        }
        api.question_answers = {"q1": ["恭喜回答正确"]}
        with tempfile.TemporaryDirectory() as tmp:
            engine, cache, _ = self._engine(tmp, api)
            # 预置缓存
            cache.set("testsecret", "testkey", "a1", "q1", ["o2"])
            stats = engine.run()
            self.assertEqual(stats.questions_cached, 1)
            self.assertEqual(stats.questions_passed, 1)
            # 只问答一次，无多次遍历
            answers = [x for x in api.posts if "/answer/" in x[0]]
            self.assertEqual(len(answers), 1)
            self.assertEqual(answers[0][1], ["o2"])

    def test_video_skipped_by_default(self):
        import tempfile, os
        api = FakeApi()
        api.page_data = [{"id": "v1", "videoUrl": "http://x", "correct": ""},
                         {"id": "a1", "videoUrl": "", "correct": "已完成"}]
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, _ = self._engine(tmp, api)
            stats = engine.run()
            self.assertEqual(stats.articles_skipped_video, 1)
            self.assertEqual(stats.articles_skipped_done, 1)
            self.assertEqual(stats.articles_done, 0)

    def test_today_reach_stops(self):
        import tempfile, os
        api = FakeApi()
        api.page_data = [{"id": "a1", "videoUrl": "", "correct": ""}]
        api._questions = {"data": {"accquieCredit": False, "todayReach": True,
                                   "questions": []}}
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, _ = self._engine(tmp, api)
            stats = engine.run()
            self.assertIn("今日", stats.stopped_reason)

    def test_multi_choice_traverse(self):
        import tempfile, os
        api = FakeApi()
        api.page_data = [{"id": "a1", "videoUrl": "", "correct": ""}]
        api._questions = {
            "data": {
                "accquieCredit": False, "todayReach": False,
                "questions": [{
                    "id": "q1", "queType": 1,
                    "optionList": [
                        {"id": "o1", "optionContent": "A"},
                        {"id": "o2", "optionContent": "B"},
                    ],
                }],
            }
        }
        api.question_answers = {
            "q1": ["答案错误", "答案错误", "恭喜回答正确"]
        }
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, _ = self._engine(tmp, api)
            stats = engine.run()
            self.assertEqual(stats.questions_passed, 1)
            answers = [p for x in api.posts if "/answer/" in x[0] for p in [x[1]]]
            # 顺序: [o1] [o2] [o1,o2]? 回溯顺序: [1],[1,2],[2]
            self.assertEqual(answers[0], ["o1"])
            self.assertEqual(answers[1], ["o1", "o2"])
            self.assertEqual(answers[2], ["o2"])


if __name__ == "__main__":
    unittest.main()
