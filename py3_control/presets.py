# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
import config

def build(preset: str,
          vx: Optional[float] = None,
          vy: Optional[float] = None,
          vw: Optional[float] = None,
          duration: Optional[float] = None) -> Dict[str, Any]:
    """
    Returns a dict NDJSON command for the Py2.6 server.
    """
    p = (preset or "").lower()

    if p == "ping":
        return {"cmd": "ping"}
    if p in ("wake", "rest", "stop"):
        return {"cmd": p}
    if p == "stand":
        return {"cmd": "posture",
                "args": {"name": "StandInit", "speed": float(config.STAND_SPEED)}}
    if p == "crouch":
        return {"cmd": "posture",
                "args": {"name": "Crouch", "speed": float(config.CROUCH_SPEED)}}
    if p == "deadman:on":
        return {"cmd": "set_deadman", "args": {"enabled": True}}
    if p == "deadman:off":
        return {"cmd": "set_deadman", "args": {"enabled": False}}
    if p == "target":
        vx = config.DEFAULT_VX if vx is None else vx
        vy = config.DEFAULT_VY if vy is None else vy
        vw = config.DEFAULT_VW if vw is None else vw
        args = {"vx_n": float(vx), "vy_n": float(vy), "vw_n": float(vw)}
        if duration is None:
            duration = config.DEFAULT_DURATION
        if duration is not None:
            args["duration_s"] = float(duration)
        return {"cmd": "set_target", "args": args}

    raise ValueError("unknown preset: %s" % preset)
