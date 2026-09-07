# -*- coding: utf-8 -*-
"""抓包助手窗口：一键配置代理并捕获 key_session / secret（内置轻量代理，无外部依赖）。"""
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

from tkinter import messagebox, ttk

from capture import proxy_ctl
from capture.proxy import ProxyService

STATE_TEXT = {
    "idle": "未开始",
    "starting": "正在准备（证书 / 代理）…",
    "capturing": "抓包运行中 —— 请到微信小程序里打开网络学习并点开任意一篇文章",
    "captured": "✅ 凭据已捕获！正在还原系统代理…",
    "failed": "未捕获到凭据，请重试",
    "stopping": "正在停止…",
}

CAPTURED = (Path(os.environ.get("APPDATA") or os.path.expanduser("~"))
            / "SecondClass" / "captured.json")


class CaptureWindow(tk.Toplevel):
    """抓包助手；on_captured(ks, secret) 在捕获成功时回调。"""

    def __init__(self, parent, on_captured):
        super().__init__(parent)
        self.title("抓包助手 —— 一键获取 key_session / secret")
        self.geometry("520x440")
        self.minsize(460, 400)
        self.transient(parent)
        self.on_captured = on_captured
        self.proxy: ProxyService | None = None
        self.backup = None
        self.state = "idle"
        self.q = queue.Queue()

        self._build()
        self.after(200, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI ----------------

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="三步获取凭据（无需安装任何工具）",
                  font=("Microsoft YaHei", 12, "bold"),
                  foreground="#1f6fb2").pack(anchor="w")
        steps = ttk.Label(outer, justify="left", foreground="#333333",
                          font=("Microsoft YaHei", 10))
        steps.configure(text=(
            "① 点击「开始抓包」（首次会自动安装证书、之后自动配置系统代理）\n"
            "② 打开「电脑版微信」→ 进入「第二课堂成绩单」小程序 →「网络学习」\n"
            "    随便点开一篇文章再返回\n"
            "③ 看到「✅ 已捕获」后，凭据会自动填到主窗口\n\n"
            "说明：抓包期间网络经由本机代理，其余使用不受影响；结束后自动还原设置。"))
        steps.pack(anchor="w", pady=(6, 10))

        self.lbl_state = ttk.Label(outer, text="状态：" + STATE_TEXT["idle"],
                                   foreground="#8a8f98",
                                   font=("Microsoft YaHei", 10, "bold"))
        self.lbl_state.pack(anchor="w", pady=(4, 8))

        frame = ttk.Frame(outer)
        frame.pack(fill="x")
        self.btn_start = ttk.Button(frame, text="▶ 开始抓包", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(frame, text="■ 停止", command=self._stop,
                                   state="disabled", style="Danger.TButton")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_install = ttk.Button(frame, text="安装证书", command=self._install_cert,
                                      style="Ghost.TButton")
        self.btn_install.pack(side="left")

        self.txt_log = tk.Text(outer, height=9, state="disabled", wrap="word",
                               font=("Consolas", 9), relief="solid", borderwidth=1)
        self.txt_log.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(outer, text="无需 Python / Fiddler / mitmproxy，单文件即用",
                  foreground="#aaaaaa").pack(anchor="w", pady=(4, 0))

    def _log(self, text: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "[{}] {}\n".format(time.strftime("%H:%M:%S"), text))
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _set_state(self, state: str):
        self.state = state
        color = {"captured": "#1a7f37", "failed": "#b3261e",
                 "capturing": "#1f6fb2", "starting": "#1f6fb2"}.get(state, "#8a8f98")
        self.lbl_state.configure(text="状态：{}".format(STATE_TEXT.get(state, state)),
                                 foreground=color)
        self.btn_start.configure(
            state="disabled" if state in ("starting", "capturing") else "normal")
        self.btn_stop.configure(
            state="normal" if state in ("starting", "capturing") else "disabled")

    # ---------------- 逻辑 ----------------

    def _start(self):
        if self.state in ("starting", "capturing"):
            return
        running = proxy_ctl.wechat_running()
        if running is True:
            self._log("已检测到微信（{}）".format(proxy_ctl.wechat_matched_name()))
        elif running is False:
            if not messagebox.askyesno(
                    "没有检测到电脑版微信",
                    "没有检测到微信在运行（已检查 WeChat/Weixin 等进程）。\n\n"
                    "请先打开「电脑版微信」并登录，然后在小程序里进「第二课堂成绩单」。\n"
                    "如果没有安装微信，请安装后重试。\n\n"
                    "若你确定微信正在运行，点「是」忽略提示继续。", icon="question"):
                return
        # running is None（检测失败）时直接放行
        self._log("准备抓包…")
        self._set_state("starting")
        threading.Thread(target=self._run_start, daemon=True).start()

    def _run_start(self):
        def put(*args):
            self.q.put(args)
        try:
            # 1) CA 证书与信任
            put("log", "生成本地抓包证书…")
            try:
                from capture import certgen
                certgen.ensure_ca()
            except Exception as e:
                put("error", "证书生成失败：{}".format(repr(e)))
                put("state", "failed")
                return
            if not proxy_ctl.is_ca_trusted():
                put("log", "证书未信任，正在安装到本机受信任根…")
                installed, msg = proxy_ctl.install_ca()
                put("log", "安装证书：{}".format(msg))
                deadline = time.time() + 120
                while time.time() < deadline and not proxy_ctl.is_ca_trusted():
                    time.sleep(1)
                if not proxy_ctl.is_ca_trusted():
                    put("log", "证书信任未完成：可点「安装证书」后再试；多数环境直接可用")
            # 2) 备份并设置系统代理
            put("log", "备份并设置系统代理 127.0.0.1:8080…")
            self.backup = proxy_ctl.read_proxy()
            proxy_ctl.apply_proxy()
            # 3) 启动内置代理（本进程内）
            put("log", "启动内置抓包代理…")
            self.proxy = ProxyService(
                on_credentials=self._on_credentials,
                on_log=lambda t: put("log", t))
            self.proxy.start()
            self._set_state("capturing")
            put("log", "抓包运行中：请在微信小程序内打开「网络学习」并点开任意文章/返回")
        except Exception as e:
            put("error", "抓包启动失败：{}".format(repr(e)))
            self._restore()
            put("state", "failed")

    def _on_credentials(self, ks: str, secret: str):
        """代理线程回调（捕获成功）。"""
        self.q.put(("captured", ks, secret))

    def _restore(self):
        if self.backup is not None:
            try:
                proxy_ctl.restore_proxy(self.backup)
                self._log("系统代理已还原")
            except Exception:
                pass
            self.backup = None

    def _install_cert(self):
        self._log("请求安装证书…")
        threading.Thread(target=self._install_cert_thread, daemon=True).start()

    def _install_cert_thread(self):
        installed, msg = proxy_ctl.install_ca()
        self.q.put(("log", "证书安装结果：{}".format(msg)))
        if installed:
            self.q.put(("log", "证书已信任"))

    def _stop(self):
        self._set_state("stopping")
        self._log("停止抓包…")
        if self.proxy:
            try:
                self.proxy.stop(timeout=5)
            except Exception:
                pass
            self.proxy = None
        self._restore()
        self._set_state("idle")
        self._log("已停止，系统代理已还原")

    # ---------------- 主线程刷新 ----------------

    def _drain(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "error":
                    self._log("错误：" + item[1])
                elif kind == "state":
                    self._set_state(item[1])
                elif kind == "captured":
                    _, ks, secret = item
                    self._restore()
                    self._set_state("captured")
                    self._log("凭据已捕获！系统代理已还原。")
                    if self.on_captured:
                        try:
                            self.on_captured(ks, secret)
                        except Exception as e:
                            self._log("填入主窗口失败：{}".format(repr(e)))
                    self.btn_start.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self._drain)

    def _on_close(self):
        if self.state in ("starting", "capturing"):
            if not messagebox.askyesno("确认", "抓包还在进行，确定退出吗？（代理会被还原）"):
                return
        self._stop()
        self.destroy()
