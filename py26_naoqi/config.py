# -*- coding: utf-8 -*-

# NAOqi endpoint
NAO_IP   = "192.168.1.169"   # change me
#NAO_IP   = "172.24.224.1"   # change me
NAO_PORT = 9559

# TCP server (this Py2.6 process)
HOST = "0.0.0.0"
PORT = 40100

# Control loop
LOOP_HZ = 20.0

# MoveToward expects normalized [-1,1]
# We'll ramp commands toward target with these max accelerations per second
MAX_ACC_VX = 1.5     # norm/s
MAX_ACC_VY = 1.5
MAX_ACC_VW = 3.0

# Safety
DEADMAN_INITIAL = False      # start with deadman off
AUTO_ZERO_ON_IDLE_S = 2    # if no client updates for a while, drift target to 0

EXTRA_SITE_DIR = "C:/dev/naoqi/lib"



# --- Head control (angles in radians) ---
HEAD_YAW_MIN   = -2.0857
HEAD_YAW_MAX   =  2.0857
HEAD_PITCH_MIN = -0.6720
HEAD_PITCH_MAX =  0.5149

# Max angular speed we’ll integrate toward (rad/s) when joystick is at ±1
HEAD_MAX_YAW_RATE   = 1.5
HEAD_MAX_PITCH_RATE = 1.0

# How fast NAO should move to the setAngles target (fraction of max speed 0..1)
HEAD_FRACTION_SPEED = 0.3