# -*- coding: utf-8 -*-
"""第二课堂小程序接口客户端：请求头、超时、重试与异常分类。"""
import json
import time

import requests

API_BASE = "https://dekt.hfut.edu.cn"

# 路径常量集中管理，接口变动只改这里
PATH_PAGE = "/scReports/api/wx/netlearning/page/{page}/{size}"
PATH_OPEN = "/scReports/api/wx/netlearning/{article_id}"
PATH_QUESTIONS = "/scReports/api/wx/netlearning/questions/{article_id}"
PATH_ANSWER = "/scReports/api/wx/netlearning/answer/{question_id}"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/8431"
)

# 列表接口的固定请求体
LIST_PAYLOAD = {"category": "", "columnType": "0"}


class ApiError(Exception):
    """可读的接口异常，kind 用于分类展示。"""

    def __init__(self, kind: str, message: str, detail: str = ""):
        super().__init__(message)
        self.kind = kind  # network / timeout / http / credential / parse
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return "{}（{}）".format(self.message, self.detail)
        return self.message


class ApiClient:
    """封装小程序接口的请求方式，失败自动重试一次网络类错误。"""

    def __init__(self, key_session: str, secret: str, timeout: int = 15):
        self.key_session = key_session
        self.secret = secret
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Host": "dekt.hfut.edu.cn",
            "Connection": "keep-alive",
            "secret": secret,
            "key_session": key_session,
            "xweb_xhr": "1",
            "User-Agent": DEFAULT_UA,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://servicewechat.com/wx1e3feaf804330562/89/page-frame.html",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def _request(self, method: str, url: str, **kw) -> requests.Response:
        last_err = None
        for attempt in (1, 2):  # 网络类错误自动重试一次
            try:
                return self.session.request(method, url, timeout=self.timeout, **kw)
            except requests.Timeout as e:
                last_err = ApiError("timeout", "请求超时（{}）".format(url))
                last_err.detail = str(e)
            except requests.ConnectionError as e:
                last_err = ApiError("network", "网络连接失败（{}）".format(url))
                last_err.detail = str(e)[:200]
            if attempt == 1:
                time.sleep(1)
        raise last_err

    def get_json(self, path: str) -> dict:
        url = API_BASE + path
        resp = self._request("GET", url)
        return self._parse(resp, url)

    def post_json(self, path: str, payload: dict) -> dict:
        url = API_BASE + path
        resp = self._request("POST", url, data=json.dumps(payload))
        return self._parse(resp, url)

    def _parse(self, resp: requests.Response, url: str) -> dict:
        if resp.status_code != 200:
            raise ApiError("http", "接口返回 HTTP {}".format(resp.status_code),
                           "{}（body: {}）".format(url, resp.text[:120]))
        try:
            return resp.json()
        except ValueError as e:
            raise ApiError("parse", "接口返回内容不是有效 JSON", url) from e

    def check_credentials(self) -> tuple[bool, str]:
        """探测凭据是否有效：调一次列表接口看结构。

        返回 (是否有效, 说明文案)。
        """
        try:
            data = self.post_json(PATH_PAGE.format(page=1, size=1), dict(LIST_PAYLOAD))
        except ApiError as e:
            if e.kind in ("network", "timeout"):
                return False, "网络异常：{}".format(e.message)
            return False, "接口异常：{}".format(e)
        if not isinstance(data, dict) or "data" not in data:
            return False, "接口结构异常（无 data 字段），可能凭据过期或接口变更"
        d = data.get("data")
        if not isinstance(d, dict) or "list" not in d:
            return False, "接口结构异常（无 list 字段），可能凭据过期或接口变更"
        return True, "凭据有效，会话正常"
