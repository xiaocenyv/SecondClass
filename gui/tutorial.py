# -*- coding: utf-8 -*-
"""「如何获取凭据」图文教程窗口。"""
import tkinter as tk
from tkinter import ttk

STEPS = [
    ("第 1 步：准备抓包环境",
     "在电脑上安装「微信电脑版」并登录。"
     "再下载抓包工具 Fiddler（推荐）并按照教程完成 HTTPS 证书配置。\n"
     "抓包教程参考：https://zhuanlan.zhihu.com/p/410150022"),
    ("第 2 步：进入小程序",
     "在微信电脑版中搜索并打开「第二课堂成绩单」小程序，"
     "使用统一认证平台账号登录。"),
    ("第 3 步：进入网络学习",
     "在小程序中点进「网络学习」模块，随便点开一篇文章后退出（这一步用于让请求带上 secret 等鉴权头）。"),
    ("第 4 步：找到凭据",
     "回到 Fiddler，找到几个与 dekt.hfut.edu.cn 相关的请求，"
     "在请求头（Request Headers）里找到同时包含以下两个参数的请求：\n"
     "    key_session=xxxxxxxx\n"
     "    secret=xxxxxxxx\n"
     "一般是最新几条请求。"),
    ("第 5 步：粘贴到软件",
     "把 key_session 和 secret 等号后面的值分别复制、"
     "粘贴到主窗口的两个输入框中，点击「测试连接」，"
     "灯变绿就可以开始刷题了。"),
]


class TutorialWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("如何获取凭据（key_session / secret）")
        self.geometry("640x520")
        self.minsize(560, 420)
        self.transient(parent)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="获取接口凭据图文引导",
                  font=("Microsoft YaHei", 13, "bold")).pack(anchor="w")

        text = tk.Text(frame, wrap="word", font=("Microsoft YaHei", 10),
                       padx=8, pady=8, relief="flat", bg=self.cget("bg"))
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for title, body in STEPS:
            text.insert("end", "\n{}\n".format(title), "head")
            text.insert("end", "{}\n\n".format(body), "body")
        text.tag_configure("head", font=("Microsoft YaHei", 11, "bold"),
                           foreground="#1f6fb2", spacing1=6)
        text.tag_configure("body", foreground="#333333")
        text.configure(state="disabled")

        hint = ttk.Label(frame, text="提示：凭据长期有效，但偶尔会过期；过期时重新执行第 3~5 步即可。",
                         foreground="#888888")
        hint.pack(anchor="w", pady=(6, 0))
