# -*- coding: utf-8 -*-
"""主窗口：凭据设置、运行参数、一键登录、开始/停止、日志与汇总。"""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from core.api_client import ApiClient
from core.answer_engine import AnswerEngine
from core.auto_login import attempt_auto_login
from core.config import AnswerCache, Config, log_to_file
from gui.tutorial import TutorialWindow
from gui.worker import Worker

APP_TITLE = "第二课堂自动刷题（SecondClass）"
APP_VERSION = "2.0"

LOG_TAG = {"info": ("#333333", ""), "debug": ("#888888", ""),
           "success": ("#1a7f37", "bold"), "warn": ("#b8860b", ""),
           "error": ("#b3261e", "bold")}


class MainWindow:
    def __init__(self, root: tk.Tk, config: Config):
        self.root = root
        self.config = config
        self.cache = AnswerCache()
        self.worker: Worker | None = None
        self._captcha_q: queue.Queue = queue.Queue()
        self._captcha_tl: tk.Toplevel | None = None

        root.title("{} v{}".format(APP_TITLE, APP_VERSION))
        root.geometry("900x700")
        root.minsize(800, 620)

        self._apply_theme(root)
        self._build_ui()
        self._load_config_into_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_messages)
        self.root.after(150, self._drain_captcha)

        # 首次向导：尚未配置凭据时自动弹出配置向导
        if not config.get("key_session", "") or not config.get("secret", ""):
            self.root.after(500, self._open_wizard)
        # 检查更新（有 github_repo 配置时，后台静默查询）
        github_repo = config.get("github_repo", "")
        if github_repo:
            self.root.after(1500, lambda: self._check_update_async(github_repo))

    # ---------------- 主题 ----------------

    def _apply_theme(self, root: tk.Tk):
        style = ttk.Style(root)
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass
        BG = "#f5f6fa"
        CARD = "#ffffff"
        PRIMARY = "#1f6fb2"
        PRIMARY_DARK = "#1a5f99"
        TEXT = "#2b2d33"
        SUB = "#8a8f98"
        BORDER = "#dfe3ea"
        root.configure(bg=BG)
        style.configure(".", background=BG, foreground=TEXT,
                        font=("Microsoft YaHei", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TRadiobutton", background=BG, foreground=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.configure("TLabelframe", background=BG, bordercolor=BORDER,
                        relief="solid")
        style.configure("TLabelframe.Label", background=BG, foreground=PRIMARY,
                        font=("Microsoft YaHei", 10, "bold"))
        style.configure("TButton", background=PRIMARY, foreground="#ffffff",
                        padding=(14, 7), borderwidth=0, focusthickness=0,
                        focuscolor=PRIMARY)
        style.map("TButton",
                  background=[("active", PRIMARY_DARK), ("pressed", PRIMARY_DARK),
                              ("disabled", "#9fb8d0")],
                  foreground=[("disabled", "#eef3f8")])
        style.configure("Danger.TButton", background="#b3261e",
                        foreground="#ffffff")
        style.map("Danger.TButton",
                  background=[("active", "#8f1d15"), ("disabled", "#d0a3a0")])
        style.configure("Ghost.TButton", background=CARD, foreground=PRIMARY,
                        borderwidth=1)
        style.map("Ghost.TButton",
                  background=[("active", "#e8eef5")],
                  foreground=[("active", PRIMARY)])
        style.configure("TEntry", fieldbackground="#ffffff", bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, padding=4)
        style.configure("TSpinbox", fieldbackground="#ffffff", bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, padding=2)
        style.configure("TLabelframe", bordercolor=BORDER)

    # ---------------- UI 构建 ----------------

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        # 顶部标题栏
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="第二课堂自动刷题", font=("Microsoft YaHei", 15, "bold"),
                  foreground="#1f6fb2").pack(side="left")
        ttk.Label(top, text="  · 每日 2 分自动搞定",
                  foreground="#888888").pack(side="left")
        ttk.Button(top, text="如何获取凭据？", command=self._open_tutorial).pack(side="right")
        ttk.Button(top, text="发布到 GitHub…", command=self._open_publish,
                   style="Ghost.TButton").pack(side="right", padx=(0, 8))

        # 凭据区
        cred = ttk.LabelFrame(outer, text="接口凭据（key_session / secret）", padding=8)
        cred.pack(fill="x", pady=(10, 6))
        cred.grid_columnconfigure(1, weight=1)
        cred.grid_columnconfigure(3, weight=1)

        ttk.Label(cred, text="key_session").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.var_ks = tk.StringVar()
        self.entry_ks = ttk.Entry(cred, textvariable=self.var_ks)
        self.entry_ks.grid(row=0, column=1, sticky="ew")
        ttk.Label(cred, text="secret").grid(row=0, column=2, sticky="w", padx=(12, 6))
        self.var_secret = tk.StringVar()
        self.entry_secret = ttk.Entry(cred, textvariable=self.var_secret, show="●")
        self.entry_secret.grid(row=0, column=3, sticky="ew")

        btn_row = ttk.Frame(cred)
        btn_row.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.var_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_row, text="显示凭据", variable=self.var_show,
                        command=self._toggle_show).pack(side="left")
        ttk.Button(btn_row, text="测试连接", command=self._test_credentials).pack(
            side="left", padx=8)
        self.lbl_status = ttk.Label(btn_row, text="● 未测试", foreground="#888888")
        self.lbl_status.pack(side="left", padx=4)
        ttk.Button(btn_row, text="保存凭据", command=self._save_credentials).pack(side="left", padx=4)
        ttk.Button(btn_row, text="抓包助手", command=self._open_capture,
                   style="Ghost.TButton").pack(side="left")

        # 参数区
        params = ttk.LabelFrame(outer, text="运行参数", padding=8)
        params.pack(fill="x", pady=6)
        ttk.Label(params, text="搜索页数").pack(side="left")
        self.var_pages = tk.IntVar(value=2)
        ttk.Spinbox(params, from_=1, to=10, textvariable=self.var_pages,
                    width=5).pack(side="left", padx=(4, 14))
        ttk.Label(params, text="每篇等待(秒)").pack(side="left")
        self.var_wait = tk.IntVar(value=3)
        ttk.Spinbox(params, from_=0, to=60, textvariable=self.var_wait,
                    width=5).pack(side="left", padx=(4, 14))
        self.var_video = tk.BooleanVar(value=False)
        ttk.Checkbutton(params, text="尝试视频文章",
                        variable=self.var_video).pack(side="left")

        # 一键登录（实验）
        login = ttk.LabelFrame(outer, text="一键登录统一认证（实验功能，免抓包探索）", padding=8)
        login.pack(fill="x", pady=6)
        ttk.Label(login, text="账号").pack(side="left")
        self.var_user = tk.StringVar()
        ttk.Entry(login, textvariable=self.var_user, width=18).pack(side="left", padx=(4, 12))
        ttk.Label(login, text="密码").pack(side="left")
        self.var_pwd = tk.StringVar()
        ttk.Entry(login, textvariable=self.var_pwd, show="●", width=18).pack(side="left", padx=(4, 12))
        ttk.Button(login, text="一键登录", command=self._auto_login).pack(side="left", padx=10)
        ttk.Label(login, text="成功后自动尝试换取第二课堂凭据（若协议支持）；当前为实验能力，"
                              "不保证可用。", foreground="#888888").pack(side="left")

        # 自动与通知区
        auto = ttk.LabelFrame(outer, text="自动与通知（每天自动刷分 + 结果通知）", padding=8)
        auto.pack(fill="x", pady=6)
        auto.grid_columnconfigure(1, weight=1)
        self.var_daily = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto, text="开启每日自动刷题",
                        variable=self.var_daily).grid(row=0, column=0, sticky="w")
        ttk.Label(auto, text="每天时间").grid(row=0, column=2, sticky="e", padx=(16, 4))
        self.var_time = tk.StringVar(value="12:30")
        ttk.Entry(auto, textvariable=self.var_time, width=8).grid(row=0, column=3, sticky="w")
        self.var_logon = tk.BooleanVar(value=True)
        ttk.Checkbutton(auto, text="开机登录时也刷",
                        variable=self.var_logon).grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Label(auto, text="通知方式").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_notify = tk.StringVar(value="banner")
        ttk.Combobox(auto, textvariable=self.var_notify, width=8, state="readonly",
                     values=["banner", "popup", "log"]).grid(row=1, column=1, sticky="w",
                                                             pady=(6, 0))
        self.var_fail = tk.BooleanVar(value=True)
        ttk.Checkbutton(auto, text="失败时也通知",
                        variable=self.var_fail).grid(row=1, column=2, sticky="w",
                                                     padx=(16, 0), pady=(6, 0))
        ttk.Button(auto, text="保存自动设置", command=self._save_auto,
                   style="Ghost.TButton").grid(row=0, column=5, rowspan=2,
                                               sticky="e", padx=(12, 0))
        self.lbl_auto_state = ttk.Label(auto, text="", foreground="#8a8f98")
        self.lbl_auto_state.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
        self.lbl_auto_result = ttk.Label(auto, text="", foreground="#1a7f37")
        self.lbl_auto_result.grid(row=3, column=0, columnspan=6, sticky="w")

        # 操作按钮
        ops = ttk.Frame(outer)
        ops.pack(fill="x", pady=6)
        self.btn_start = ttk.Button(ops, text="▶ 开始刷题", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(ops, text="■ 停止", command=self._stop,
                                   state="disabled", style="Danger.TButton")
        self.btn_stop.pack(side="left", padx=10)
        self.lbl_progress = ttk.Label(ops, text="", foreground="#1a7f37")
        self.lbl_progress.pack(side="left", padx=16)

        # 日志区
        ttk.Label(outer, text="运行日志").pack(anchor="w", pady=(4, 0))
        self.txt_log = scrolledtext.ScrolledText(outer, wrap="word", height=16,
                                                 font=("Consolas", 10), state="disabled")
        self.txt_log.pack(fill="both", expand=True, pady=(2, 4))
        for tag, (color, weight) in LOG_TAG.items():
            opts = {"foreground": color}
            if weight:
                opts["font"] = ("Consolas", 10, weight)
            self.txt_log.tag_configure(tag, **opts)

        # 汇总
        self.lbl_summary = ttk.Label(outer, text="", foreground="#1a7f37")
        self.lbl_summary.pack(anchor="w")

    # ---------------- 凭据与参数 ----------------

    def _load_config_into_ui(self):
        self.var_ks.set(self.config.get("key_session", ""))
        self.var_secret.set(self.config.get("secret", ""))
        self.var_pages.set(self.config.get("pages", 2))
        self.var_wait.set(self.config.get("wait_seconds", 3))
        self.var_video.set(bool(self.config.get("try_video", False)))
        self.var_user.set(self.config.get("auto_login_username", ""))
        self.var_daily.set(bool(self.config.get("auto_daily_enabled", False)))
        self.var_time.set(self.config.get("auto_daily_time", "12:30"))
        self.var_logon.set(bool(self.config.get("auto_login_trigger", True)))
        self.var_notify.set(self.config.get("notify_mode", "banner"))
        self.var_fail.set(bool(self.config.get("notify_on_fail", True)))
        self._refresh_auto_state()

    def _refresh_auto_state(self):
        from core.scheduler import query
        try:
            st = query()
            self.lbl_auto_state.configure(
                text="任务计划：{} {}".format(
                    "登录触发 ✅" if st["logon"] else "登录触发 ✗",
                    "每天定时 ✅" if st["daily"] else "每天定时 ✗"))
        except Exception:
            self.lbl_auto_state.configure(text="任务计划状态未知")
        from core.daily import read_results
        try:
            rows = read_results(1)
            if rows:
                r = rows[-1]
                mark = {"completed": "✅ 已完成", "failed": "⚠️ 未完成",
                        "no-credentials": "⚠️ 未配置凭据"}.get(r.get("status"), "?")
                self.lbl_auto_result.configure(
                    text="上次自动运行 {}　{}　{}".format(
                        r.get("time", "")[:16], mark,
                        str(r.get("detail", ""))[:60]))
        except Exception:
            pass

    def _toggle_show(self):
        show = self.var_show.get()
        if not show:
            self.entry_ks.configure(show="")
            self.entry_secret.configure(show="")
        else:
            self.entry_ks.configure(show="●")
            self.entry_secret.configure(show="●")

    def _save_credentials(self):
        self.config.patch(
            key_session=self.var_ks.get().strip(),
            secret=self.var_secret.get().strip(),
            pages=max(1, int(self.var_pages.get() or 2)),
            wait_seconds=max(0, int(self.var_wait.get() or 0)),
            try_video=bool(self.var_video.get()),
            auto_login_username=self.var_user.get().strip(),
        )
        self.config.save()
        self._log("info", "凭据与参数已保存。")

    def _save_auto(self):
        """保存自动设置并注册任务计划。"""
        t = (self.var_time.get().strip() or "12:30")
        if len(t) != 5 or t[2] != ":" or not t[:2].isdigit() or not t[3:].isdigit():
            self._log("error", "时间格式应为 HH:MM（如 12:30）")
            return
        if not (0 <= int(t[:2]) <= 23 and 0 <= int(t[3:]) <= 59):
            self._log("error", "时间超出范围")
            return
        enabled = bool(self.var_daily.get())
        self.config.patch(auto_daily_enabled=enabled,
                          auto_daily_time=t,
                          auto_login_trigger=bool(self.var_logon.get()),
                          notify_mode=self.var_notify.get(),
                          notify_on_fail=bool(self.var_fail.get()))
        self.config.save()
        import sys as _sys
        import os as _os
        from core.scheduler import register
        if getattr(_sys, "frozen", False):
            prefix = '"{}"'.format(_sys.executable)
        else:
            app_path = _os.path.join(_os.path.dirname(_os.path.dirname(
                _os.path.abspath(__file__))), "app.py")
            prefix = '"{}" "{}"'.format(_sys.executable, app_path)
        msgs = register(prefix, enabled and bool(self.var_logon.get()),
                        enabled, t)
        for m in msgs:
            self._log("info", m)
        self._refresh_auto_state()
        self._log("success", "自动设置已保存。")

    def _open_tutorial(self):
        TutorialWindow(self.root)

    def _open_wizard(self):
        from gui.setup_wizard import SetupWizard
        SetupWizard(self.root, self.config)

    def _open_capture(self):
        from gui.capture_window import CaptureWindow
        CaptureWindow(self.root, on_captured=self.fill_credentials)

    def _open_publish(self):
        from gui.publish_window import PublishWindow
        PublishWindow(self.root)

    def fill_credentials(self, key_session: str, secret: str):
        """抓包助手/其它来源填入凭据（主线程调用）。"""
        self.var_ks.set(key_session)
        self.var_secret.set(secret)
        self.config.patch(key_session=key_session, secret=secret)
        self.config.save()
        self._log("success", "凭据已填入并保存（来自抓包助手）。可直接点「测试连接」验证。")

    # ---------------- 日志 ----------------

    def _log(self, level: str, text: str):
        log_to_file(level, text)
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "[{}] {}\n".format(
            {"info": "信息", "debug": "调试", "success": "成功",
             "warn": "提示", "error": "错误"}.get(level, "信息"), text), level)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _drain_messages(self):
        if self.worker:
            try:
                while True:
                    kind, level, payload = self.worker.queue.get_nowait()
                    if kind == "__done__":
                        self._on_worker_done()
                    elif kind == "log":
                        self._log(level, payload)
                    elif kind == "summary":
                        self.lbl_summary.configure(text=payload)
                    elif kind == "progress":
                        self.lbl_progress.configure(text=payload)
                    elif kind == "error":
                        self._log("error", "后台线程异常：\n{}".format(payload))
                    elif kind == "status":
                        self._set_status(payload[0], payload[1])
            except queue.Empty:
                pass
        self.root.after(100, self._drain_messages)

    def _set_status(self, ok: bool, text: str):
        mark = "●" if ok else "●"
        self.lbl_status.configure(text="{} {}{}".format(mark, "有效" if ok else "无效", text),
                                  foreground="#1a7f37" if ok else "#b3261e")

    # ---------------- 测试连接 / 开始 / 停止 ----------------

    def _guard_busy(self) -> bool:
        if self.worker and not self.worker.finished():
            messagebox.showinfo("任务进行中", "当前有任务正在运行，请等待完成或先停止。")
            return True
        return False

    def _test_credentials(self):
        if self._guard_busy():
            return
        ks = self.var_ks.get().strip()
        secret = self.var_secret.get().strip()
        if not ks or not secret:
            self._set_status(False, "请先填写 key_session 与 secret")
            return
        self._set_status(True, " 测试中…")
        self._log("info", "开始测试凭据…")

        def run(q, stop):
            api = ApiClient(ks, secret)
            ok, msg = api.check_credentials()
            q.put(("log", "success" if ok else "error", "测试结果：{}".format(msg)))
            q.put(("status", (ok, msg)))
            if ok:
                self.config.patch(key_session=ks, secret=secret)
                self.config.save()
                q.put(("log", "info", "凭据有效，已自动保存。"))

        self.worker = Worker(run)
        self.worker.start()

    def _start(self):
        if self._guard_busy():
            return
        ks = self.var_ks.get().strip()
        secret = self.var_secret.get().strip()
        if not ks or not secret:
            messagebox.showwarning("缺少凭据", "请先填写 key_session 与 secret（详见「如何获取凭据？」）。")
            return
        self._save_credentials()
        self.lbl_summary.configure(text="")
        self.lbl_progress.configure(text="")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._log("info", "任务已提交，开始…")

        config = self.config
        cache = self.cache
        engine = AnswerEngine(
            ApiClient(ks, secret),
            config,
            cache,
            on_log=lambda level, text: self.worker.queue.put(("log", level, text)),
            should_stop=lambda: (self.worker and self.worker.is_stopping()),
            on_progress=lambda cur, total, aid: self.worker.queue.put(
                ("progress", "处理中：第 {:>2}/{:<2} 篇（{}）".format(cur, total, aid))),
        )

        def run(q, stop):
            stats = engine.run()
            q.put(("summary", stats.summary()))
            q.put(("log", "success", "运行完成。" if not stats.failures else "运行结束，存在未完成项。"))
            q.put(("__done__", "", ""))

        self.worker = Worker(run)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()
            self._log("warn", "正在停止（等待当前请求完成）…")

    def _on_worker_done(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_progress.configure(text="")
        self.worker = None

    def _check_update_async(self, repo: str):
        """后台静默检查更新（不阻塞 UI，失败无提示）。"""
        def run():
            try:
                from core.updater import check_latest, parse_version
                info = check_latest(repo)
                if not info:
                    return
                latest = parse_version(info.get("version", ""))
                cur = (2, 0, 0)
                if latest > cur:
                    txt = "发现新版本 {}（当前 v{}）：{}".format(
                        info.get("version", "?"), APP_VERSION, info.get("url", ""))
                    self.root.after(0, lambda: self._log("info", txt))
            except Exception:
                return
        threading.Thread(target=run, daemon=True).start()

    # ---------------- 一键登录 ----------------

    def _auto_login(self):
        username = self.var_user.get().strip()
        pwd = self.var_pwd.get()
        if not username or not pwd:
            messagebox.showwarning("缺少账号", "请填写统一认证账号与密码。")
            return
        self.var_pwd.set("")
        self._log("info", "一键登录开始（实验功能）…")

        def code_reader(png_bytes, hint):
            ev = threading.Event()
            res = {}
            self._captcha_q.put((png_bytes, hint, ev, res))
            ev.wait(timeout=120)
            return res.get("code", "")

        def run(q, stop):
            result = attempt_auto_login(username, pwd, code_reader,
                                        on_log=lambda lv, tx: q.put(("log", lv, tx)))
            q.put(("log", "success" if result["ok"] else "error", result["message"]))
            if result["ok"]:
                # 附带探索：用会话探测第二课堂网页端
                from core.auto_login import verify_session_for_dekt
                info = verify_session_for_dekt(result["session"])
                q.put(("log", "info", "会话诊断：{}".format(info)))
                q.put(("log", "warn",
                       "注意：小程序接口凭据通常由微信端签发；若下方刷题仍要求 "
                       "key_session/secret，请使用抓包方式（应用内教程）。"))
            q.put(("__done__", "", ""))

        self.worker = Worker(run)
        self.worker.start()

    def _drain_captcha(self):
        try:
            while True:
                png, hint, ev, res = self._captcha_q.get_nowait()
                self._show_captcha(png, hint, ev, res)
        except queue.Empty:
            pass
        self.root.after(150, self._drain_captcha)

    def _show_captcha(self, png: bytes, hint: str, ev: threading.Event, res: dict):
        # Tk 8.6 原生支持 PNG/GIF 解码，无需额外依赖
        photo = None
        try:
            photo = tk.PhotoImage(data=png)
        except Exception:
            photo = None

        tl = tk.Toplevel(self.root)
        self._captcha_tl = tl
        tl.title("验证码")
        tl.attributes("-topmost", True)
        tl.geometry("360x220")
        ttk.Label(tl, text=hint).pack(pady=(12, 6))
        if photo:
            lbl = ttk.Label(tl, image=photo)
            lbl.image = photo  # 防回收
            lbl.pack()
        else:
            ttk.Label(tl, text="（验证码图片无法显示，请到统一认证页面查看后手动输入）").pack()
        var = tk.StringVar()
        entry = ttk.Entry(tl, textvariable=var, width=18, justify="center")
        entry.pack(pady=8)
        entry.focus_set()

        def confirm(event=None):
            res["code"] = var.get()
            ev.set()
            tl.destroy()
            self._captcha_tl = None

        tl.bind("<Return>", confirm)
        ttk.Button(tl, text="确定", command=confirm).pack()

    # ---------------- 关闭 ----------------

    def _on_close(self):
        if self.worker and not self.worker.finished():
            if not messagebox.askyesno("确认退出", "刷题任务还在运行，确定退出吗？"):
                return
            self.worker.stop()
        self.root.destroy()
