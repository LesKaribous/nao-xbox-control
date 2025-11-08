# -*- coding: utf-8 -*-
import time
import threading
from typing import Dict, Any

import config
from net import connect, send_json_line, recv_json_line
from mapping import MapParams, map_state_to_vel

# Shared gamepad state (left stick + LB/RB only)
class PadState(object):
    def __init__(self):
        self.axes = {"LX": 0.0, "LY": 0.0, "RX": 0.0, "RY": 0.0}
        self.buttons = {"LB": False, "RB": False}
        self._lock = threading.Lock()

    def update_axis(self, name, val):
        with self._lock:
            self.axes[name] = val

    def update_button(self, name, down):
        with self._lock:
            self.buttons[name] = bool(down)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {"axes": dict(self.axes), "buttons": dict(self.buttons)}

def _clamp01(x):  # helper
    return 0.0 if x is None else (x if -1.0 <= x <= 1.0 else (1.0 if x > 1.0 else -1.0))

def _norm_axis_manual(v):
    """
    Normalize raw 'inputs' value to [-1,1] using config.AXIS_MODE.
    Modes:
      - "signed":  -32768..+32767    -> [-1..+1]
      - "u16":     0..65535 (center 32768)
      - "u15":     0..32767 (center 16384)
    Applies optional axis scales from config.
    """
    try:
        iv = int(v)
    except Exception:
        return 0.0

    mode = (config.AXIS_MODE or "u16").lower()
    if mode == "signed":
        n = iv / 32767.0
    elif mode == "u15":
        n = (iv - 16384.0) / 16384.0
    else:  # default "u16"
        n = (iv - 32768.0) / 32767.0

    # clamp and scale per-axis later in the thread
    if n < -1.0: n = -1.0
    if n >  1.0: n =  1.0
    return n

def _inputs_event_thread(state: PadState, stop_evt: threading.Event):
    """Blocking event loop using 'inputs' package; updates PadState."""
    from inputs import get_gamepad
    scale_lx = float(getattr(config, "AXIS_SCALE_LX", 1.0))
    scale_ly = float(getattr(config, "AXIS_SCALE_LY", 1.0))

    while not stop_evt.is_set():
        try:
            events = get_gamepad()  # blocks until at least one event
        except Exception:
            time.sleep(0.01)
            continue
        for e in events:
            code, val = e.code, e.state
            if code == "ABS_X":             # left stick X
                lx = _norm_axis_manual(val) * scale_lx
                state.update_axis("LX", _clamp01(lx))
            elif code == "ABS_Y":           # left stick Y
                ly = _norm_axis_manual(val) * scale_ly
                state.update_axis("LY", _clamp01(ly))
            elif code == "ABS_RX":          # right stick X  → head yaw
                rx = _norm_axis_manual(val)
                state.update_axis("RX", _clamp01(rx))
            elif code == "ABS_RY":          # right stick Y  → head pitch
                ry = _norm_axis_manual(val)
                state.update_axis("RY", _clamp01(ry))
            elif code in ("BTN_TL", "BTN_TL2"):   # LB
                state.update_button("LB", val)
            elif code in ("BTN_TR", "BTN_TR2"):   # RB
                state.update_button("RB", val)
            # extend here if you want more controls

def run_controller():
    # Ensure 'inputs' is available
    try:
        import inputs  # noqa: F401
    except Exception:
        print("[GAMEPAD] Please install the inputs package: pip install inputs")
        return

    pad = PadState()
    stop_evt = threading.Event()
    t = threading.Thread(target=_inputs_event_thread, args=(pad, stop_evt))
    t.daemon = True
    t.start()

    # Connect to NAO server
    sock = connect(config.HOST, config.PORT, timeout=3.0)
    if config.GAMEPAD_SET_DEADMAN_ON_START:
        send_json_line(sock, {"cmd":"set_deadman","args":{"enabled":True}})
        try: _ = recv_json_line(sock)
        except Exception: pass

    params = MapParams(
        deadzone=config.STICK_DEADZONE,
        max_vx=config.MAX_VX_NORM,
        max_vy=config.MAX_VY_NORM,
        hold_vw=config.HOLD_VW_NORM,
        invert_y=config.INVERT_Y,
        debug=config.MAPPING_DEBUG
    )

    print("[GAMEPAD] inputs backend (mode=%s) streaming to %s:%d at %.1f Hz" %
          (config.AXIS_MODE, config.HOST, config.PORT, config.LOOP_HZ))
    dt = 1.0 / float(config.LOOP_HZ)
    last_print = 0.0

    try:
        while True:
            t0 = time.time()
            st = pad.snapshot()
            vx, vy, vw = map_state_to_vel(st, params)

            # --- Head control (right stick) ---
            rx = st["axes"].get("RX", 0.0)
            ry = st["axes"].get("RY", 0.0)

            # Deadzone
            if abs(rx) < config.STICK_DEADZONE: rx = 0.0
            if abs(ry) < config.STICK_DEADZONE: ry = 0.0
            # invert Y so up = look up
            ry = -ry if config.INVERT_Y else ry

            rx *= getattr(config, "HEAD_YAW_SCALE", 1.0)
            ry *= getattr(config, "HEAD_PITCH_SCALE", 1.0)


            # Debug readout (throttled)
            if config.GAMEPAD_DEBUG_PRINT and (time.time() - last_print > 0.1):
                ax = st["axes"]; btn = st["buttons"]
                print("LX={:+.3f} LY={:+.3f} RX={:+.3f} RY={:+.3f}| LB={} RB={} -> vx={:+.3f} vy={:+.3f} vw={:+.3f} hx={:+.3f} hy={:+.3f}".format(
                    ax["LX"], ax["LY"],ax["RX"], ax["RY"], int(btn["LB"]), int(btn["RB"]), vx, vy, vw, rx, ry
                ))
                last_print = time.time()

            send_json_line(sock, {"cmd":"set_target", "args":{"vx_n":vx, "vy_n":vy, "vw_n":vw}})
            try: _ = recv_json_line(sock)
            except Exception: pass






            
            try:
                send_json_line(sock, {"cmd": "set_head", "args": {"yaw_n": rx, "pitch_n": ry}})
                _ = recv_json_line(sock)
            except Exception:
                pass



            sleep_t = dt - (time.time() - t0)
            if sleep_t > 0: time.sleep(sleep_t)
    except KeyboardInterrupt:
        print("\n[GAMEPAD] stopping...")
        stop_evt.set()
        try:
            send_json_line(sock, {"cmd":"stop"}); _ = recv_json_line(sock)
        except Exception: pass
    finally:
        try: sock.close()
        except Exception: pass
        try: t.join(1.0)
        except Exception: pass
