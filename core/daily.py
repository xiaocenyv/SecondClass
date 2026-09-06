# -*- coding: utf-8 -*-
"""每日自动刷题流程：检测今日积分 → 未达标则刷 → 通知结果 → 写结果文件。"""
import datetime
import json
import os
import time
from pathlib import Path

from .api_client import ApiClient, ApiError, LIST_PAYLOAD, PATH_QUESTIONS
from .answer_engine import AnswerEngine
from .config import AnswerCache, Config, data_dir, log_to_file
from .notify import notify

RESULT_FILE = os.path.join(data_dir(), "daily_result.json")


def check_today(api: ApiClient) -> bool | None:
    """轻量检测今日是否已达标。True=达标；False=未达标；None=无法判断。"""
    try:
        import json as _json
        data = api.post_json(
            "/scReports/api/wx/netlearning/page/1/10", dict(LIST_PAYLOAD))
        lst = (data.get("data") or {}).get("list") or []
        # 选第一篇有题目的文章来探测
        for a in lst:
            if not a.get("videoUrl") and a.get("correct") != "已完成":
                q = api.get_json(PATH_QUESTIONS.format(article_id=a.get("id")))
                d = (q.get("data") or {})
                if isinstance(d, dict):
                    return bool(d.get("todayReach"))
        # 全部已完成：无可探测文章 → 视为已完成状态（无新文章）
        return True
    except Exception:
        return None


def run_daily(config: Config, mode: str | None = None) -> dict:
    """自动刷题一次；返回结果 dict。

    结果状态：
      completed     今日达标（本次刷完或此前已达标）
      failed        未完成（附原因）
      no-credentials 未配置凭据
    """
    on_fail_notify = bool(config.get("notify_on_fail", True))
    mode = mode or config.get("notify_mode", "banner")
    ks = config.get("key_session", "")
    secret = config.get("secret", "")
    result = {"time": datetime.datetime.now().isoformat(timespec="seconds"),
              "status": "failed", "detail": "", "articles": 0, "questions": 0}

    if not ks or not secret:
        result["status"] = "no-credentials"
        result["detail"] = "未配置凭据（请打开软件完成抓包）"
        log_to_file("daily", result["detail"])
        notify("第二课堂自动刷题", "未配置凭据，请打开 SecondClass 完成一次抓包",
               mode, record=False)
        return result

    def log(level, text):
        log_to_file("daily", text)

    api = ApiClient(ks, secret)
    cache = AnswerCache()
    try:
        today = check_today(api)
    except Exception as e:
        today = None
        log("警告：今日状态检测失败 {}".format(repr(e)))

    if today is True:
        result.update(status="completed", detail="今日 2 分已达成（此前已完成）")
        notify("第二课堂自动刷题", "今日 2 分已达成，无需重复刷题", mode)
        _write_result(result)
        return result

    if today is None:
        # 检测失败，仍尝试刷（引擎在取题时会再次确认 todayReach）
        log("今日状态未知，继续尝试刷题")

    try:
        engine = AnswerEngine(api, config, cache,
                              on_log=lambda lv, tx: log(lv, tx),
                              should_stop=lambda: False)
        stats = engine.run()
    except Exception as e:
        result["detail"] = "运行异常：{}".format(repr(e))
        log("异常：{}".format(repr(e)))
        if on_fail_notify:
            notify("第二课堂自动刷题", "今日未完成（异常）：{}".format(result["detail"]),
                   mode)
        _write_result(result)
        return result

    result["articles"] = stats.articles_done
    result["questions"] = stats.questions_passed
    reason = stats.stopped_reason or ""
    if "今日" in reason:
        result.update(status="completed",
                      detail="今日 2 分已达成（本轮完成 {} 篇 / {} 题）".format(
                          stats.articles_done, stats.questions_passed))
        notify("第二课堂自动刷题", "今日 2 分已达成！完成 {} 篇 / {} 题".format(
            stats.articles_done, stats.questions_passed), mode)
    elif stats.failures:
        why = stats.failures[0][1][:120]
        result["detail"] = "未完成：{}".format(why)
        if on_fail_notify:
            notify("第二课堂自动刷题", "今日未完成：{}".format(why), mode)
    elif stats.articles_done > 0:
        result.update(status="completed",
                      detail="今日完成 {} 篇 / {} 题".format(
                          stats.articles_done, stats.questions_passed))
        notify("第二课堂自动刷题", "今日 2 分已完成！完成 {} 篇 / {} 题".format(
            stats.articles_done, stats.questions_passed), mode)
    else:
        result["detail"] = "无新文章或全部已完成"
        notify("第二课堂自动刷题", "今日无可刷的新文章（可能已全部完成）", mode)
    _write_result(result)
    return result


def _write_result(result: dict) -> None:
    try:
        # 保留最近 30 条
        prev = []
        try:
            with open(RESULT_FILE, "r", encoding="utf-8") as f:
                prev = json.load(f)
        except (FileNotFoundError, ValueError):
            prev = []
        prev = (prev + [result])[-30:]
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(prev, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def read_results(limit: int = 5) -> list[dict]:
    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data[-limit:]
    except (FileNotFoundError, ValueError):
        return []
