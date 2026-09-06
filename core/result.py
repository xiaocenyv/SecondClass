# -*- coding: utf-8 -*-
"""运行结果的数据结构。"""
from dataclasses import dataclass, field


@dataclass
class RunStats:
    """一次刷题运行的统计汇总。"""

    articles_scanned: int = 0        # 扫描到的文章数
    articles_done: int = 0           # 本次完成答题文章数
    articles_skipped_done: int = 0   # 之前已完成跳过的
    articles_skipped_video: int = 0  # 视频跳过的
    questions_total: int = 0         # 遇到的题目总数
    questions_passed: int = 0        # 通过的题目数
    questions_cached: int = 0        # 命中缓存的题目数
    questions_unknown: int = 0       # 无法判定结果的题目数
    stopped_reason: str = ""         # 停止原因（空=自然结束）
    failures: list = field(default_factory=list)  # [(文章id, 原因)]

    def add_failure(self, article_id: str, reason: str) -> None:
        self.failures.append((article_id, reason))

    def summary(self) -> str:
        lines = [
            "========== 本次运行汇总 ==========",
            "扫描文章：{} 篇".format(self.articles_scanned),
            "本次完成：{} 篇（跳过已完成的 {} 篇，跳过视频 {} 篇）".format(
                self.articles_done, self.articles_skipped_done,
                self.articles_skipped_video),
            "题目通过：{} / {}（其中命中缓存 {} 题，无法判定 {} 题）".format(
                self.questions_passed, self.questions_total,
                self.questions_cached, self.questions_unknown),
        ]
        if self.stopped_reason:
            lines.append("停止原因：{}".format(self.stopped_reason))
        else:
            lines.append("停止原因：全部扫描完成")
        if self.failures:
            lines.append("未正常完成的条目：")
            for aid, why in self.failures[:10]:
                lines.append("  - {}".format(why))
        lines.append("请到第二课堂小程序「网络学习」中查看积分到账情况。")
        return "\n".join(lines)
