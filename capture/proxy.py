# -*- coding: utf-8 -*-
"""轻量 MITM 代理（同步 socket 实现）：捕获第二课堂小程序的 key_session / secret。

架构：
  客户端(CONNECT dekt.hfut.edu.cn:443) ── TLS(代理动态签发证书) ──> 本代理(127.0.0.1)
  本代理 ── TLS(系统 CA 验证) ──> 真实服务器（原样转发）

命中目标请求头即回调 on_credentials 并停止；其他请求正常转发（兼容 chunked）。
"""
import datetime
import json
import os
import socket
import ssl
import tempfile
import threading
from pathlib import Path

from .certgen import issue_cert

BUFSIZE = 65536
HANDSHAKE_TIMEOUT = 20


def save_credentials(key_session: str, secret: str) -> Path:
    """保存捕获的凭据到 %APPDATA%/SecondClass/captured.json。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = Path(base) / "SecondClass"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "captured.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "key_session": key_session,
            "secret": secret,
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
        }, f, ensure_ascii=False, indent=2)
    return path


def _parse_headers(data: bytes) -> dict:
    headers = {}
    for line in data.split(b"\r\n"):
        if b":" not in line:
            continue
        k, _, v = line.partition(b":")
        headers[k.decode("latin-1").strip().lower()] = v.decode("latin-1").strip()
    return headers


def _recv_until(sock: socket.socket, marker: bytes, limit: int = 256 * 1024) -> bytes:
    """接收直到出现 marker（或超限/断开）。"""
    sock.settimeout(HANDSHAKE_TIMEOUT)
    buf = b""
    while marker not in buf and len(buf) < limit:
        chunk = sock.recv(BUFSIZE)
        if not chunk:
            break
        buf += chunk
    return buf


class ProxyService:
    """本地 MITM 代理（同步 socket，线程模型）。"""

    def __init__(self, host_filter: str = "dekt.hfut.edu.cn", port: int = 8080,
                 on_credentials=None, on_log=None, verify_upstream: bool = True):
        self.host_filter = host_filter
        self.port = port
        self.on_credentials = on_credentials
        self.on_log = on_log or (lambda text: None)
        self.verify_upstream = verify_upstream
        self._srv: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._cert_cache: dict = {}
        self._conns: set[socket.socket] = set()
        self._lock = threading.Lock()

    def _safe_log(self, text: str):
        """日志永不抛异常（GBK 终端等编码问题兜底）。"""
        try:
            self.on_log(text)
        except Exception:
            pass

    # ---------------- 生命周期 ----------------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="mini-mitm", daemon=True)
        self._thread.start()

    def _run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", self.port))
            srv.listen(64)
            srv.settimeout(1.0)
            self._srv = srv
            self.on_log("代理已监听 127.0.0.1:{}".format(self.port))
            while not self._stop.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with self._lock:
                    self._conns.add(conn)
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
        except Exception as e:
            self.on_log("代理启动失败：{}".format(repr(e)))
        finally:
            try:
                if self._srv:
                    self._srv.close()
            except Exception:
                pass

    def stop(self, timeout: float = 3.0):
        self._stop.set()
        with self._lock:
            for c in list(self._conns):
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()
        if self._thread:
            self._thread.join(timeout=timeout)

    # ---------------- 连接处理 ----------------

    def _register(self, sock: socket.socket):
        with self._lock:
            self._conns.add(sock)

    def _unregister(self, sock: socket.socket):
        with self._lock:
            self._conns.discard(sock)

    def _handle(self, conn: socket.socket):
        try:
            conn.settimeout(HANDSHAKE_TIMEOUT)
            data = _recv_until(conn, b"\r\n\r\n")
            lines = data.split(b"\r\n")
            parts = lines[0].decode("latin-1").split(" ")
            if len(parts) < 2 or parts[0].upper() != "CONNECT":
                conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            target = parts[1]
            host, _, port_str = target.partition(":")
            port = int(port_str or "443")
            if host.rstrip(".").lower() != self.host_filter:
                conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                return
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._safe_log("CONNECT {}:{} 已应答".format(host, port))

            # TLS 握手（本代理为服务端，动态签发证书）
            key_pem, cert_pem = self._cert_cache.get(host) or issue_cert(host)
            if host not in self._cert_cache:
                self._cert_cache[host] = (key_pem, cert_pem)
            with tempfile.TemporaryDirectory() as td:
                kp = os.path.join(td, "k.pem")
                cp = os.path.join(td, "c.pem")
                Path(kp).write_bytes(key_pem)
                Path(cp).write_bytes(cert_pem)
                sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                sctx.load_cert_chain(cp, kp)
                tls = sctx.wrap_socket(conn, server_side=True)
            self._register(tls)
            self._safe_log("TLS 握手完成")

            # 读解密后的请求头
            head = _recv_until(tls, b"\r\n\r\n")
            headers = _parse_headers(head)
            ks = headers.get("key_session", "")
            secret = headers.get("secret", "")
            captured = False
            if ks and secret:
                captured = True
                try:
                    save_credentials(ks, secret)
                except Exception as e:
                    self._safe_log("保存凭据失败：{}".format(repr(e)))
                self._safe_log("[OK] 已捕获凭据（key_session/secret）")
                try:
                    if self.on_credentials:
                        self.on_credentials(ks, secret)
                except Exception as e:
                    self._safe_log("回调异常：{}".format(repr(e)))

            # 未命中 / 命中后均正常转发（命中后转发完成即停止，避免小程序请求失败）
            self._forward(tls, head, host, port, headers)
            if captured:
                self._stop.set()  # 捕获完成，停止接受新连接（外层负责恢复代理）
        except (socket.timeout, ConnectionError, OSError, ssl.SSLError, ValueError):
            pass
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self._unregister(conn)

    def _forward(self, tls: socket.socket, head: bytes,
                 host: str, port: int, headers: dict):
        tls.settimeout(30)
        body = b""
        try:
            length = int(headers.get("content-length", "0") or "0")
            if length > 0 and length <= 8 * 1024 * 1024:
                got = b""
                while len(got) < length:
                    chunk = tls.recv(min(BUFSIZE, length - len(got)))
                    if not chunk:
                        break
                    got += chunk
                body = got
            elif headers.get("transfer-encoding", "").lower() == "chunked":
                body = self._read_chunked(tls)
        except Exception:
            pass
        cctx = ssl.create_default_context()
        if not self.verify_upstream:
            cctx.check_hostname = False
            cctx.verify_mode = ssl.CERT_NONE
        try:
            raw_up = socket.create_connection((host, port), timeout=15)
            up = cctx.wrap_socket(raw_up, server_hostname=host
                                  if self.verify_upstream else None)
        except Exception:
            try:
                tls.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except Exception:
                pass
            return
        try:
            up.sendall(head + body)
            # 双向泵送
            threads = [threading.Thread(target=self._pump, args=(up, tls), daemon=True),
                       threading.Thread(target=self._pump, args=(tls, up), daemon=True)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=120)
        finally:
            try:
                up.close()
            except Exception:
                pass

    def _pump(self, src: socket.socket, dst: socket.socket):
        try:
            while True:
                chunk = src.recv(BUFSIZE)
                if not chunk:
                    break
                dst.sendall(chunk)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    def _read_chunked(self, sock: socket.socket) -> bytes:
        data = b""
        buf = b""
        while True:
            while b"\r\n" not in buf:
                chunk = sock.recv(BUFSIZE)
                if not chunk:
                    return data
                buf += chunk
            line, buf = buf.split(b"\r\n", 1)
            try:
                size = int(line.split(b";")[0].strip(), 16)
            except ValueError:
                return data
            if size == 0:
                return data
            while len(buf) < size + 2:
                chunk = sock.recv(BUFSIZE)
                if not chunk:
                    return data
                buf += chunk
            data += buf[:size]
            buf = buf[size + 2:]
