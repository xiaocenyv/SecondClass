# -*- coding: utf-8 -*-
"""后台任务线程：把耗时工作放到子线程，消息经队列回传主线程。"""
import queue
import threading
import traceback


class Worker(threading.Thread):
    """执行 target(queue, stop_event)，并在异常时回传 error 消息。"""

    def __init__(self, target, name="worker"):
        super().__init__(name=name, daemon=True)
        self._target = target
        self.queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._done = threading.Event()

    def run(self):
        try:
            self._target(self.queue, self._stop)
        except Exception:
            self.queue.put(("error", "", traceback.format_exc()))
        finally:
            self._done.set()
            self.queue.put(("__done__", "", ""))

    def stop(self):
        self._stop.set()

    def is_stopping(self) -> bool:
        return self._stop.is_set()

    def finished(self) -> bool:
        return self._done.is_set()
