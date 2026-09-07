# -*- coding: utf-8 -*-
"""单实例锁：socket 独占端口实现（GUI 与 --daily 各自独立，跨进程有效）。"""
import socket

GUI_LOCK_PORT = 37441
DAILY_LOCK_PORT = 37442


class AppLock:
    def __init__(self, port: int):
        self.port = port
        self._sock: socket.socket | None = None

    def acquire(self) -> bool:
        """独占端口成功返回 True；已被占用返回 False。"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Windows 下必须用 EXCLUSIVEADDRUSE（SO_REUSEADDR 允许重复绑定，锁会失效）
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            s.bind(("127.0.0.1", self.port))
            s.listen(1)
            self._sock = s
            return True
        except OSError:
            return False

    def release(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.release()
