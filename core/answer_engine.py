# -*- coding: utf-8 -*-
"""答题引擎：翻页拉文章 → 过滤 → 逐题作答 → 汇总。

判定策略沿用原项目思路：靠接口返回的文字（错误/恭喜等）判断对错，
并增加答案缓存，已答对的题下次直接提交正确答案，一次通过。
"""
import time

from .api_client import ApiClient, ApiError, LIST_PAYLOAD, PATH_ANSWER, PATH_OPEN, PATH_PAGE, PATH_QUESTIONS
from .config import AnswerCache, Config
from .result import RunStats

# 判定关键词：先看否定（避免"不正确"含"正确"子串的误判），再看肯定
ACCEPT_KEYS = ("恭喜", "回答正确", "答对了", "已通过", "通过")
REJECT_KEYS = ("错误", "不正确", "答错", "不对", "失败")


def classify_desc(desc: str) -> str:
    """根据接口返回文案分类：pass / fail / unknown。"""
    if not desc:
        return "unknown"
    if any(k in desc for k in REJECT_KEYS):
        return "fail"
    if any(k in desc for k in ACCEPT_KEYS):
        return "pass"
    return "unknown"


def generate_combinations(n: int) -> list[list[int]]:
    """生成 1..n 的所有非空子集（回溯法），多选遍历用。"""
    result = []

    def backtrack(start: int, path: list[int]) -> None:
        if path:
            result.append(list(path))
        for i in range(start, n + 1):
            path.append(i)
            backtrack(i + 1, path)
            path.pop()

    backtrack(1, [])
    return result


class AnswerEngine:
    """一次运行的核心执行器；通过 on_log 回调输出、should_stop 支持停止。"""

    def __init__(self, api: ApiClient, config: Config, cache: AnswerCache,
                 on_log=None, should_stop=None, on_progress=None):
        self.api = api
        self.config = config
        self.cache = cache
        self.on_log = on_log or (lambda level, text: None)
        self.should_stop = should_stop or (lambda: False)
        self.on_progress = on_progress or (lambda cur, total, article_id: None)
        self.stats = RunStats()
        self._global_stop = False  # 今日已达等接口级停止

    # ---------- 对外入口 ----------

    def run(self) -> RunStats:
        pages = max(1, int(self.config.get("pages", 2) or 2))
        try_video = bool(self.config.get("try_video", False))
        self.on_log("info", "开始刷题：搜索前 {} 页，{}视频文章".format(
            pages, "尝试" if try_video else "跳过"))
        for page in range(1, pages + 1):
            if self._stop_now():
                break
            try:
                payload = dict(LIST_PAYLOAD)
                data = self.api.post_json(PATH_PAGE.format(page=page, size=10), payload)
            except ApiError as e:
                self.on_log("error", "第 {} 页文章列表获取失败：{}".format(page, e))
                self.stats.add_failure("page{}".format(page), str(e))
                if e.kind in ("http", "credential"):
                    self.stats.stopped_reason = "接口异常，已停止（请检查凭据）"
                    break
                continue
            articles = (data.get("data") or {}).get("list") or []
            if not articles:
                self.on_log("info", "第 {} 页没有文章，停止搜索".format(page))
                break
            self.stats.articles_scanned += len(articles)
            self.on_log("info", "第 {} 页共 {} 篇文章".format(page, len(articles)))
            for idx, article in enumerate(articles, start=1):
                if self._stop_now():
                    break
                aid = str(article.get("id", ""))
                self.on_progress(idx, len(articles), aid)
                is_video = bool(article.get("videoUrl"))
                if is_video and not try_video:
                    self.stats.articles_skipped_video += 1
                    self.on_log("warn", "文章 {}：视频类型，跳过（可在设置中勾选尝试）".format(aid))
                    continue
                if article.get("correct") == "已完成":
                    self.stats.articles_skipped_done += 1
                    self.on_log("info", "文章 {}：已完成，跳过".format(aid))
                    continue
                self._try_learn(aid, credits=article.get("credits"))
                if self._global_stop:  # 今日已达：整体停止
                    break
        return self.stats

    # ---------- 内部实现 ----------

    def _stop_now(self) -> bool:
        return self._global_stop or self.should_stop()

    def _try_learn(self, article_id: str, credits=None) -> None:
        """学习并作答一篇文章，异常时记录失败但不中断整体。"""
        try:
            mark = "（预计 {} 分）".format(credits) if credits else ""
            self.on_log("info", "── 学习文章 {}{} ──".format(article_id, mark))
            self._learn(article_id)
        except ApiError as e:
            self.on_log("error", "文章 {} 处理失败：{}".format(article_id, e))
            self.stats.add_failure(article_id, str(e))
        except Exception as e:  # 兜底：任何意外都不中断整轮
            self.on_log("error", "文章 {} 处理异常：{}".format(article_id, repr(e)))
            self.stats.add_failure(article_id, repr(e))

    def _learn(self, article_id: str) -> None:
        wait = max(0, int(self.config.get("wait_seconds", 3) or 0))
        if wait:
            time.sleep(wait)
        resp = self.api.get_json(PATH_OPEN.format(article_id=article_id))
        if not isinstance(resp, dict) or not isinstance(resp.get("data"), dict):
            self.on_log("warn", "文章 {}：打开接口返回结构异常".format(article_id))
        questions_data = self.api.get_json(PATH_QUESTIONS.format(article_id=article_id))
        data = (questions_data or {}).get("data") or {}
        if data.get("accquieCredit") is True:
            self.on_log("info", "文章 {}：已经作答过，跳过".format(article_id))
            self.stats.articles_skipped_done += 1
            return
        if data.get("todayReach") is True:
            reason = "今日积分已达标，停止刷题（第二课堂每日上限）"
            self.on_log("success", reason)
            self.stats.stopped_reason = reason
            self._global_stop = True
            return
        questions = data.get("questions") or []
        if not questions:
            self.on_log("warn", "文章 {}：没有题目，不加分".format(article_id))
            return
        self.stats.questions_total += len(questions)
        all_passed = True
        for question in questions:
            if self._stop_now():
                return
            ok = self._answer_question(article_id, question)
            if not ok:
                all_passed = False
        if all_passed:
            self.stats.articles_done += 1
            self.on_log("success", "文章 {} 全部题目通过".format(article_id))
        else:
            self.on_log("warn", "文章 {} 存在未通过的题目".format(article_id))
            self.stats.add_failure(article_id, "存在未通过的题目")

    def _answer_question(self, article_id: str, question: dict) -> bool:
        """作答单题；返回是否通过。"""
        qid = str(question.get("id", ""))
        opt_list = question.get("optionList") or []
        qtype = question.get("queType")
        options = list(opt_list)
        if not options:
            self.on_log("warn", "题目 {}：没有选项，跳过".format(qid))
            return False

        # 1) 优先命中缓存：直接提交正确答案
        cached = self.cache.get(self.api.secret, self.api.key_session, article_id, qid)
        if cached:
            ids = [oid for oid in cached if oid in {o.get("id") for o in options}]
            if ids:
                self.stats.questions_cached += 1
                self.on_log("info", "题目 {}：命中缓存答案，直接提交".format(qid))
                res = self._submit(qid, ids)
                if res == "pass":
                    self.stats.questions_passed += 1
                    self.on_log("success", "题目 {}：缓存答案有效".format(qid))
                    return True
                elif res == "unknown":
                    self.stats.questions_unknown += 1
                    self.on_log("warn", "题目 {}：缓存提交结果无法判定".format(qid))
                    return False
                # fail：缓存失效，清除后重新遍历
                self.cache.clear_question(self.api.secret, self.api.key_session, article_id, qid)
                self.on_log("warn", "题目 {}：缓存答案失效，重新遍历".format(qid))

        # 2) 未命中缓存：按类型遍历选项
        if qtype == 1:  # 多选
            combos = generate_combinations(len(options))
            order = combos  # 从小到大
        else:           # 单选（含其他未知类型兜底）
            order = [[i + 1] for i in range(len(options))]

        self.on_log("info", "题目 {}：共 {} 个选项，开始遍历试错".format(qid, len(options)))
        for combo in order:
            if self._stop_now():
                return False
            chosen = [options[i - 1] for i in combo]
            ids = [c.get("id") for c in chosen]
            names = [c.get("optionContent", "") for c in chosen]
            self.on_log("info", "  试答：{}".format("、".join(str(n) for n in names) or "(空)"))
            res = self._submit(qid, ids)
            if res == "pass":
                self.stats.questions_passed += 1
                self.cache.set(self.api.secret, self.api.key_session, article_id, qid, ids)
                self.on_log("success", "题目 {}：通过".format(qid))
                return True
            if res == "unknown":
                self.stats.questions_unknown += 1
                self.on_log("warn", "题目 {}：回复无法判定，终止该题".format(qid))
                return False
            # fail → 继续下一组合
        self.on_log("warn", "题目 {}：所有组合均未通过".format(qid))
        return False

    def _submit(self, qid: str, option_ids: list) -> str:
        """提交一次作答，返回 pass / fail / unknown。"""
        try:
            res = self.api.post_json(PATH_ANSWER.format(question_id=qid), option_ids)
        except ApiError as e:
            self.on_log("error", "题目 {}：提交失败 {}".format(qid, e))
            return "unknown"
        desc = ""
        try:
            desc = str((res.get("data") or {}).get("desc", ""))
        except Exception:
            pass
        kind = classify_desc(desc)
        if desc:
            self.on_log("debug", "  接口回执：{}".format(desc))
        return kind
