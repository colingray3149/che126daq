"""Settings: defaults here, your changes in settings.json beside daq.py.

Every value can be changed on the Settings page; the page writes settings.json.
"""

from __future__ import annotations

import json
import os
import threading

from .model import DEFAULT_MODEL
from .util import atomic_write, deep_merge

DEFAULTS = {
    "variac_V": 100.0,              # what the variac is set to; heater power scales with V^2
    "heater_W": 500.0,              # McMaster 8440T32: 500 W at 120 V
    "heater_rated_V": 120.0,
    "heater_max_C": 760.0,          # 8440T32 maximum exposure temperature (1400 F)
    "room_C": 24.0,
    "tcs": [                        # amp = which MAX31855 board (1: pins 22/24/26, 2: 28/30/32, 3: 34/36/38)
        {"name": "Heater side", "amp": 2, "show": True},
        {"name": "Barrier rear", "amp": 1, "show": True},
        {"name": "Cartridge internal", "amp": 3, "show": False},
    ],
    "tc3_is_core": False,           # TC3 is the cartridge's internal thermocouple
    "manual_cutoffs": {"1": 730, "2": 120, "3": None},  # board cutoffs while Manual heats
    "control": {
        "mode": "predictive",       # predictive | onoff (see model.Controller)
        "hysteresis_C": 1.0,        # switching band
        "min_pulse_s": 0.5,         # shortest relay on or off time
        "lead_s": 30.0,             # onoff: look-ahead on the measured slope
    },
    "model": DEFAULT_MODEL,
    "relay": "NC",                  # NC: heat flows when the relay is unpowered; NO: only when energized
    "fault_trip_s": 3.0,            # board cuts heat if a TC with a cutoff gives no reading this long (0 = never)
    "sample_ms": 250,
    "lease_ms": 2000,               # board turns heat off if this computer is silent this long
    "port": "",                     # "" = first Arduino found
    "runs_dir": "runs",
    "http_port": 8765,
    "github": "https://github.com/colingray3149/che126daq",
}


class Settings:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = deep_merge(DEFAULTS, {})
        self.problem = ""
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = deep_merge(DEFAULTS, json.load(f))
            except (OSError, ValueError) as e:
                self.problem = "settings.json could not be read (%s); using defaults" % e
        self._fix()

    def _fix(self):
        tcs = list(self.data.get("tcs") or [])
        while len(tcs) < 3:
            tcs.append(dict(DEFAULTS["tcs"][len(tcs)]))
        self.data["tcs"] = tcs[:3]
        for k in ("variac_V", "heater_W", "heater_rated_V"):
            try:
                if float(self.data[k]) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                self.data[k] = DEFAULTS[k]

    def get(self):
        with self.lock:
            return json.loads(json.dumps(self.data))

    def update(self, changes):
        validate(changes)
        with self.lock:
            self.data = deep_merge(self.data, changes)
            self._fix()
            atomic_write(self.path, json.dumps(self.data, indent=2) + "\n")
            return json.loads(json.dumps(self.data))

    def runs_dir(self, root):
        d = self.data.get("runs_dir") or "runs"
        return d if os.path.isabs(d) else os.path.join(root, d)


def validate(c):
    def pos(key, lo=0.0, hi=1e9, src=None):
        src = c if src is None else src
        if key in src:
            try:
                v = float(src[key])
            except (TypeError, ValueError):
                raise ValueError("%s must be a number" % key)
            if not lo < v <= hi:
                raise ValueError("%s must be between %g and %g" % (key, lo, hi))

    pos("variac_V", 0, 300)
    pos("heater_W", 0, 10000)
    pos("heater_rated_V", 0, 300)
    pos("sample_ms", 99, 1000)
    pos("room_C", -40, 60)
    pos("heater_max_C", 0, 2000)
    for k, v in (c.get("manual_cutoffs") or {}).items():
        if v not in (None, ""):
            pos(k, 0, 3000, c["manual_cutoffs"])
    pos("lease_ms", 299, 10000)
    if "fault_trip_s" in c:
        pos("fault_trip_s", -1e-9, 60)
    if "relay" in c and c["relay"] not in ("NC", "NO"):
        raise ValueError("relay must be NC or NO")
    for t in c.get("tcs") or []:
        if int(t.get("amp", 1)) not in (1, 2, 3):
            raise ValueError("amplifier must be 1, 2 or 3")
    ctl = c.get("control") or {}
    if ctl.get("mode", "predictive") not in ("predictive", "onoff"):
        raise ValueError("control mode must be predictive or onoff")
    for k in ("hysteresis_C", "lead_s"):
        pos(k, 0, 1e4, ctl)
    if "min_pulse_s" in ctl:
        pos("min_pulse_s", -1e-9, 60, ctl)
    for k, v in (c.get("model") or {}).items():
        pos(k, 0 if k != "radiation_W_per_K4" else -1e-9, 1e9, c.get("model"))
