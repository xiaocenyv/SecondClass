# -*- coding: utf-8 -*-
"""配置与答案缓存的本地存取（%APPDATA%/SecondClass，仅存本机）。"""
import json
import os
import threading

APP_NAME = "SecondClass"

DEFAULTS = {
    "key_session": "",
    "secret": "",
    "pages": 2,               # 搜索文章的最大页码
    "try_video": False,       # 是否尝试视频类文章
    "wait_seconds": 3,        # 每篇文章作答前的等待秒数（防频繁请求，可设 0）
    "remember_credentials": True,
    "auto_login_username": "",  # 只记用户名，绝不保存密码
    "github_repo": "xiaocenyv/SecondClass",  # 检查更新用
    "last_update_check": 0,     # 上次检查更新的时间戳
    "auto_daily_enabled": False,  # 每日自动刷题总开关
    "auto_daily_time": "12:30",   # 每天固定时间
    "auto_login_trigger": True,   # 开机登录触发
    "notify_mode": "banner",      # banner / popup / log
    "notify_on_fail": True,       # 失败时也通知
}


def data_dir() -> str:
    """返回数据目录（Windows: %APPDATA%/SecondClass；其他平台: ~/.secondclass）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    return os.path.join(data_dir(), "config.json")


def cache_path() -> str:
    return os.path.join(data_dir(), "answer_cache.json")


def logs_dir() -> str:
    d = os.path.join(data_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def _today_log() -> str:
    import datetime
    return os.path.join(logs_dir(),
                        datetime.date.today().strftime("%Y%m%d") + ".log")


def log_to_file(level: str, text: str) -> None:
    """把一条日志追加到当日日志文件（GUI 每次 _log 时调用）。"""
    try:
        import datetime
        line = "[{}] [{}] {}\n".format(datetime.datetime.now().strftime("%H:%M:%S"),
                                       level, text)
        with open(_today_log(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # 日志写失败不影响主流程


class Config:
    """线程安全的配置存取，落后于磁盘的读写通过锁保护。"""

    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._path = path or config_path()
        self._data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    # 只接受已知键，防止脏文件
                    self._data = {k: loaded.get(k, v) for k, v in DEFAULTS.items()}
            except FileNotFoundError:
                pass
            except Exception:
                # 配置损坏时保留默认值，不崩溃
                self._data = dict(DEFAULTS)

    def save(self) -> None:
        with self._lock:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = value

    def patch(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)


class AnswerCache:
    """答案缓存：{隔离键: {文章id: {题目id: [选项id,...]}}}。

    隔离键由 secret 与 key_session 生成，换账号自动隔离，互不串用。
    """

    def __init__(self, path: str | None = None):
        self._path = path or cache_path()
        self._lock = threading.Lock()
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                self._data = d
        except (FileNotFoundError, ValueError):
            self._data = {}

    def _save(self) -> None:
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self._path)
        except Exception:
            pass  # 缓存写失败不影响主流程

    @staticmethod
    def isolation_key(secret: str, key_session: str) -> str:
        """用 secret 的 crc32 与 key_session 前缀生成隔离键。"""
        import zlib
        s = "{}:{}".format(secret, key_session[:8])
        return "%08x" % (zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF)

    def get(self, secret: str, key_session: str, article_id: str, question_id: str):
        """返回缓存中的正确选项 id 列表，无则 None。"""
        with self._lock:
            return self._data.get(self.isolation_key(secret, key_session), {}).get(
                article_id, {}).get(question_id)

    def set(self, secret: str, key_session: str, article_id: str,
            question_id: str, option_ids: list) -> None:
        with self._lock:
            ik = self.isolation_key(secret, key_session)
            self._data.setdefault(ik, {}).setdefault(article_id, {})[question_id] = list(option_ids)
            self._save()

    def clear_question(self, secret: str, key_session: str,
                       article_id: str, question_id: str) -> None:
        """清除单题的缓存（缓存答案被判定失效时使用）。"""
        with self._lock:
            art = self._data.get(self.isolation_key(secret, key_session), {}).get(article_id)
            if art and question_id in art:
                del art[question_id]
                self._save()
