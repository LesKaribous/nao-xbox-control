# -*- coding: utf-8 -*-
from __future__ import print_function
import time
import socket
import threading
import json
import sys
import traceback
import site

import signal
import threading
import config

if config.EXTRA_SITE_DIR:
    try:
        site.addsitedir(config.EXTRA_SITE_DIR)
    except Exception:
        pass

try:
    from naoqi import ALProxy
except Exception as e:
    print("[FATAL] NAOqi SDK not importable:", e)
    sys.exit(1)

from net import send_json_line, recv_json_line
from motion import MovingTargetController





_SHUTDOWN = threading.Event()
_listener_sock = None
_client_threads = []


def _sig_handler(signum, frame):
    # Trigger graceful shutdown
    _SHUTDOWN.set()
    try:
        if _listener_sock:
            _listener_sock.close()  # unblocks accept()
    except Exception:
        pass

# Handle Ctrl-C and TERM
signal.signal(signal.SIGINT, _sig_handler)
try:
    signal.signal(signal.SIGTERM, _sig_handler)
except Exception:
    # SIGTERM may not exist on some platforms
    pass



def _clip(x, lo, hi):
    if x < lo: return lo
    if x > hi: return hi
    return x



# Globals
_motion = None
_posture = None
_tts = None

_deadman = bool(config.DEADMAN_INITIAL)
_ctrl = MovingTargetController(
    max_acc_vx=config.MAX_ACC_VX,
    max_acc_vy=config.MAX_ACC_VY,
    max_acc_vw=config.MAX_ACC_VW,
    auto_zero_on_idle_s=config.AUTO_ZERO_ON_IDLE_S
)

_clients = set()
_clients_lock = threading.Lock()

# ---- Head control state ----
_head_yaw   = 0.0
_head_pitch = 0.0
_head_cmd = {"yaw_n": 0.0, "pitch_n": 0.0}
_head_lock = threading.Lock()



# Py2.6 type helpers
try:
    basestring  # noqa
except NameError:
    basestring = str
try:
    unicode  # noqa
except NameError:
    unicode = str

_VALID_POSTURES = set([
    "Stand", "StandInit", "StandZero",
    "Crouch",
    "Sit", "SitRelax",
    "LyingBelly", "LyingBack"
])
_ALIASES = {
    "stand": "Stand",
    "standinit": "StandInit",
    "standzero": "StandZero",
    "crouch": "Crouch",
    "sit": "Sit",
    "sitrelax": "SitRelax",
    "belly": "LyingBelly",
    "back": "LyingBack"
}

def _normalize_posture(name):
    if not name:
        return None
    if isinstance(name, basestring):
        key = name.strip()
        if not key:
            return None
        if key in _VALID_POSTURES:
            return key
        low = key.replace(" ", "").lower()
        return _ALIASES.get(low)
    return None

def _to_bytes(s):
    # Ensure NAOqi sees a plain 'str' (bytes) not unicode
    if isinstance(s, unicode):
        try:
            return s.encode('utf-8')
        except Exception:
            return s.encode('ascii', 'ignore')
    return s





def init_proxies():
    global _motion, _posture, _tts
    _motion  = ALProxy("ALMotion",       config.NAO_IP, config.NAO_PORT)
    _posture = ALProxy("ALRobotPosture", config.NAO_IP, config.NAO_PORT)
    try:
        _tts = ALProxy("ALTextToSpeech", config.NAO_IP, config.NAO_PORT)
    except Exception:
        _tts = None

def say(txt):
    if _tts:
        try: _tts.say(txt)
        except Exception: pass


def handle_conn(conn, addr):
    buf = {'data': ""}
    with _clients_lock:
        _clients.add(conn)
    try:
        while not _SHUTDOWN.is_set():
            msg = recv_json_line(conn, buf)
            if msg is None:
                break
            rid = msg.get("rid")
            cmd = msg.get("cmd")
            args = msg.get("args", {}) or {}
            try:
                if cmd == "ping":
                    rep = {"ok": True, "rid": rid, "data": {"pong": time.time()}}
                elif cmd == "shutdown":
                    # Optional remote shutdown
                    _SHUTDOWN.set()
                    rep = {"ok": True, "rid": rid, "data": {"shutting_down": True}}
                elif cmd == "wake":
                    try:
                        # not all NAOqi 1.14 have wakeUp; emulate
                        _motion.setStiffnesses("Body", 1.0)
                        try:
                            _posture.goToPosture("StandInit", 0.75)
                        except Exception:
                            pass
                        rep = {"ok": True, "rid": rid, "data": {}}
                    except Exception as e:
                        rep = {"ok": False, "rid": rid, "error": str(e)}
                elif cmd == "rest":
                    try:
                        try:
                            _posture.goToPosture("Crouch", 0.5)
                        except Exception:
                            pass
                        _motion.setStiffnesses("Body", 0.0)
                        rep = {"ok": True, "rid": rid, "data": {}}
                    except Exception as e:
                        rep = {"ok": False, "rid": rid, "error": str(e)}




                elif cmd == "set_head":
                    # args: {"yaw_n": float[-1,1], "pitch_n": float[-1,1]}
                    try:
                        yn = float(args.get("yaw_n", 0.0))
                        pn = float(args.get("pitch_n", 0.0))
                    except Exception:
                        yn, pn = 0.0, 0.0
                    if yn < -1.0: yn = -1.0
                    if yn >  1.0: yn =  1.0
                    if pn < -1.0: pn = -1.0
                    if pn >  1.0: pn =  1.0
                    with _head_lock:
                        _head_cmd["yaw_n"] = yn
                        _head_cmd["pitch_n"] = pn
                    rep = {"ok": True, "rid": rid, "data": {"yaw_n": yn, "pitch_n": pn}}

                elif cmd == "center_head":
                    with _head_lock:
                        global _head_yaw, _head_pitch
                        _head_yaw = 0.0
                        _head_pitch = 0.0
                    rep = {"ok": True, "rid": rid, "data": {}}



                elif cmd == "posture":
                    raw_name = args.get("name", None)
                    name = _normalize_posture(raw_name)
                    if not name:
                        rep = {"ok": False, "rid": rid,
                            "error": "invalid or missing 'name'; allowed: %s" % (sorted(_VALID_POSTURES),)}
                    else:
                        try:
                            speed = float(args.get("speed", 0.7))
                            if speed < 0.0: speed = 0.0
                            if speed > 1.0: speed = 1.0
                            # Force bytes for NAOqi
                            name_b = _to_bytes(name)
                            _motion.setStiffnesses("Body", 1.0)
                            _posture.goToPosture(name_b, speed)
                            rep = {"ok": True, "rid": rid, "data": {"name": name, "speed": speed}}
                        except Exception as e:
                            rep = {"ok": False, "rid": rid, "error": str(e)}


                elif cmd == "set_deadman":
                    global _deadman
                    _deadman = bool(args.get("enabled", False))
                    rep = {"ok": True, "rid": rid, "data": {"enabled": _deadman}}
                elif cmd == "set_target":
                    vx = float(args.get("vx_n", 0.0))
                    vy = float(args.get("vy_n", 0.0))
                    vw = float(args.get("vw_n", 0.0))
                    dur = args.get("duration_s", None)
                    if dur is not None:
                        dur = float(dur)
                    _ctrl.set_target(vx, vy, vw, duration_s=dur)
                    rep = {"ok": True, "rid": rid, "data": _ctrl.state()}
                else:
                    rep = {"ok": False, "rid": rid, "error": "unknown cmd: %s" % cmd}
            except Exception as e:
                rep = {"ok": False, "rid": rid, "error": "exception: %s" % (e,)}
            try:
                send_json_line(conn, rep)
            except Exception:
                break
    finally:
        with _clients_lock:
            try: _clients.remove(conn)
            except Exception: pass
        try: conn.close()
        except Exception: pass




def control_loop():
    # use a sane default if LOOP_HZ missing/zero
    hz = float(getattr(config, "LOOP_HZ", 50.0)) or 50.0
    dt = 1.0 / hz
    last = time.time()
    print("[INFO] control loop at %.1f Hz" % hz)

    # ensure globals are writable
    global _head_yaw, _head_pitch

    while not _SHUTDOWN.is_set():
        t0 = time.time()
        dt_eff = t0 - last
        # guard against weird time jumps
        if dt_eff <= 0.0 or dt_eff > 0.5:
            dt_eff = dt
        last = t0

        # --- Locomotion (gated by deadman) ---
        try:
            vx, vy, vw = _ctrl.step(dt_eff)
            if _deadman:
                _motion.moveToward(vx, vy, vw)
            else:
                _motion.moveToward(0.0, 0.0, 0.0)
        except Exception:
            pass

        # --- Head control (NOT gated by deadman) ---
        try:
            # read normalized inputs safely
            with _head_lock:
                yaw_n   = max(-1.0, min(1.0, float(_head_cmd.get("yaw_n", 0.0))))
                pitch_n = max(-1.0, min(1.0, float(_head_cmd.get("pitch_n", 0.0))))

            # integrate normalized rates (rad/s) -> absolute target angles
            _head_yaw   += yaw_n   * float(getattr(config, "HEAD_MAX_YAW_RATE",   1.5)) * dt_eff
            _head_pitch += pitch_n * float(getattr(config, "HEAD_MAX_PITCH_RATE", 1.0)) * dt_eff

            # clamp to mechanical limits
            _head_yaw   = _clip(_head_yaw,   getattr(config, "HEAD_YAW_MIN",   -2.0857), getattr(config, "HEAD_YAW_MAX",   2.0857))
            _head_pitch = _clip(_head_pitch, getattr(config, "HEAD_PITCH_MIN", -0.6720), getattr(config, "HEAD_PITCH_MAX", 0.5149))

            # make sure head is stiff and send both joints in one call
            try:
                _motion.setStiffnesses(["HeadYaw", "HeadPitch"], 1.0)
            except Exception:
                pass

            frac = float(getattr(config, "HEAD_FRACTION_SPEED", 0.3))
            # fraction must be [0..1]
            if frac < 0.0: frac = 0.0
            if frac > 1.0: frac = 1.0

            _motion.setAngles(["HeadYaw", "HeadPitch"], [_head_yaw, _head_pitch], frac)
        except Exception:
            # never crash the loop on head errors
            pass

        # --- pacing ---
        slept = time.time() - t0
        wait = dt - slept
        if wait > 0.0:
            time.sleep(wait)

    # On shutdown ensure a stop command goes out once
    try:
        _motion.moveToward(0.0, 0.0, 0.0)
    except Exception:
        pass



def main():
    global _listener_sock
    init_proxies()
    try:
        say("Interface prêt.")
    except Exception:
        pass

    # Read current head angles as starting target
    try:
        ang = _motion.getAngles(["HeadYaw","HeadPitch"], True)
        if isinstance(ang, list) and len(ang) == 2:
            global _head_yaw, _head_pitch
            _head_yaw, _head_pitch = float(ang[0]), float(ang[1])
    except Exception:
        pass


    # Start control thread
    th = threading.Thread(target=control_loop)
    th.daemon = True
    th.start()

    # Start TCP server (timeout to poll shutdown)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((config.HOST, config.PORT))
    s.listen(5)
    s.settimeout(0.5)  # so we can check _SHUTDOWN regularly
    _listener_sock = s
    print("[INFO] py26 NAO interface listening on %s:%d" % (config.HOST, config.PORT))

    try:
        while not _SHUTDOWN.is_set():
            try:
                c, a = s.accept()
            except socket.timeout:
                continue
            except Exception:
                if _SHUTDOWN.is_set():
                    break
                raise

            try:
                c.setblocking(1)
                c.settimeout(None)
            except Exception:
                pass

            t = threading.Thread(target=handle_conn, args=(c, a))
            t.daemon = True
            t.start()
            _client_threads.append(t)
    finally:
        # Stop accepting new connections
        try: s.close()
        except Exception: pass

        # Close existing client sockets (nudges handlers to exit)
        with _clients_lock:
            for cli in list(_clients):
                try: cli.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                try: cli.close()
                except Exception: pass

        # Wait a bit for client threads
        t_deadline = time.time() + 2.0
        for t in _client_threads:
            remain = t_deadline - time.time()
            if remain <= 0: break
            try: t.join(remain)
            except Exception: pass

        # Ask control loop to stop and wait shortly
        _SHUTDOWN.set()
        try: th.join(2.0)
        except Exception: pass

        try: say("Au revoir.")
        except Exception: pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try: say("Au revoir.")
        except Exception: pass
