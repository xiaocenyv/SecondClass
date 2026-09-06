# -*- coding: utf-8 -*-
"""首次配置向导：引导用户完成 抓包 → 每日自动设置 → 完成。"""
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from core.config import Config


class SetupWizard(tk.Toplevel):
    def __init__(self, parent, config: Config, on_done=None):
        super().__init__(parent)
        self.title("第一次使用 · 配置向导")
        self.geometry("620x480")
        self.minsize(560, 440)
        self.transient(parent)
        self.config = config
        self.on_done = on_done
        self.page = 0
        self.pages = []
        self._build()
        self._show(0)
        self.protocol("WM_DELETE_WINDOW", self._skip)

    # ---------------- 构建 ----------------

    def _build(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        self.body = ttk.Frame(outer)
        self.body.pack(fill="both", expand=True)
        self.footer = ttk.Frame(outer)
        self.footer.pack(fill="x", pady=(10, 0))
        self.btn_prev = ttk.Button(self.footer, text="‹ 上一步",
                                   command=self._prev, style="Ghost.TButton")
        self.btn_prev.pack(side="left")
        self.btn_next = ttk.Button(self.footer, text="下一步 ›", command=self._next)
        self.btn_next.pack(side="right")

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _page_welcome(self):
        ttk.Label(self.body, text="欢迎使用第二课堂自动刷题",
                  font=("Microsoft YaHei", 15, "bold"),
                  foreground="#1f6fb2").pack(anchor="w", pady=(0, 8))
        ttk.Label(self.body, justify="left", font=("Microsoft YaHei", 10),
                  foreground="#333333", text=(
            "这个软件能帮你：\n\n"
            "  · 每天自动完成「第二课堂 → 网络学习」的 2 分\n"
            "  · 只用一个 exe（已内置抓包能力，无需安装任何工具）\n\n"
            "配置只需 2 分钟；之后每天自动跑并通知结果。\n\n"
            "点击「下一步」开始。"
        )).pack(anchor="w")

    def _page_check(self):
        ttk.Label(self.body, text="检查环境",
                  font=("Microsoft YaHei", 13, "bold"),
                  foreground="#1f6fb2").pack(anchor="w", pady=(0, 6))
        ks = self.config.get("key_session", "")
        secret = self.config.get("secret", "")
        if ks and secret:
            ttk.Label(self.body, text="✅ 已检测到凭据，无需重新抓包。",
                      font=("Microsoft YaHei", 11),
                      foreground="#1a7f37").pack(anchor="w", pady=8)
            ttk.Label(self.body, text="可以直接点击「下一步」设置每日自动；"
                                      "或直接关闭向导开始使用。",
                      font=("Microsoft YaHei", 10),
                      foreground="#888888").pack(anchor="w")
        else:
            ttk.Label(self.body, text="还没有配置凭据，接下来只需两步：",
                      font=("Microsoft YaHei", 10),
                      foreground="#333333").pack(anchor="w", pady=8)
            ttk.Label(self.body, text="① 请先确认电脑上已登录「电脑版微信」\n"
                                      "② 点击「去抓包」→ 按提示打开小程序点一篇文章（自动完成）",
                      justify="left", font=("Microsoft YaHei", 10),
                      foreground="#333333").pack(anchor="w")
            ttk.Button(self.body, text="▶ 去抓包（打开抓包助手）",
                       command=self._open_capture).pack(anchor="w", pady=(8, 0))
            ttk.Label(self.body, text="若抓包完成后回到本向导点击「检查凭据」即可继续",
                      font=("Microsoft YaHei", 9),
                      foreground="#888888").pack(anchor="w", pady=(6, 0))
            ttk.Button(self.body, text="检查凭据", command=self._recheck,
                       style="Ghost.TButton").pack(anchor="w", pady=(4, 0))

    def _page_auto(self):
        ttk.Label(self.body, text="开启每日自动（可选，推荐开启）",
                  font=("Microsoft YaHei", 13, "bold"),
                  foreground="#1f6fb2").pack(anchor="w", pady=(0, 6))
        ttk.Label(self.body, text="自动化触发与通知方式都可以稍后在主窗口「自动与通知」里调整。",
                  font=("Microsoft YaHei", 9),
                  foreground="#888888").pack(anchor="w", pady=(0, 8))
        var_daily = tk.BooleanVar(value=True)
        var_logon = tk.BooleanVar(value=True)
        var_time = tk.StringVar(value="12:30")
        var_notify = tk.StringVar(value="banner")
        row = ttk.Frame(self.body)
        row.pack(anchor="w")
        ttk.Checkbutton(row, text="开启每日自动刷题", variable=var_daily).pack(side="left")
        ttk.Checkbutton(row, text="开机登录时也刷", variable=var_logon).pack(side="left", padx=16)
        ttk.Label(row, text="每天 ").pack(side="left", padx=(16, 0))
        ttk.Entry(row, textvariable=var_time, width=8).pack(side="left")
        ttk.Label(row, text=" 通知方式：").pack(side="left", padx=(16, 0))
        ttk.Combobox(row, textvariable=var_notify, width=8, state="readonly",
                     values=["banner", "popup", "log"]).pack(side="left")
        ttk.Label(self.body, text="banner=通知横幅（推荐） / popup=弹窗 / log=仅记录",
                  font=("Microsoft YaHei", 9),
                  foreground="#888888").pack(anchor="w", pady=(4, 0))
        self._wiz_vars = (var_daily, var_logon, var_time, var_notify)

    def _page_done(self):
        ttk.Label(self.body, text="配置完成！",
                  font=("Microsoft YaHei", 15, "bold"),
                  foreground="#1a7f37").pack(anchor="w", pady=(4, 8))
        ttk.Label(self.body, justify="left", font=("Microsoft YaHei", 10),
                  foreground="#333333", text=(
            "  下一步：\n"
            "  · 在主窗口点「测试连接」验证凭据（应显示绿色）\n"
            "  · 点「开始刷题」即可立即手动跑一次\n"
            "  · 开启自动后，每天会按设定时间自动完成并通知结果\n\n"
            "如遇问题，主窗口右上角有「如何获取凭据」与内置说明。"
        )).pack(anchor="w")
        self.btn_prev.pack_forget()
        self.btn_next.configure(text="完成 ✔", command=self._finish)

    # ---------------- 流程 ----------------

    def _show(self, idx: int):
        self.page = idx
        self._clear()
        if idx == 0:
            self._page_welcome()
            self.btn_prev.pack_forget()
        elif idx == 1:
            self._page_check()
            self.btn_prev.pack(side="left", fill="x", expand=True)
        elif idx == 2:
            self._page_auto()
            self.btn_prev.pack(side="left", fill="x", expand=True)
        elif idx == 3:
            self._page_done()
        self.btn_next.configure(text="下一步 ›", command=self._next)

    def _next(self):
        if self.page == 0:
            self._show(1)
        elif self.page == 1:
            # 未配置凭据不允许进入下一步
            if not self.config.get("key_session", "") or not self.config.get("secret", ""):
                messagebox.showinfo("还没配置凭据", "请先完成抓包（点「去抓包」，完成后点「检查凭据」）。")
                return
            self._show(2)
        elif self.page == 2:
            self._apply_auto()
            self._show(3)

    def _prev(self):
        if self.page > 0:
            self._show(self.page - 1)

    def _apply_auto(self):
        vars_ = getattr(self, "_wiz_vars", None)
        if not vars_:
            return
        var_daily, var_logon, var_time, var_notify = vars_
        t = var_time.get().strip() or "12:30"
        self.config.patch(auto_daily_enabled=bool(var_daily.get()),
                          auto_daily_time=t,
                          auto_login_trigger=bool(var_logon.get()),
                          notify_mode=var_notify.get())
        self.config.save()
        if var_daily.get():
            from core.scheduler import register
            try:
                import os as _os
                if getattr(sys, "frozen", False):
                    prefix = '"{}"'.format(sys.executable)
                else:
                    app_path = _os.path.join(_os.path.dirname(_os.path.dirname(
                        _os.path.abspath(__file__))), "app.py")
                    prefix = '"{}" "{}"'.format(sys.executable, app_path)
                register(prefix, bool(var_logon.get()), True, t)
            except Exception:
                pass

    def _open_capture(self):
        from capture import proxy_ctl
        if not proxy_ctl.wechat_running():
            if not messagebox.askyesno(
                    "需要电脑版微信",
                    "检测到电脑版微信没有运行。\n\n"
                    "请先打开「电脑版微信」→ 登录 → 搜索小程序「第二课堂成绩单」。\n\n"
                    "打开后点「是」继续（会打开抓包助手）。"):
                return
        from gui.capture_window import CaptureWindow
        CaptureWindow(self, on_captured=self._on_captured)

    def _on_captured(self, ks, secret):
        self.config.patch(key_session=ks, secret=secret)
        self.config.save()
        self._recheck()

    def _recheck(self):
        if self.config.get("key_session", "") and self.config.get("secret", ""):
            self._show(2)
            self.btn_next.configure(text="下一步 ›", command=self._next)
        else:
            messagebox.showinfo("尚未完成", "还没有捕获到凭据，请按提示操作后重试。")

    def _finish(self):
        if self.on_done:
            try:
                self.on_done()
            except Exception:
                pass
        self.destroy()

    def _skip(self):
        self.destroy()
