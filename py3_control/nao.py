#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import sys

import config
from net import connect, send_json_line, recv_json_line
from presets import build as build_preset
from controller import run_controller

def one_shot(host: str, port: int, msg: dict) -> None:
    s = connect(host, port)
    try:
        send_json_line(s, msg)
        rep = recv_json_line(s)
        if config.PRETTY_JSON:
            print(json.dumps(rep, indent=2))
        else:
            print(rep)
    finally:
        s.close()

def repl(host: str, port: int) -> None:
    print(f"[REPL] Connected to {host}:{port}. Type JSON per line. Ctrl+C to exit.")
    s = connect(host, port)
    try:
        while True:
            try:
                line = input(config.REPL_PROMPT).strip()
            except EOFError:
                print()
                break
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                print(f"! invalid JSON: {e}")
                continue
            send_json_line(s, obj)
            rep = recv_json_line(s)
            if config.PRETTY_JSON:
                print(json.dumps(rep, indent=2))
            else:
                print(rep)
    except KeyboardInterrupt:
        print("\n[REPL] bye.")
    finally:
        s.close()

def parse_args():
    ap = argparse.ArgumentParser(description="NDJSON client for NAO Py2.6 server")
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--port", type=int, default=config.PORT)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preset", help="ping | wake | rest | stop | stand | crouch | deadman:on|off | target")
    g.add_argument("--json", help='Raw JSON string, e.g. \'{"cmd":"get_state"}\'')
    g.add_argument("--repl", action="store_true", help="Interactive mode")
    g.add_argument("--gamepad", action="store_true", help="Run Xbox controller loop (inputs backend)")
    ap.add_argument("--vx", type=float, help="for preset=target")
    ap.add_argument("--vy", type=float, help="for preset=target")
    ap.add_argument("--vw", type=float, help="for preset=target")
    ap.add_argument("--duration", type=float, help="for preset=target")
    return ap.parse_args()

def main():
    args = parse_args()

    if args.gamepad:
        run_controller()
        return

    if args.repl:
        repl(args.host, args.port)
        return

    if args.json:
        try:
            msg = json.loads(args.json)
        except Exception as e:
            print(f"Invalid JSON: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        try:
            msg = build_preset(args.preset, args.vx, args.vy, args.vw, args.duration)
        except Exception as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)

    one_shot(args.host, args.port, msg)

if __name__ == "__main__":
    main()
