# -*- coding: utf-8 -*-
"""单实例锁：socket 独占端口实现（GUI 与 --daily 各自独立，跨进程有效）。

支持"唤起"：第二实例启动时向持锁实例发 ALIVE 信号，持锁实例回调显示窗口，
从而在无托盘图标的环境下也能通过再次双击找回窗口。
"""
import socket
import threading

GUI_LOCK_PORT = 37441
DAILY_LOCK_PORT = 37442

_ALIVE = b"SC_ACTIVATE\n"


class AppLock:
    def __init__(self, port: int):
        self.port = port
        self._sock: socket.socket | None = None
        self._on_activate = None
        self._accept_thread: threading.Thread | None = None
        self._stop = threading.Event()

    def acquire(self, on_activate=None) -> bool:
        """独占端口成功返回 True；已被占用返回 False（并发起唤起信号）。"""
        self._on_activate = on_activate
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Windows 下必须用 EXCLUSIVEADDRUSE（SO_REUSEADDR 允许重复绑定，锁会失效）
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            s.bind(("127.0.0.1", self.port))
            s.listen(4)
            self._sock = s
            # 接收"已有实例被唤起"的连接？不对——持锁者监听；发起方给持锁者发信号
            self._start_accept()
            return True
        except OSError:
            self._signal_activate()
            return False

    # ---------- 发起方 ----------

    def _signal_activate(self):
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.5) as s:
                s.sendall(_ALIVE)
        except OSError:
            pass

    # ---------- 持锁方 ----------

    def _start_accept(self):
        self._stop.clear()
        self._accept_thread = threading.Thread(target=self._accept_loop,
                                               name="applock", daemon=True)
        self._accept_thread.start()

    def _accept_loop(self):
        s = self._sock
        if s is None:
            return
        s.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, _ = s.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                data = conn.recv(64)
                if data.startswith(b"SC_ACTIVATE") and self._on_activate:
                    self._on_activate()
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def release(self):
        self._stop.set()
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
