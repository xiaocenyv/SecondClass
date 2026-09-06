# -*- coding: utf-8 -*-
"""实验性自动登录：合肥工业大学统一身份认证（one.hfut.edu.cn）。

学校登录页为 CAS 形态：
  * 密码使用 AES-ECB/PKCS7 加密，密钥来自 cookie LOGIN_FLAVORING
    （页面 JS 从 /cas/checkInitParams 等接口获取后写入 cookie）；
  * 图形验证码图片接口：/cas/vercode?time=<随机>；
  * 登录表单：username(明文) / password(加密) / capcha / execution / _eventId / codeRandom 等。

本模块自动登录统一认证并拿到会话。登录成功后能否直接换取「第二课堂」接口凭据
需要真机验证：若可行则可免抓包；若接口仍要求 key_session/secret（由微信小程序
运行时签发），则本模块会如实报告不可行，主流程回退抓包方式。
"""
import base64
import random
import re
from urllib.parse import urljoin

import requests

CAS_ORIGIN = "https://one.hfut.edu.cn"
LOGIN_URL = CAS_ORIGIN + "/cas/login"
CHECK_INIT_URL = CAS_ORIGIN + "/cas/checkInitParams"

# 登录表单字段名（与页面一致）
FIELD_USERNAME = "username"
FIELD_PASSWORD = "password"
FIELD_CAPTCHA = "capcha"
FIELD_DYNAMIC_CAPTCHA = "dynamicCapcha"
FIELD_EXECUTION = "execution"
FIELD_EVENT_ID = "_eventId"
FIELD_GEOLOCATION = "geolocation"
FIELD_CODE_RANDOM = "codeRandom"


class AutoLoginError(Exception):
    """自动登录过程中的可读错误。"""


def aes_ecb_encrypt(key: str, plaintext: str) -> str:
    """与页面 CryptoJS AES.encrypt(utf8, key, ECB/Pkcs7) 等价：返回 base64。"""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    key_bytes = key.encode("utf-8")
    if len(key_bytes) not in (16, 24, 32):
        raise AutoLoginError("加密密钥长度异常（{} 字节，应为 16/24/32），登录协议可能已变更".format(
            len(key_bytes)))
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(encrypted).decode("ascii")


def _find_logging_flavoring(session: requests.Session) -> str | None:
    """多路尝试获取 AES 密钥（LOGIN_FLAVORING）。"""
    # 1) 已有 cookie
    for c in session.cookies:
        if c.name.upper() == "LOGIN_FLAVORING":
            return c.value
    # 2) checkInitParams 接口（页面 JS 调用它得到 codeRandom 等）
    for method in ("get", "post"):
        try:
            r = session.request(method, CHECK_INIT_URL, timeout=10,
                                headers={"Referer": LOGIN_URL})
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                data = r.json()
                for key in ("logingFlavoring", "loginFlavoring", "flavoring", "secretKey"):
                    v = data.get(key)
                    if v:
                        session.cookies.set("LOGIN_FLAVORING", str(v),
                                            domain="one.hfut.edu.cn")
                        return str(v)
        except Exception:
            continue
    return None


def _extract_field(html: str, field_id: str) -> str:
    """从登录页提取隐藏字段值（如 execution）。"""
    m = re.search(r'id=[\'"]{}[\'"][^>]*value=[\'"]([^\'"]*)[\'"]'.format(field_id), html)
    if m:
        return m.group(1)
    m = re.search(r'name=[\'"]{}[\'"][^>]*value=[\'"]([^\'"]*)[\'"]'.format(field_id), html)
    return m.group(1) if m else ""


def _extract_form_action(html: str, page_url: str) -> str:
    m = re.search(r'<form[^>]*action=[\'"]([^\'"]*)[\'"]', html, re.I)
    action = m.group(1) if m else "login"
    return urljoin(page_url, action)


def attempt_auto_login(username: str, password: str, code_reader,
                       on_log=None) -> dict:
    """尝试自动登录。

    参数:
      username / password: 统一认证账号密码（密码仅在内存中用于一次加密）。
      code_reader: 回调 code_reader(png_bytes, hint) -> 用户输入的验证码字符串。
      on_log: 可选日志回调 (level, text)。

    返回: {"ok": bool, "message": str, "session": requests.Session|None}
    """
    log = on_log or (lambda level, text: None)
    if not username or not password:
        return {"ok": False, "message": "账号或密码为空", "session": None}

    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        # 1) 打开登录页，拿会话 cookie 与表单字段
        log("info", "打开统一认证登录页…")
        r = s.get(LOGIN_URL, timeout=15)
        if r.status_code != 200:
            return {"ok": False, "message": "登录页返回 HTTP {}".format(r.status_code),
                    "session": None}
        html = r.text
        action = _extract_form_action(html, r.url)
        execution = _extract_field(html, FIELD_EXECUTION)
        if not execution:
            return {"ok": False, "message": "登录页未解析到 execution 字段，登录协议可能已变更",
                    "session": None}
        log("debug", "表单 action={}，execution={}".format(action, execution))

        # 2) 获取 AES 密钥
        key = _find_logging_flavoring(s)
        if not key:
            return {"ok": False, "message": "未获取到加密密钥（LOGIN_FLAVORING），登录协议可能已变更",
                    "session": None}
        log("debug", "已获取加密密钥（长度 {}）".format(len(key)))

        # 3) 获取图形验证码
        vercode_url = urljoin(r.url, "vercode?time={}".format(random.random()))
        img = s.get(vercode_url, timeout=15)
        if img.status_code != 200 or not img.content:
            return {"ok": False, "message": "验证码图片获取失败（HTTP {}）".format(img.status_code),
                    "session": None}
        log("info", "验证码已加载，请输入图片中的字符…")
        code = (code_reader(img.content, "请输入统一认证登录验证码") or "").strip()
        if not code:
            return {"ok": False, "message": "未输入验证码，已取消", "session": None}

        # 4) 提交登录
        enc_pwd = aes_ecb_encrypt(key, password)
        payload = {
            FIELD_USERNAME: username,
            FIELD_PASSWORD: enc_pwd,
            FIELD_CAPTCHA: code,
            FIELD_DYNAMIC_CAPTCHA: "",
            FIELD_EXECUTION: execution,
            FIELD_EVENT_ID: "submit",
            FIELD_GEOLOCATION: "",
            FIELD_CODE_RANDOM: s.cookies.get("codeRandom") or "",
        }
        log("info", "提交登录表单…")
        r2 = s.post(action, data=payload, timeout=20, allow_redirects=False,
                    headers={"Referer": r.url,
                             "Origin": CAS_ORIGIN,
                             "Content-Type": "application/x-www-form-urlencoded"})
        if r2.status_code in (301, 302, 303, 307, 308):
            loc = r2.headers.get("Location", "")
            # 跟随重定向拿最终会话，但仅作为成功信号
            s.get(urljoin(action, loc) if loc.startswith("/") else loc, timeout=15)
            log("success", "登录成功（已跳转 {}）".format(loc[:80]))
            return {"ok": True, "message": "统一认证登录成功", "session": s}
        if r2.status_code == 200:
            msg = _extract_login_error(r2.text)
            return {"ok": False, "message": "登录失败：{}".format(msg or "账号/密码或验证码不正确"),
                    "session": None}
        return {"ok": False, "message": "登录接口返回 HTTP {}".format(r2.status_code),
                "session": None}
    except AutoLoginError as e:
        return {"ok": False, "message": str(e), "session": None}
    except requests.RequestException as e:
        return {"ok": False, "message": "网络异常：{}".format(str(e)[:200]), "session": None}
    except Exception as e:  # 兜底：反馈可读信息
        return {"ok": False, "message": "自动登录异常：{}".format(repr(e)), "session": None}


def _extract_login_error(html: str) -> str:
    """从 200 响应页面中提取错误信息。"""
    for pat in (
        r'id=["\']error(?:username|password|code)["\'](?:[^>]*>)([^<]*)',
        r'class=["\'][^"\']*mess[^"\']*["\'][^>]*>([^<]{2,80})',
    ):
        m = re.search(pat, html)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def verify_session_for_dekt(session: requests.Session) -> str:
    """用统一认证会话探测第二课堂网页端是否可用。

    返回结论文案（仅诊断用；dekt 仅校内网可达时结果为"网络不可达"）。
    注意：第二课堂小程序接口的 key_session/secret 是否可由网页会话免签，
    必须真机验证后才能确定。
    """
    try:
        r = session.get("https://dekt.hfut.edu.cn/", timeout=12)
        return "第二课堂站点可访问（HTTP {}）".format(r.status_code)
    except Exception as e:
        return "第二课堂站点不可达（{}）".format(str(e)[:120])
