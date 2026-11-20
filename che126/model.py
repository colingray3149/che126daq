"""Thermal model of the rig, and the controllers that use it.

Nodes (temperatures in degC):

    core ──R── surface (TC1) ──loss──> room
                  │
                  └─a1─> barrier middle ─a2─> rear (TC2) ─b─> room

    core:    the hidden inside of the cartridge (what an internal TC / the TC513 sees)
    surface: the heater-side thermocouple, TC1
    rear:    the thermocouple behind the barrier, TC2

    d core/dt    = (P - (core - surface) / R) / C_core
    d surface/dt = ((core - surface) / R - G (surface - room) - k (Tk_surface^4 - Tk_room^4)) / C_surface
    d middle/dt  = a1 (surface - middle) - a2 (middle - rear)
    d rear/dt    = a2 (middle - rear) - b (rear - room)

P = heater_W * (variac_V / heater_rated_V)^2 while the relay is on, else 0.

Default numbers are fitted to the measured runs (see analysis/README.md):
heater nodes to run068 (500 W cartridge, 100 V, 3 degC RMS), barrier nodes to the
median of runs 026/028/036/040 (1-3 degC RMS).
"""

from __future__ import annotations

import math

DEFAULT_MODEL = {
    "core_J_per_K": 23.4,
    "surface_J_per_K": 40.0,
    "core_to_surface_K_per_W": 1.82,
    "loss_W_per_K": 0.112,
    "radiation_W_per_K4": 5.39e-11,
    "barrier_a1_per_s": 0.00134,
    "barrier_a2_per_s": 0.0042,
    "rear_loss_per_s": 0.0043,
}


def heater_power(s, on=True):
    if not on:
        return 0.0
    return float(s["heater_W"]) * (float(s["variac_V"]) / float(s["heater_rated_V"])) ** 2


class ThermalState:
    __slots__ = ("core", "surf", "mid", "rear")

    def __init__(self, core, surf, mid, rear):
        self.core, self.surf, self.mid, self.rear = core, surf, mid, rear

    def copy(self):
        return ThermalState(self.core, self.surf, self.mid, self.rear)

    def as_list(self):
        return [self.surf, self.rear, self.core]  # TC1, TC2, TC3 order


def step(state, m, power, room, dt):
    """Advance the model by dt seconds (sub-stepped for stability)."""
    n = max(1, int(math.ceil(dt / 0.25)))
    h = dt / n
    cc, cs = m["core_J_per_K"], m["surface_J_per_K"]
    r, g, k = m["core_to_surface_K_per_W"], m["loss_W_per_K"], m["radiation_W_per_K4"]
    a1, a2, b = m["barrier_a1_per_s"], m["barrier_a2_per_s"], m["rear_loss_per_s"]
    ta4 = (room + 273.15) ** 4
    for _ in range(n):
        q = (state.core - state.surf) / r
        ts = state.surf + 273.15
        loss = g * (state.surf - room) + k * (ts * ts * ts * ts - ta4)
        state.core += h * (power - q) / cc
        state.surf += h * (q - loss) / cs
        dm = a1 * (state.surf - state.mid) - a2 * (state.mid - state.rear)
        dr = a2 * (state.mid - state.rear) - b * (state.rear - room)
        state.mid += h * dm
        state.rear += h * dr
    return state


def steady_surface(m, power, room):
    """Surface temperature the heater settles at with constant power (bisection)."""
    lo, hi = room, 3000.0
    ta4 = (room + 273.15) ** 4
    for _ in range(60):
        mid = (lo + hi) / 2
        loss = m["loss_W_per_K"] * (mid - room) + m["radiation_W_per_K4"] * ((mid + 273.15) ** 4 - ta4)
        if loss < power:
            lo = mid
        else:
            hi = mid
    return lo


def rear_gain(m):
    """Steady rear rise per degree of surface rise through the barrier."""
    b = m["rear_loss_per_s"]
    return 1.0 / (1.0 + b / m["barrier_a2_per_s"] + b / m["barrier_a1_per_s"])


class Observer:
    """Tracks the model state, nudged toward whatever thermocouples read.

    The core is never measured directly (unless TC3 is the internal TC); it is
    inferred from how the surface responds to the heater.
    """

    SURF_GAIN = 0.25
    CORE_GAIN = 0.12
    REAR_GAIN = 0.25

    def __init__(self):
        self.state = None

    def reset(self):
        self.state = None

    def update(self, dt, heat_on, temps, s):
        m = s["model"]
        room = float(s["room_C"])
        surf, rear, core = temps[0], temps[1], temps[2]
        if self.state is None:
            if surf is None:
                return None
            r = rear if rear is not None else room
            self.state = ThermalState(core if core is not None else surf, surf, (surf + r) / 2, r)
            return self.state
        st = self.state
        step(st, m, heater_power(s, heat_on), room, dt)
        if surf is not None:
            e = surf - st.surf
            st.surf += self.SURF_GAIN * e
            st.core += self.CORE_GAIN * e
        if rear is not None:
            e = rear - st.rear
            st.rear += self.REAR_GAIN * e
            st.mid += self.REAR_GAIN * 0.5 * e
        if core is not None and s.get("tc3_is_core"):
            st.core += self.SURF_GAIN * (core - st.core)
        return st


def coast_peak(state, s, node, horizon_s=150.0, dt=0.5):
    """Highest temperature `node` reaches if the heater turns off now, and when."""
    m = s["model"]
    room = float(s["room_C"])
    st = state.copy()
    best = getattr(st, node)
    best_t = 0.0
    t = 0.0
    while t < horizon_s:
        step(st, m, 0.0, room, dt)
        t += dt
        v = getattr(st, node)
        if v > best:
            best, best_t = v, t
        elif t - best_t > 20:
            break
    return best, best_t


NODE_OF_TC = {1: "surf", 2: "rear", 3: "core"}


class Controller:
    """Decides heater on/off for a setpoint on one TC.

    predictive: heat while the model says the TC would stay below the setpoint
                if the heater were switched off now (handles the cartridge's
                stored heat, and voltage through P = V^2/R).
    onoff:      on below setpoint - band, off above setpoint + band, judged on the
                reading plus its slope times the look-ahead (30 s holds within
                ~5 C in simulation; the old firmware's 5 s overshot by ~60 C).
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.on = False
        self.last_switch = -1e9
        self.duty = 0.0
        self.predicted_peak = None

    def output(self, now, dt, tc, sp, sp_at, temp, slope, observer_state, s):
        """sp_at(seconds_ahead) gives the setpoint in the future (for ramps)."""
        c = s["control"]
        mode = c.get("mode", "predictive")
        min_pulse = max(0.0, float(c.get("min_pulse_s", 0.5)))
        if temp is None or sp is None:
            self.duty = 0.0
            return self._set(now, False, 0.0)
        if mode == "predictive" and observer_state is not None and tc in NODE_OF_TC:
            node = NODE_OF_TC[tc]
            horizon = 150.0 if node != "rear" else 900.0
            peak, when = coast_peak(observer_state, s, node, horizon, 0.5 if node != "rear" else 5.0)
            self.predicted_peak = peak
            band = float(c.get("hysteresis_C", 1.0))
            target = sp_at(when)
            if self.on:
                want = peak < target + band * 0.5
            else:
                want = peak < target - band * 0.5
            self.duty = 1.0 if want else 0.0
            return self._set(now, want, min_pulse)
        if mode == "onoff" or observer_state is None:
            lead = float(c.get("lead_s", 30.0))
            band = float(c.get("hysteresis_C", 1.0))
            pred = temp + (slope or 0.0) * lead
            want = self.on
            if pred < sp - band:
                want = True
            elif pred > sp + band:
                want = False
            self.duty = 1.0 if want else 0.0
            return self._set(now, want, min_pulse)
        self.duty = 0.0
        return self._set(now, False, min_pulse)

    def _set(self, now, want, min_pulse):
        if want != self.on and now - self.last_switch >= min_pulse:
            self.on = want
            self.last_switch = now
        return self.on

