# -*- coding: utf-8 -*-
"""
mapping.py
Left stick -> XY planar, LB/RB -> heading. Always returns a triple.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any

@dataclass
class MapParams:
    deadzone: float = 0.12
    max_vx: float = 1.0
    max_vy: float = 1.0
    hold_vw: float = 0.6
    invert_y: bool = True
    debug: bool = False  # set True to print unexpected states

def _dz(val: float, dz: float) -> float:
    return 0.0 if abs(val) < dz else val

def map_state_to_vel(state: Dict[str, Any], p: MapParams) -> Tuple[float, float, float]:
    """
    state: {"axes": {...}, "buttons": {...}}
    returns (vx_n, vy_n, vw_n) in [-1, 1]
    """
    try:
        axes = state.get("axes") or {}
        btns = state.get("buttons") or {}

        # Pull axes (may be missing on some drivers)
        lx = float(axes.get("LX", 0.0))
        ly = float(axes.get("LY", 0.0))

        # Deadzone
        lx = _dz(lx, p.deadzone)
        ly = _dz(ly, p.deadzone)

        # XY planar
        vy = max(-1.0, min(1.0, lx)) * p.max_vy
        vx_in = -ly if p.invert_y else ly
        vx = max(-1.0, min(1.0, vx_in)) * p.max_vx

        # Heading from bumpers (digital)
        lb = bool(btns.get("LB", False))
        rb = bool(btns.get("RB", False))
        if lb and not rb:
            vw = +abs(p.hold_vw)
        elif rb and not lb:
            vw = -abs(p.hold_vw)
        else:
            vw = 0.0

        # Clamp
        vx = max(-1.0, min(1.0, vx))
        vy = max(-1.0, min(1.0, vy))
        vw = max(-1.0, min(1.0, vw))

        return vx, vy, vw
    except Exception as e:
        # Never propagate; fail safe with zeros
        if getattr(p, "debug", False):
            print("[MAPPING] unexpected state -> zeros:", e, "state=", state)
        return 0.0, 0.0, 0.0
