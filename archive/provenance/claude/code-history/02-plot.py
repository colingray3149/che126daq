#!/usr/bin/env nix-shell
#!nix-shell -i python3 -p "python3.withPackages (p: [p.matplotlib p.pyserial p.tkinter])"
# Live plot of the two thermocouples from thermocouple_logger.ino.
# Shows the last 20 s; usage: ./plot.py [port]   (default /dev/ttyACM0)

import sys
from collections import deque

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
WINDOW_S = 20
COLORS = ("#2a78d6", "#eb6834")  # TC1 blue, TC2 orange

ser = serial.Serial(PORT, 115200, timeout=0)
t, tc = deque(), (deque(), deque())
buf = b""

fig, ax = plt.subplots(figsize=(8, 4.5))
fig.canvas.manager.set_window_title("Thermocouples")
lines = [ax.plot([], [], color=c, lw=2, label=f"TC{i+1} (A{i+1})")[0] for i, c in enumerate(COLORS)]
tags = [ax.text(0, 0, "", fontsize=10, va="center", color="#333") for _ in COLORS]
ax.set_xlabel("time (s)")
ax.set_ylabel("temperature (°C)")
ax.grid(color="#e5e5e2", lw=0.8)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
ax.legend(loc="upper left", frameon=False)


def update(_):
    global buf
    buf += ser.read(ser.in_waiting or 1)
    *rows, buf = buf.split(b"\n")
    for row in rows:
        try:
            s, a, b = map(float, row.decode().strip().split(","))
        except ValueError:
            continue  # header or partial line
        t.append(s); tc[0].append(a); tc[1].append(b)
    if not t:
        return
    while t[-1] - t[0] > WINDOW_S:
        t.popleft(); tc[0].popleft(); tc[1].popleft()

    start = max(0, t[-1] - WINDOW_S)
    ax.set_xlim(start, start + WINDOW_S)
    lo, hi = min(min(tc[0]), min(tc[1])), max(max(tc[0]), max(tc[1]))
    pad = max(1, (hi - lo) * 0.15)
    ax.set_ylim(lo - pad, hi + pad)
    for line, tag, ys in zip(lines, tags, tc):
        line.set_data(t, ys)
        tag.set_position((t[-1] + 0.2, ys[-1]))
        tag.set_text(f"{ys[-1]:.1f} °C")


anim = FuncAnimation(fig, update, interval=100, cache_frame_data=False)
fig.subplots_adjust(right=0.86)
for tag in tags:
    tag.set_clip_on(False)
plt.show()
