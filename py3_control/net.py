# -*- coding: utf-8 -*-
import json
import socket
from typing import Optional, Dict, Any

def connect(host: str, port: int, timeout: float = 3.0) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    s.settimeout(None)
    return s

def send_json_line(sock: socket.socket, obj: Dict[str, Any]) -> None:
    line = json.dumps(obj)
    if not line.endswith("\n"):
        line += "\n"
    _send_all(sock, line.encode("utf-8"))

def recv_json_line(sock: socket.socket) -> Optional[Dict[str, Any]]:
    buf = bytearray()
    while True:
        b = sock.recv(1)
        if not b:
            if buf:
                try:
                    return json.loads(buf.decode("utf-8"))
                except Exception:
                    return None
            return None
        if b == b"\n":
            line = buf.decode("utf-8").strip()
            if not line:
                return None
            return json.loads(line)
        buf += b

def _send_all(sock: socket.socket, data: bytes) -> None:
    total = 0
    n = len(data)
    while total < n:
        sent = sock.send(data[total:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        total += sent
