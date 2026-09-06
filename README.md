# 第二课堂自动刷题（SecondClass）

> 合肥工业大学「第二课堂」小程序 · 网络学习模块 · 自动刷题桌面软件
> **开箱即用**：一个 exe 内置抓包能力 —— 首次配置引导 2 分钟，之后**每天自动完成 2 分并通知结果**。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-blue)
![Version](https://img.shields.io/badge/Version-2.1.0-orange)
![License](https://img.shields.io/badge/License-MIT-green)
[![GitHub Downloads](https://img.shields.io/github/downloads/xiaocenyv/SecondClass/v2.1.0/total?color=green)](https://github.com/xiaocenyv/SecondClass/releases/latest)
[![GitHub Stars](https://img.shields.io/github/stars/xiaocenyv/SecondClass?color=green)](https://github.com/xiaocenyv/SecondClass)

![主界面](assets/screens/main.png)

## 特性

- **开箱即用**：单文件 exe，内置轻量抓包代理（无需 Python / Fiddler / mitmproxy / 任何证书配置）；
- **首次配置向导**：第一次打开按引导走：授权电脑微信小程序 → 自动抓取凭据 → 开启每日自动，2 分钟完成；
- **每日自动刷分**：开机登录自动刷 ＋ 每天指定时间（默认 12:30）再兜底一次，达标检测（school 每日 2 分上限）自动停；
- **结果通知**：完成/未完成以 Windows 通知横幅反馈（也可选弹窗或仅记录）；结果历史本地留存；
- **答案缓存**：答对的题记录正确答案，二次运行直接提交秒过；本次运行自动去重；
- **可靠健壮**：超时重试、异常分类可读、单篇失败不中断；凭据测试连接即时校验；
- **免抓包探索**：实验性统一认证自动登录（one.hfut.edu.cn）；
- **内置发布助手**：一键上传 GitHub 并创建 Release（含 exe 附件）。

## 快速开始（普通人版）

1. 下载 `SecondClass.exe`（Releases 页面），**双击运行**（Windows 10/11，无需安装任何东西）；
2. 首次打开自动弹出**配置向导**：按提示点「去抓包」→ 打开**电脑版微信** → 进入「第二课堂成绩单」小程序 → 「网络学习」点开任意一篇文章 → 自动捕获凭据；
3. 向导中顺手勾选「每日自动刷题」（时间/通知方式都可自选）；
4. 完成！之后每天自动刷，完成/失败都有通知横幅；主窗口也可随时手动「开始刷题」。

## 源码运行

```bash
pip install -r requirements.txt
python app.py            # GUI（--daily 静默自动模式 / --smoke 自检）
python publisher.py      # 发布助手
```

## 界面功能

| 区域 | 说明 |
|---|---|
| 接口凭据 | key_session / secret 显示隐藏、测试连接即时校验 |
| 抓包助手 | 内置代理一键抓取（自动配证书/代理/提取/还原） |
| 运行参数 | 搜索页数、每篇等待、尝试视频文章 |
| 一键登录（实验） | 统一认证自动登录探索 |
| **自动与通知** | 每日自动开关、时间（HH:MM）、登录触发、通知方式（横幅/弹窗/仅记录）、失败通知；任务状态与上次结果 |
| 发布助手 | git → GitHub 仓库 → tag → Release（含 exe） |

## 常见问题

**Q：没有电脑版微信 / 不在电脑前？**
抓包需要电脑版微信（小程序在电脑上打开）。只有手机的同学需要借电脑抓一次，
或用 Fiddler 手动抓取一次凭据（主窗口「如何获取凭据」教程），之后同样自动。

**Q：双击 exe 提示「Windows 已保护你的电脑」/ SmartScreen？**
这是 Windows 对下载文件的保护（软件没有付费代码签名证书）。解决方法：
右键 exe → 属性 → 勾选「解除锁定」→ 确定，再双击即可。
（Release 页面附 SHA256 校验值可核对文件未被篡改。）

**Q：杀毒软件（火绒/360/Defender）拦截或删除了 exe？**
这是单文件打包程序（PyInstaller）的常见误报。请将 SecondClass.exe
添加到杀软信任区/白名单；校验 SHA256 与发布页一致即安全。

**Q：每天 2 分什么时候到账？**
按你的自动设置（登录时 / 每天定时）；完成后通知横幅可见，也可在小程序内确认。

**Q：通知没弹出来？**
Windows 通知中心被关闭时降级为本地记录（`%APPDATA%\SecondClass\daily_result.json` 与 logs/），主窗口「自动与通知」区可查看最近结果。

**Q：凭据过期了？**
重新点「抓包助手」抓一次即可（登录时自动任务失败也会通知你）。

**Q：会收集账号信息吗？**
不会。所有数据仅存本机 `%APPDATA%\SecondClass\`，不上传、不入库；密码不落盘。

## 版本历史

- **v2.1.0**：开箱即用 —— 内置抓包代理（零外部依赖）、首次配置向导、每日自动刷分（登录+定时双触发）、通知横幅、自动任务与结果历史；
- **v2.0.0**：桌面版重写 —— GUI、答案缓存、凭据校验、结果汇总、实验性统一认证登录、发布助手；真机验证通过。

## 致谢与许可

接口调用协议与「遍历试错」答题思路参考了
[Zirconium233/SecondClass](https://github.com/Zirconium233/SecondClass)
（原作者未提供开源许可），本版为完全重写并致谢原作者。

[MIT License](LICENSE)

---

*仅限本人账号学习使用；请遵守学校网络与教务系统使用规范。*
