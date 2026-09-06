# -*- coding: utf-8 -*-
"""抓包助手窗口：一键配置代理并捕获 key_session / secret。"""
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from capture import proxy_ctl

STATE_TEXT = {
    "idle": "未开始",
    "starting": "正在准备（证书 / 代理）…",
    "capturing": "抓包运行中 —— 请到微信小程序里打开网络学习并点开任意一篇文章",
    "captured": "✅ 凭据已捕获！正在还原系统代理…",
    "failed": "未捕获到凭据，请重试",
    "stopping": "正在停止…",
}


def captured_json_path() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "SecondClass" / "captured.json"


class CaptureWindow(tk.Toplevel):
    """抓包助手；on_captured(ks, secret) 在捕获成功时回调。"""

    def __init__(self, parent, on_captured):
        super().__init__(parent)
        self.title("抓包助手 —— 一键获取 key_session / secret")
        self.geometry("520x420")
        self.minsize(460, 380)
        self.transient(parent)
        self.on_captured = on_captured
        self.proc = None
        self.backup = None
        self.state = "idle"
        self.q = queue.Queue()
        self._runner = None
        self._stop_loop = threading.Event()

        self._build()
        self.after(200, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI ----------------

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="三步获取凭据", font=("Microsoft YaHei", 12, "bold"),
                  foreground="#1f6fb2").pack(anchor="w")
        steps = ttk.Label(outer, justify="left", foreground="#333333",
                          font=("Microsoft YaHei", 10))
        steps.configure(text=(
            "① 点击「开始抓包」（首次会自动安装证书、之后自动配置系统代理）\n"
            "② 打开「电脑版微信」→ 进入「第二课堂成绩单」小程序 →「网络学习」\n"
            "    随便点开一篇文章再返回（或直接打开 1 篇文章）\n"
            "③ 等待提示「已捕获」，凭据会自动填到主窗口\n\n"
            "提示：抓包期间电脑网络经由本地代理，其余正常使用不受影响；"
            "结束后自动还原设置。"))
        steps.pack(anchor="w", pady=(6, 10))

        self.lbl_state = ttk.Label(outer, text="状态：" + STATE_TEXT["idle"],
                                   foreground="#8a8f98", font=("Microsoft YaHei", 10, "bold"))
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

        self.txt_log = tk.Text(outer, height=8, state="disabled", wrap="word",
                               font=("Consolas", 9), relief="solid", borderwidth=1)
        self.txt_log.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(outer, text="依赖：需本机已安装 Python 与 mitmproxy（pip install -r requirements-capture.txt）",
                  foreground="#aaaaaa").pack(anchor="w", pady=(4, 0))

    def _log(self, text: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "[{}] {}\n".format(
            time.strftime("%H:%M:%S"), text))
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _set_state(self, state: str):
        self.state = state
        self.lbl_state.configure(text="状态：{}".format(STATE_TEXT.get(state, state)),
                                 foreground="#1a7f37" if state == "captured" else
                                 ("#b3261e" if state == "failed" else "#8a8f98"))
        self.btn_start.configure(state="disabled" if state in ("starting", "capturing") else "normal")
        self.btn_stop.configure(state="normal" if state in ("starting", "capturing") else "disabled")

    # ---------------- 逻辑 ----------------

    def _start(self):
        if self.state in ("starting", "capturing"):
            return
        self.proc = None
        self._log("准备抓包…")
        self._set_state("starting")
        thread = threading.Thread(target=self._run_start, daemon=True)
        self._runner = thread
        thread.start()

    def _run_start(self):
        def put(*args):
            self.q.put(args)
        try:
            # 1) CA 证书准备
            put("log", "检查/生成 mitmproxy 证书…")
            ok = proxy_ctl.ensure_ca_cert()
            if not ok:
                put("error", "证书生成失败，请确认 mitmproxy 已安装")
                return
            if not proxy_ctl.is_ca_trusted():
                put("log", "证书未信任，正在安装到本机受信任根…")
                installed, msg = proxy_ctl.install_ca()
                put("log", "安装证书：{}".format(msg))
                # 等待用户确认 UAC / 完成信任
                deadline = time.time() + 120
                while time.time() < deadline and not proxy_ctl.is_ca_trusted():
                    if self._stop_loop.is_set():
                        return
                    time.sleep(1)
                if not proxy_ctl.is_ca_trusted():
                    put("log", "证书信任未完成，请点击「安装证书」后再试（亦可忽略，多数环境仍可直连）")
            # 2) 备份并设置系统代理
            put("log", "备份并设置系统代理 127.0.0.1:8080…")
            self.backup = proxy_ctl.read_proxy()
            proxy_ctl.apply_proxy()
            addon = Path(__file__).resolve().parent.parent / "capture" / "addon.py"
            # 3) 启动 mitmdump
            put("log", "启动抓包服务…")
            self.proc = proxy_ctl.start_dump(addon)
            self._set_state("capturing")
            put("log", "抓包运行中：请在微信小程序内打开「网络学习」并点开任意文章/返回")
            self._monitor()
        except Exception as e:
            put("error", "抓包启动失败：{}".format(repr(e)))
            self._restore()
            put("state", "failed")

    def _monitor(self):
        """监控进程退出并处理结果（在后台线程中调用）。"""
        def wait_and_collect():
            proc = self.proc
            if proc is None:
                return
            try:
                proc.wait(timeout=600)
            except Exception:
                self._restore()
                self.q.put(("state", "failed"))
                return
            self.q.put(("log", "抓包进程已退出"))
            path = captured_json_path()
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    ks = data.get("key_session", "")
                    secret = data.get("secret", "")
                    if ks and secret:
                        self._restore()
                        self.q.put(("captured", ks, secret))
                        return
                except Exception:
                    pass
            self._restore()
            self.q.put(("log", "未捕获到凭据（可能未覆盖目标请求）"))
            self.q.put(("state", "failed"))
        threading.Thread(target=wait_and_collect, daemon=True).start()

    def _restore(self):
        if self.backup is not None:
            try:
                proxy_ctl.restore_proxy(self.backup)
                self.q.put(("log", "系统代理已还原"))
            except Exception:
                pass
            self.backup = None

    def _install_cert(self):
        self._log("请求安装证书…")
        threading.Thread(target=self._install_cert_thread, daemon=True).start()

    def _install_cert_thread(self):
        ok = proxy_ctl.ensure_ca_cert()
        if not ok:
            self.q.put(("log", "证书文件生成失败"))
            return
        installed, msg = proxy_ctl.install_ca()
        self.q.put(("log", "证书安装结果：{}".format(msg)))
        if installed:
            self.q.put(("log", "证书已信任"))
        else:
            self.q.put(("log", "如弹出 UAC 授权窗口请点「是」，完成后可重新开始抓包"))

    def _stop(self):
        if self.proc is not None:
            self._stop_loop.set()
            self._log("停止抓包…")
            try:
                proxy_ctl.stop_dump(self.proc)
            except Exception:
                pass
            self.proc = None
            self._restore()
            self._set_state("idle")
            self._log("已停止，系统代理已还原")
        else:
            self._restore()
            self._set_state("idle")

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
                    self._set_state("captured")
                    self._log("凭据已捕获！")
                    if self.on_captured:
                        try:
                            self.on_captured(ks, secret)
                        except Exception as e:
                            self._log("填入主窗口失败：{}".format(repr(e)))
                    self.btn_start.configure(state="normal")
        except queue.Empty:
            pass
        self.after(200, self._drain)

    def _on_close(self):
        if self.state in ("starting", "capturing"):
            if not messagebox.askyesno("确认", "抓包还在进行，确定退出吗？（代理会被还原）"):
                return
        self._stop_loop.set()
        self._stop()
        self.destroy()
