# -*- coding: utf-8 -*-
from __future__ import print_function
import socket
import json

def send_json_line(sock, obj):
    data = json.dumps(obj)
    if not data.endswith("\n"):
        data += "\n"
    _send_all(sock, data.encode('utf-8'))

def _send_all(sock, data_bytes):
    total = 0
    ln = len(data_bytes)
    while total < ln:
        sent = sock.send(data_bytes[total:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        total += sent

def recv_json_line(sock, buf):
    """
    buf is a dict with 'data' string buffer (Py2.6 str).
    Returns (obj or None). Keeps partial data in buf['data'].
    """
    while True:
        idx = buf['data'].find("\n")
        if idx != -1:
            line = buf['data'][:idx]
            buf['data'] = buf['data'][idx+1:]
            line = line.strip()
            if line:
                return json.loads(line)
            return None
        chunk = sock.recv(4096)
        if not chunk:
            # peer closed; flush possible trailing line
            if buf['data'].strip():
                obj = json.loads(buf['data'])
                buf['data'] = ""
                return obj
            return None
        buf['data'] += chunk
