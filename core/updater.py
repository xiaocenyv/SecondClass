# -*- coding: utf-8 -*-
"""检查更新：从 GitHub Releases 读取最新版本（匿名 API + 本地缓存，失败静默）。"""
import json
import os
import time

import requests

from .config import data_dir

CACHE_FILE = os.path.join(data_dir(), "update_cache.json")
CACHE_TTL = 24 * 3600  # 24 小时内不重复查询（匿名 API 有 60 次/时限流）


def parse_version(tag: str) -> tuple:
    """把 'v2.0.0' / '2.0.0' 解析为 (2, 0, 0)。"""
    parts = []
    for p in tag.lstrip("vV").split("."):
        nums = ""
        for ch in p:
            if ch.isdigit():
                nums += ch
            else:
                break
        parts.append(int(nums) if nums else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_latest(repo: str, force: bool = False) -> dict | None:
    """查询最新 Release 版本。

    返回 {"version": "v2.0.0", "url": "..."} 或 None（未配置/网络失败/无 release）。
    force=False 时命中 24h 缓存直接返回缓存结果。
    """
    if not repo or "/" not in repo:
        return None
    cache = None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("repo") == repo and not force:
            if time.time() - cache.get("time", 0) < CACHE_TTL:
                return cache.get("result")
    except (FileNotFoundError, ValueError):
        cache = None
    try:
        r = requests.get("https://api.github.com/repos/{}/releases/latest".format(repo),
                         headers={"Accept": "application/vnd.github+json",
                                  "User-Agent": "SecondClass"},
                         timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        result = {"version": data.get("tag_name", ""),
                  "url": data.get("html_url", "")}
    except requests.RequestException:
        return None
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"repo": repo, "time": time.time(), "result": result},
                      f, ensure_ascii=False)
    except Exception:
        pass
    return result
