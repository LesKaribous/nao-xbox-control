# -*- coding: utf-8 -*-

# NAO Py2.6 server endpoint
HOST = "127.0.0.1"
PORT = 40100

# UI/printing
PRETTY_JSON = True
REPL_PROMPT = "> "

# Gamepad streaming (inputs backend)
LOOP_HZ = 20.0
STICK_DEADZONE = 0.12
INVERT_Y = True                # left stick up = forward (mapping.py)
MAX_VX_NORM = 1.0              # [-1,1]
MAX_VY_NORM = 1.0              # [-1,1]
HOLD_VW_NORM = 0.6             # yaw while LB/RB held
GAMEPAD_SET_DEADMAN_ON_START = True

# Debug
MAPPING_DEBUG = False
GAMEPAD_DEBUG_PRINT=False

AXIS_MODE = "signed"              # << set to "signed", "u16", or "u15"


# Optional extra sensitivity scaling per axis after normalization:
AXIS_SCALE_LX = -1.0            # multiply normalized LX by this
AXIS_SCALE_LY = -1.0            # multiply normalized LY by this

# Right stick sensitivity
HEAD_YAW_SCALE   = 0.8   # 0–1 multiplier
HEAD_PITCH_SCALE = 0.8