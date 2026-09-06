# -*- coding: utf-8 -*-
"""发布可视化窗口：一键把本地项目推送到 GitHub 并创建 Release。"""
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.release import DEFAULT_EXE, Publisher, find_gh

STEP_NAMES = [
    ("0", "环境预检", "gh 登录 / git / exe 就绪"),
    ("1", "提交代码", "git add + commit"),
    ("2", "推送仓库", "gh repo create --public --push"),
    ("3", "打标签", "git tag vX.Y.Z + push"),
    ("4", "创建 Release", "gh release create + exe 附件"),
]

DEFAULT_NOTES = """# 第二课堂自动刷题 v2.0

合肥工业大学「第二课堂」·网络学习模块自动刷题桌面软件。

## 特性

- 图形界面，一键开始，实时日志与结果汇总
- 内置「抓包助手」：自动捕获 key_session / secret，无需手工配置证书
- 答案缓存：答过的题下次直接秒过
- 凭据测试连接、超时重试、单篇失败不中断
- 实验性统一认证自动登录（免抓包探索）
- 支持 PyInstaller 打包为单文件 exe

基于 [Zirconium233/SecondClass](https://github.com/Zirconium233/SecondClass)
的思路重构，致谢原作者。"""


class PublishWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("发布助手 —— 上传 GitHub + Release")
        self.geometry("680x640")
        self.minsize(600, 560)
        self.transient(parent)
        self.q = queue.Queue()
        self.publisher: Publisher | None = None
        self._running = False
        self._build()
        self.after(200, self._drain)

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        # 基本信息
        info = ttk.LabelFrame(outer, text="发布信息", padding=8)
        info.pack(fill="x")
        info.grid_columnconfigure(1, weight=3)
        info.grid_columnconfigure(3, weight=1)
        ttk.Label(info, text="仓库名").grid(row=0, column=0, sticky="w")
        self.var_repo = tk.StringVar(value="SecondClass")
        ttk.Entry(info, textvariable=self.var_repo).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(info, text="版本").grid(row=0, column=2, sticky="w")
        self.var_ver = tk.StringVar(value="2.0.0")
        ttk.Entry(info, textvariable=self.var_ver, width=8).grid(row=0, column=3, sticky="ew")
        ttk.Label(info, text="标题").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.var_title = tk.StringVar(value="第二课堂自动刷题 v2.0.0")
        ttk.Entry(info, textvariable=self.var_title).grid(row=1, column=1, columnspan=3,
                                                           sticky="ew", padx=6, pady=(8, 0))
        ttk.Label(info, text="Release 说明").grid(row=2, column=0, sticky="nw", pady=(8, 0))
        self.var_notes = tk.Text(info, height=8, wrap="word")
        self.var_notes.insert("1.0", DEFAULT_NOTES)
        self.var_notes.grid(row=2, column=1, columnspan=3, sticky="nsew", padx=6, pady=(8, 0))

        ttk.Label(info, text="exe 路径").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.var_exe = tk.StringVar(value=str(DEFAULT_EXE))
        ttk.Entry(info, textvariable=self.var_exe).grid(row=3, column=1, columnspan=2,
                                                        sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(info, text="浏览…", command=self._browse_exe,
                   style="Ghost.TButton").grid(row=3, column=3, pady=(8, 0), sticky="ew")
        self.var_public = tk.BooleanVar(value=True)
        ttk.Checkbutton(info, text="公开仓库", variable=self.var_public).grid(
            row=4, column=1, sticky="w", pady=(6, 0))

        # 预检
        pre = ttk.Frame(outer)
        pre.pack(fill="x", pady=(10, 4))
        ttk.Button(pre, text="预检环境", command=self._precheck).pack(side="left")
        self.lbl_pre = ttk.Label(pre, text="未预检", foreground="#8a8f98")
        self.lbl_pre.pack(side="left", padx=10)

        # 步骤
        steps = ttk.LabelFrame(outer, text="发布步骤", padding=8)
        steps.pack(fill="both", expand=True, pady=4)
        self.step_labels = []
        for i, (no, name, desc) in enumerate(STEP_NAMES):
            row = ttk.Frame(steps)
            row.pack(fill="x", pady=2)
            lbl = ttk.Label(row, text="○ {} {}".format(no, name), foreground="#8a8f98",
                            font=("Microsoft YaHei", 10))
            lbl.pack(side="left")
            self.step_labels.append(lbl)

        # 操作
        ops = ttk.Frame(outer)
        ops.pack(fill="x", pady=(8, 0))
        self.btn_pub = ttk.Button(ops, text="▶ 开始发布", command=self._start)
        self.btn_pub.pack(side="left")
        self.btn_retry = ttk.Button(ops, text="重试失败步骤", command=self._retry,
                                    state="disabled")
        self.btn_retry.pack(side="left", padx=8)
        ttk.Button(ops, text="打开项目页", command=self._open_page,
                   style="Ghost.TButton").pack(side="left")

        ttk.Label(outer, text="执行日志").pack(anchor="w", pady=(8, 0))
        self.txt_log = tk.Text(outer, height=9, state="disabled", wrap="word",
                               font=("Consolas", 9), relief="solid", borderwidth=1)
        self.txt_log.pack(fill="both", expand=True, pady=(2, 0))

    # ---------- 行为 ----------

    def _browse_exe(self):
        path = filedialog.askopenfilename(title="选择 exe",
                                          filetypes=[("Windows 程序", "*.exe")])
        if path:
            self.var_exe.set(path)

    def _log(self, text: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "[{}] {}\n".format(
            time.strftime("%H:%M:%S"), text))
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _set_step(self, idx: int, state: str):
        mark = {"ok": "✅", "run": "▶", "fail": "❌", "wait": "○"}[state]
        color = {"ok": "#1a7f37", "run": "#1f6fb2", "fail": "#b3261e",
                 "wait": "#8a8f98"}[state]
        no, name, _ = STEP_NAMES[idx]
        lbl = self.step_labels[idx]
        lbl.configure(text="{} {} {}".format(mark, no, name), foreground=color)

    def _precheck(self):
        pub = self._make_publisher()
        if not pub:
            return
        self.publisher = pub
        self._set_step(0, "run")
        self.lbl_pre.configure(text="预检中…", foreground="#1f6fb2")

        def run():
            problems = pub.step_precheck()
            self.q.put(("precheck", problems))

        threading.Thread(target=run, daemon=True).start()

    def _make_publisher(self) -> Publisher | None:
        repo = self.var_repo.get().strip()
        ver = self.var_ver.get().strip() or "1.0.0"
        if not repo:
            messagebox.showwarning("缺少仓库名", "请填写 GitHub 仓库名（如 SecondClass）")
            return None
        return Publisher(repo, ver, self.var_title.get().strip() or "SecondClass",
                         self.var_notes.get("1.0", "end").strip(),
                         exe_path=self.var_exe.get().strip() or None,
                         public=self.var_public.get())

    def _start(self):
        if self._running:
            return
        pub = self._make_publisher()
        if not pub:
            return
        if not find_gh():
            messagebox.showwarning(
                "缺少 gh CLI",
                "未找到 gh 命令。安装方式：\n"
                "  1) winget install GitHub.cli  （或下载 zip 解压到 tools/gh/bin/）\n"
                "  2) 然后执行 gh auth login 完成浏览器授权")
            return
        self.publisher = pub
        self._running = True
        self.btn_pub.configure(state="disabled")
        self.btn_retry.configure(state="disabled")
        self._log("预检环境…")
        self._set_step(0, "run")

        def worker():
            problems = pub.step_precheck()
            if problems:
                self.q.put(("precheck", problems))
                self.q.put(("done",))
                return
            self.q.put(("precheck", []))
            self.q.put(("step", (0, "ok", "")))
            for i in range(1, 5):
                self.q.put(("step", (i, "run", "")))
                ok, msg = pub.run_step(i)
                self.q.put(("step", (i, "ok" if ok else "fail", msg)))
                if not ok:
                    break
            self.q.put(("done",))

        threading.Thread(target=worker, daemon=True).start()

    def _retry(self):
        if self._running or not self.publisher:
            return
        self._running = True
        self.btn_retry.configure(state="disabled")
        self.btn_pub.configure(state="disabled")
        self._log("重试失败步骤…")

        def worker():
            for i in range(0, 5):
                if i == 0:
                    # 重新拉取用户名（可能刚完成 gh 登录）
                    self.publisher.step_precheck()
                ok, msg = self.publisher.run_step(i)
                self.q.put(("step", (i, "ok" if ok else "fail", msg)))
                if not ok:
                    break
            self.q.put(("done",))

        threading.Thread(target=worker, daemon=True).start()

    def _open_page(self):
        if self.publisher and self.publisher.github_user:
            import webbrowser
            webbrowser.open(self.publisher.release_url())

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "precheck":
                    problems = payload
                    if problems:
                        self.lbl_pre.configure(text="❌ 预检失败", foreground="#b3261e")
                        for p in problems:
                            self._log("预检问题：{}".format(p))
                        self._set_step(0, "fail")
                    else:
                        self.lbl_pre.configure(
                            text="✅ 预检通过（用户：{}）".format(
                                self.publisher.github_user if self.publisher else ""),
                            foreground="#1a7f37")
                        self._set_step(0, "ok")
                elif kind == "step":
                    idx, state, msg = payload
                    self._set_step(idx, state)
                    if msg:
                        self._log(("成功：" if state == "ok" else "失败：") + msg)
                elif kind == "done":
                    self._running = False
                    self.btn_pub.configure(state="normal")
                    self.btn_retry.configure(state="normal")
                    self._log("流程结束。")
        except queue.Empty:
            pass
        self.after(200, self._drain)
