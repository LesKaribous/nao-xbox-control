# -*- coding: utf-8 -*-
from __future__ import print_function
import time

class SlewRateLimiter(object):
    """
    Clamp per-axis velocity change per time, units: 'norm per second' for MoveToward.
    """
    def __init__(self, max_acc):
        self.max_acc = float(max_acc)
        self.current = 0.0

    def step(self, target, dt):
        t = float(target)
        c = float(self.current)
        max_step = self.max_acc * dt
        if t > c + max_step:
            c = c + max_step
        elif t < c - max_step:
            c = c - max_step
        else:
            c = t
        # bound to [-1, 1] to be safe
        if c > 1.0: c = 1.0
        if c < -1.0: c = -1.0
        self.current = c
        return c

class MovingTargetController(object):
    """
    Maintains target normalized velocities and produces smoothed commands with
    per-axis slew limiting. Also supports 'duration_s' one-shot targets.
    """
    def __init__(self, max_acc_vx, max_acc_vy, max_acc_vw, auto_zero_on_idle_s):
        self._lim_x = SlewRateLimiter(max_acc_vx)
        self._lim_y = SlewRateLimiter(max_acc_vy)
        self._lim_w = SlewRateLimiter(max_acc_vw)

        self._tgt_x = 0.0
        self._tgt_y = 0.0
        self._tgt_w = 0.0

        self._until_ts = 0.0  # if > now: auto-zero after deadline
        self._last_update_ts = 0.0
        self._idle_zero_s = float(auto_zero_on_idle_s)

    def set_target(self, vx_n, vy_n, vw_n, duration_s=None):
        now = time.time()
        self._last_update_ts = now
        self._tgt_x = _clip(vx_n, -1.0, 1.0)
        self._tgt_y = _clip(vy_n, -1.0, 1.0)
        self._tgt_w = _clip(vw_n, -1.0, 1.0)
        if duration_s is not None and duration_s > 0.0:
            self._until_ts = now + float(duration_s)
        else:
            self._until_ts = 0.0

    def stop(self):
        # make the target zero immediately; limiters will ramp to zero
        self.set_target(0.0, 0.0, 0.0, duration_s=None)

    def step(self, dt):
        """
        Returns smoothed (vx, vy, vw), considering auto-zero on timeout.
        """
        now = time.time()

        if self._until_ts > 0.0 and now >= self._until_ts:
            # time-boxed target expired -> go to zero
            self._tgt_x = 0.0; self._tgt_y = 0.0; self._tgt_w = 0.0
            self._until_ts = 0.0

        if self._idle_zero_s > 0.0:
            if (now - self._last_update_ts) > self._idle_zero_s:
                self._tgt_x = 0.0; self._tgt_y = 0.0; self._tgt_w = 0.0

        vx = self._lim_x.step(self._tgt_x, dt)
        vy = self._lim_y.step(self._tgt_y, dt)
        vw = self._lim_w.step(self._tgt_w, dt)
        return vx, vy, vw

    def state(self):
        return {
            "target": {"vx_n": self._tgt_x, "vy_n": self._tgt_y, "vw_n": self._tgt_w},
            "current": {"vx_n": self._lim_x.current, "vy_n": self._lim_y.current, "vw_n": self._lim_w.current},
            "until_ts": self._until_ts,
            "last_update_ts": self._last_update_ts
        }

def _clip(x, lo, hi):
    if x < lo: return lo
    if x > hi: return hi
    return x
