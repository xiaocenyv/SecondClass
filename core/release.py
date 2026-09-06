# -*- coding: utf-8 -*-
"""发布编排：git 提交 → 推送到 GitHub → 打 tag → 创建 Release 并上传 exe。

每一步返回 (ok, message, can_skip)；失败时 GUI 支持"重试失败步骤"（幂等：
已完成的步骤会跳过）。
"""
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXE = PROJECT_ROOT / "dist" / "SecondClass.exe"

GH_PATH_CANDIDATES = [
    "gh",
    r"C:\Program Files\GitHub CLI\gh.exe",
    str(PROJECT_ROOT / "tools" / "gh" / "bin" / "gh.exe"),
]


def _run(cmd, timeout=180, cwd=None):
    """运行命令，返回 (exit_code, stdout+stderr 文本)。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace",
                           cwd=str(cwd or PROJECT_ROOT))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "命令超时"
    except FileNotFoundError:
        return -1, "找不到命令：{}".format(cmd[0])


def find_gh() -> str | None:
    exe = shutil.which("gh")
    if exe:
        return exe
    for c in GH_PATH_CANDIDATES:
        if Path(c).exists():
            return c
    return None


class Publisher:
    """封装发布流程；step_precheck 预检，run_step(index) 逐步执行。"""

    def __init__(self, repo_name: str, version: str, title: str, notes: str,
                 exe_path: str | None = None, public: bool = True):
        self.repo_name = repo_name
        self.version = version.lstrip("v")  # 统一不带 v
        self.tag = "v" + self.version
        self.title = title
        self.notes = notes
        self.exe_path = Path(exe_path) if exe_path else DEFAULT_EXE
        self.public = public
        self.github_user = ""

    # ---------- 预检（无副作用） ----------

    def step_precheck(self) -> list[str]:
        """返回问题列表；空列表 = 全部通过。"""
        problems = []
        if not shutil.which("git"):
            problems.append("未找到 git")
        gh = find_gh()
        if not gh:
            problems.append("未找到 gh CLI（请安装或放入 tools/gh/）")
        else:
            _, out = _run([gh, "auth", "status"], timeout=30)
            if "Logged in" not in out:
                problems.append("gh 未登录（请先 gh auth login 授权）")
            else:
                rc, u = _run([gh, "api", "user", "--jq", ".login"], timeout=30)
                if rc == 0 and u.strip():
                    self.github_user = u.strip()
                else:
                    problems.append("无法获取 GitHub 用户名")
        if not self.exe_path.exists():
            problems.append("exe 不存在：{}（请先 build_exe.bat 打包）".format(self.exe_path))
        return problems

    # ---------- 步骤 ----------

    def run_step(self, index: int) -> tuple[bool, str]:
        """执行第 index 步（0..4），返回 (ok, msg)。"""
        gh = find_gh()
        if not gh:
            return False, "缺少 gh CLI"
        if index == 0:  # git 初始化、身份与本地提交
            if not (PROJECT_ROOT / ".git").exists():
                rc, msg = _run(["git", "init"])
                if rc != 0:
                    return False, "git init 失败: " + msg[-200:]
            if not self.github_user:
                return False, "GitHub 用户名未知（请先预检）"
            _, u = _run(["git", "config", "user.name"])
            if not u.strip():
                _run(["git", "config", "user.name", self.github_user])
                _run(["git", "config", "user.email",
                      "{}@users.noreply.github.com".format(self.github_user)])
            _, status = _run(["git", "status", "--porcelain"])
            if not status.strip():
                return True, "工作区干净，跳过提交"
            _run(["git", "add", "-A"])
            rc, msg = _run(["git", "commit", "-m", "{} ({})".format(self.title, self.version)])
            if rc != 0:
                return False, "git commit 失败: " + msg[-200:]
            return True, "git 已提交"
        if index == 1:  # 创建远程仓库并推送
            rc, rem = _run(["git", "remote", "get-url", "origin"])
            if rc == 0 and rem.strip():
                return True, "远程已存在，跳过创建"
            target = "{}/{}".format(self.github_user, self.repo_name)
            rc, msg = _run([gh, "repo", "create", target,
                            "--public" if self.public else "--private",
                            "--source=.", "--push"], timeout=600)
            if rc != 0:
                return False, "创建仓库失败: " + msg[-300:]
            return True, "仓库已创建并推送代码"
        if index == 2:  # tag
            _, tags = _run(["git", "tag", "-l", self.tag])
            if self.tag in tags:
                return True, "tag {} 已存在，跳过".format(self.tag)
            rc, msg = _run(["git", "tag", self.tag])
            if rc != 0:
                return False, "创建 tag 失败: " + msg[-200:]
            rc, msg = _run(["git", "push", "origin", self.tag])
            if rc != 0:
                return False, "推送 tag 失败: " + msg[-300:]
            return True, "tag {} 已推送".format(self.tag)
        if index == 3:  # Release
            target = "{}/{}".format(self.github_user, self.repo_name)
            rc, rel = _run([gh, "release", "list", "-R", target], timeout=60)
            if self.tag in rel:
                return True, "Release {} 已存在，跳过".format(self.tag)
            cmd = [gh, "release", "create", self.tag, "-R", target,
                   "--title", self.title, "--notes", self.notes]
            if self.exe_path.exists():
                cmd.append(str(self.exe_path))
            rc, msg = _run(cmd, timeout=600)
            if rc != 0:
                return False, "创建 release 失败: " + msg[-300:]
            return True, "Release {} 已创建（含 exe 附件）".format(self.tag)
        return False, "未知步骤"

    def release_url(self) -> str:
        return "https://github.com/{}/{}/releases/tag/{}".format(
            self.github_user, self.repo_name, self.tag)
