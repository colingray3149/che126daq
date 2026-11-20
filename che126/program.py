"""Experiment programs: a list of steps run in order.

A program is plain JSON (programs/*.json):

{
  "name": "700 C, 60 s hold",
  "steps": [
    {"type": "full", "tc": 1, "temp": 100, "time": null, "wait": true},
    {"type": "ramp", "tc": 1, "temp": 200, "time": 90},
    {"type": "hold", "tc": 1, "temp": 700, "time": 60},
    {"type": "off",  "tc": 1, "temp": 80}
  ],
  "end_when": [{"tc": 2, "op": ">=", "temp": 85}],   # finish early (heat off)
  "cutoffs": {"1": 730, "2": 120, "3": null},         # board trips heat off
  "end_run": false                                     # stop recording at the end
}

Step types (tc = which thermocouple the step watches or controls):
  full  heater fully on until TC >= temp, or for `time` s, or (both blank) until NEXT
  ramp  setpoint moves from the TC's reading at step start to `temp` over `time` s
  hold  regulate TC at `temp`; the `time` s timer starts when the TC first gets within
        2 C of `temp` (blank time: hold until NEXT)
  off   heater off until TC <= temp, or for `time` s, or (both blank) until NEXT
wait: when the step is done, keep its last action (hold at its temperature, stay
off, stay on) until NEXT. NEXT always moves on immediately, whatever the state.
"""

from __future__ import annotations

import math

from . import model

STEP_TYPES = ("full", "ramp", "hold", "off")
HOLD_BAND_C = 2.0  # a Hold step's timer starts once the TC is within this of the setpoint
TC_COUNT = 3


def _num(v, what, allow_none=True):
    if v is None or v == "":
        if allow_none:
            return None
        raise ValueError("%s is required" % what)
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number" % what)
    if not math.isfinite(x):
        raise ValueError("%s must be a number" % what)
    return x


def normalize(p):
    """Validate a program; raise ValueError with a plain message."""
    if not isinstance(p, dict):
        raise ValueError("program must be an object")
    steps = []
    if len(p.get("steps") or []) > 100:
        raise ValueError("a program can have at most 100 steps")
    for i, s in enumerate(p.get("steps") or []):
        n = i + 1
        kind = s.get("type")
        if kind not in STEP_TYPES:
            raise ValueError("step %d: unknown action %r" % (n, kind))
        try:
            tc = int(s.get("tc") or 1)
        except (TypeError, ValueError):
            raise ValueError("step %d: TC must be 1, 2 or 3" % n)
        if not 1 <= tc <= TC_COUNT:
            raise ValueError("step %d: TC must be 1, 2 or 3" % n)
        temp = _num(s.get("temp"), "step %d temperature" % n, allow_none=kind in ("off", "full"))
        if temp is not None and not -50 <= temp <= 1500:
            raise ValueError("step %d: temperature must be between -50 and 1500 °C" % n)
        secs = _num(s.get("time"), "step %d time" % n, allow_none=kind != "ramp")
        if secs is not None and secs < 0:
            raise ValueError("step %d: time cannot be negative" % n)
        steps.append({"type": kind, "tc": tc, "temp": temp, "time": secs, "wait": bool(s.get("wait"))})
    ends = []
    for e in p.get("end_when") or []:
        t = _num(e.get("temp"), "finish-early temperature")
        if t is None:
            continue
        tc = int(e.get("tc") or 2)
        if not 1 <= tc <= TC_COUNT:
            raise ValueError("finish-early TC must be 1, 2 or 3")
        if not -50 <= t <= 1500:
            raise ValueError("finish-early temperature must be between -50 and 1500 °C")
        ends.append({"tc": tc, "op": e.get("op") if e.get("op") in (">=", "<=") else ">=", "temp": t})
    cut = {}
    for k in ("1", "2", "3"):
        v = _num((p.get("cutoffs") or {}).get(k), "TC%s cutoff" % k)
        if v is not None and v > 1500:
            raise ValueError("TC%s cutoff must be at most 1500 °C" % k)
        cut[k] = v if v and v > 0 else None
    name = str(p.get("name") or "").strip() or "Untitled"
    return {"name": name[:80], "steps": steps, "end_when": ends, "cutoffs": cut, "end_run": bool(p.get("end_run"))}


def describe(s):
    tc = "TC%d" % s["tc"]
    t, secs = s.get("temp"), s.get("time")
    dur = ("%g s" % secs) if secs is not None else ""
    if s["type"] == "full":
        if t is not None:
            txt = "Full power until %s ≥ %g °C" % (tc, t) + (" (max %s)" % dur if secs else "")
        else:
            txt = "Full power " + ("for " + dur if dur else "until NEXT")
    elif s["type"] == "ramp":
        txt = "Ramp %s to %g °C over %s" % (tc, t, dur)
    elif s["type"] == "hold":
        txt = "Hold %s at %g °C " % (tc, t) + ("for " + dur if dur else "until NEXT")
    else:
        if t is not None:
            txt = "Heat off until %s ≤ %g °C" % (tc, t) + (" (max %s)" % dur if secs else "")
        else:
            txt = "Heat off " + ("for " + dur if dur else "until NEXT")
    if s.get("wait"):
        txt += ", then wait for NEXT"
    return txt


class Runner:
    """Executes a program. tick() returns whether the heater should be on.

    Shared by the live system and by preview(), so the predicted run uses the
    same rules as the real one.
    """

    def __init__(self, on_event=None, on_finish=None):
        self.on_event = on_event or (lambda text: None)
        self.on_finish = on_finish or (lambda: None)
        self.program = None
        self.index = -1
        self.state = "idle"  # idle | running | waiting | done | stopped | tripped
        self.step_started = 0.0
        self.step_start_temp = None
        self.reached = False
        self.setpoint = None
        self.message = ""
        self.ctrl = model.Controller()

    def start(self, program, now, temps):
        self.program = program
        self.message = ""
        self._enter(0, now, temps)

    def active(self):
        return self.state in ("running", "waiting")

    def current(self):
        if self.program and 0 <= self.index < len(self.program["steps"]):
            return self.program["steps"][self.index]
        return None

    def _enter(self, i, now, temps):
        self.index = i
        self.step_started = now
        self.reached = False
        self.hold_started = None
        self.setpoint = None
        self.ctrl.reset()
        steps = self.program["steps"]
        if i >= len(steps):
            self.state = "done"
            self.index = len(steps)
            self.on_event("Program finished; heat off")
            self.on_finish()
            return
        self.state = "running"
        s = steps[i]
        self.step_start_temp = temps[s["tc"] - 1]
        self.on_event("Step %d: %s" % (i + 1, describe(s)))

    def next(self, now, temps):
        if not self.active():
            return False
        self.on_event("NEXT pressed in step %d" % (self.index + 1))
        self._enter(self.index + 1, now, temps)
        return True

    def stop(self, why, state="stopped"):
        if self.active():
            self.state = state
            self.message = why
            self.setpoint = None

    def tick(self, now, dt, temps, slopes, obs, s):
        if not self.active():
            self.setpoint = None
            return False
        for e in self.program["end_when"]:
            v = temps[e["tc"] - 1]
            if v is not None and ((e["op"] == ">=" and v >= e["temp"]) or (e["op"] == "<=" and v <= e["temp"])):
                self.on_event("Finish-early condition met: TC%d %s %g °C (reads %.1f)" % (e["tc"], e["op"], e["temp"], v))
                self._enter(len(self.program["steps"]), now, temps)
                return False
        step = self.program["steps"][self.index]
        kind, tc, target, secs = step["type"], step["tc"], step.get("temp"), step.get("time")
        temp = temps[tc - 1]
        slope = slopes[tc - 1]
        elapsed = now - self.step_started
        if self.step_start_temp is None and temp is not None:
            self.step_start_temp = temp

        def regulate(sp, sp_at):
            self.setpoint = sp
            return self.ctrl.output(now, dt, tc, sp, sp_at, temp, slope, obs, s)

        if self.reached:  # done, holding its final action until NEXT
            if kind == "off":
                self.setpoint = None
                return False
            if kind == "full" and target is None:
                self.setpoint = None
                return True
            return regulate(target, lambda ahead: target)

        done = False
        heat = False
        if kind == "full":
            self.setpoint = target
            if target is not None and temp is not None and temp >= target:
                done = True
            elif secs is not None and elapsed >= secs:
                done = True
            else:
                # Full power needs a reading only when it is waiting for a temperature.
                heat = target is None or temp is not None
        elif kind == "off":
            self.setpoint = None
            if target is not None and temp is not None and temp <= target:
                done = True
            elif secs is not None and elapsed >= secs:
                done = True
        elif kind == "ramp":
            start = self.step_start_temp if self.step_start_temp is not None else target
            span = target - start

            def sp_at(ahead):
                if not secs:
                    return target
                return start + span * min(1.0, (elapsed + ahead) / secs)

            if secs is None or elapsed >= secs:
                done = True
            heat = regulate(sp_at(0.0), sp_at)
        elif kind == "hold":
            if self.hold_started is None and temp is not None and abs(temp - target) <= HOLD_BAND_C:
                self.hold_started = now
                if secs is not None:
                    self.on_event("Step %d: TC%d reached %g °C; %s hold starts now" % (self.index + 1, tc, target, _mmss(secs)))
            if secs is not None and self.hold_started is not None and now - self.hold_started >= secs:
                done = True
            heat = regulate(target, lambda ahead: target)

        if not done:
            return heat
        if step.get("wait") or (kind == "hold" and secs is None):
            self.reached = True
            if self.state != "waiting":
                self.state = "waiting"
                self.on_event("Step %d done; waiting for NEXT" % (self.index + 1))
            return self.tick(now, 0.0, temps, slopes, obs, s)
        self._enter(self.index + 1, now, temps)
        return False if kind in ("off",) else self.tick(now, 0.0, temps, slopes, obs, s)

    def waiting_for_next(self):
        """True when the step can only end with NEXT (a wait, or no end condition)."""
        st = self.current()
        if not st or not self.active():
            return False
        if self.reached:
            return True
        if st["type"] == "hold":
            return st.get("time") is None
        if st["type"] in ("full", "off"):
            return st.get("temp") is None and st.get("time") is None
        return False


def preview(program, s, start_temps=None, next_after_s=30.0, max_s=7200.0, dt=0.5):
    """Simulate a program on the thermal model with the live rules.

    Returns arrays every 2 s plus step boundaries and plain warnings. NEXT is
    assumed `next_after_s` seconds after a step starts waiting for it.
    """
    room = float(s["room_C"])
    m = s["model"]
    t1 = start_temps[0] if start_temps and start_temps[0] is not None else room
    t2 = start_temps[1] if start_temps and start_temps[1] is not None else room
    plant = model.ThermalState(t1, t1, (t1 + t2) / 2, t2)
    events = []
    runner = Runner(on_event=lambda txt: events.append((round(t, 1), txt)))
    t = 0.0
    temps = [plant.surf, plant.rear, plant.core]
    runner.start(program, 0.0, temps)
    out = {"t": [], "tc1": [], "tc2": [], "core": [], "heat": [], "sp": [], "steps": [], "warnings": []}
    cut = program.get("cutoffs") or {}
    heat = False
    wait_since = None
    step_marks = [(0.0, 0)]
    last_index = 0
    on_time = 0.0
    max_core = plant.core
    hist = [[], [], []]
    sample_every = 2.0
    next_sample = 0.0
    tripped = None
    while t <= max_s and runner.active():
        temps = [plant.surf, plant.rear, plant.core]
        slopes = []
        for i in range(3):
            h = hist[i]
            h.append((t, temps[i]))
            while h and t - h[0][0] > 3.0:
                h.pop(0)
            slopes.append((h[-1][1] - h[0][1]) / (h[-1][0] - h[0][0]) if len(h) > 1 and h[-1][0] > h[0][0] else 0.0)
        heat = runner.tick(t, dt, temps, slopes, plant, s)
        if runner.index != last_index:
            step_marks.append((t, runner.index))
            last_index = runner.index
            wait_since = None
        if runner.active() and runner.waiting_for_next():
            if wait_since is None:
                wait_since = t
            elif t - wait_since >= next_after_s:
                runner.next(t, temps)
                wait_since = None
                continue
        for k, tc_temp in (("1", plant.surf), ("2", plant.rear), ("3", plant.core)):
            lim = cut.get(k)
            if lim and tc_temp >= lim and not (k == "3" and not s.get("tc3_is_core")):
                tripped = "TC%s reaches its %g °C cutoff at %s" % (k, lim, _mmss(t))
                runner.stop(tripped, state="tripped")
                break
        if t >= next_sample:
            next_sample = t + sample_every
            out["t"].append(round(t, 1))
            out["tc1"].append(round(plant.surf, 2))
            out["tc2"].append(round(plant.rear, 2))
            out["core"].append(round(plant.core, 2))
            out["heat"].append(1 if heat else 0)
            out["sp"].append(None if runner.setpoint is None else round(runner.setpoint, 2))
        if heat:
            on_time += dt
        model.step(plant, m, model.heater_power(s, heat), room, dt)
        max_core = max(max_core, plant.core)
        t += dt
    # Record the cool-down for a few minutes after the program, as the run would.
    end_t = t
    cool_until = t + 300.0
    while t <= cool_until:
        model.step(plant, m, 0.0, room, dt)
        t += dt
        if t >= next_sample:
            next_sample = t + sample_every
            out["t"].append(round(t, 1))
            out["tc1"].append(round(plant.surf, 2))
            out["tc2"].append(round(plant.rear, 2))
            out["core"].append(round(plant.core, 2))
            out["heat"].append(0)
            out["sp"].append(None)
    out["steps"] = [{"t": round(a, 1), "index": i} for a, i in step_marks]
    out["events"] = events
    out["program_s"] = round(end_t, 1)
    out["heat_on_s"] = round(on_time, 1)
    out["energy_kJ"] = round(model.heater_power(s) * on_time / 1000.0, 1)
    out["peak_tc1"] = max(out["tc1"]) if out["tc1"] else None
    out["peak_tc2"] = max(out["tc2"]) if out["tc2"] else None
    out["peak_core"] = round(max_core, 1)
    w = out["warnings"]
    if tripped:
        w.append(tripped + "; the program would stop there.")
    if runner.active():
        w.append("Still running after %s; a step may never finish (unreachable temperature?)." % _mmss(max_s))
    reach = model.steady_surface(m, model.heater_power(s), room)
    for i, st in enumerate(program["steps"]):
        if st["type"] in ("full", "ramp", "hold") and st.get("temp") is not None and st["tc"] == 1 and st["temp"] > reach - 5:
            w.append("Step %d: TC1 %g °C is above what %g V can reach (about %d °C)." % (i + 1, st["temp"], s["variac_V"], reach))
    rating = float(s.get("heater_max_C") or 0)
    if rating and max_core > rating:
        w.append("Model puts the cartridge core near %d °C, above its %d °C rating." % (max_core, rating))
    return out


def _mmss(t):
    t = int(round(t))
    return "%d:%02d" % (t // 60, t % 60)
