"""The running DAQ: board link, control loop, program, recording, live data."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime

from . import model, program as prog
from .board import BoardLink
from .runs import Library, Run, run_ids
from .settings import Settings
from .util import atomic_write, iso, safe_name

TC_COUNT = 3


class App:
    def __init__(self, root, forced_port=""):
        self.root = root
        self.settings_path = os.path.join(root, "settings.json")
        self.programs_dir = os.path.join(root, "programs")
        self.firmware_hex = os.path.join(root, "firmware", "che126_daq", "che126_daq.hex")
        self.settings = Settings(self.settings_path)
        self.forced_port = forced_port
        self.lock = threading.RLock()
        self.clients = []
        self.clients_lock = threading.Lock()
        self.board = BoardLink(self)
        self.runner = self._new_runner()
        self.practice = forced_port == "sim://"
        self.practice_dir = os.path.join(root, "practice-runs")
        self.library = Library(lambda: self.settings.runs_dir(self.root), lambda: self.run.number if self.run else None,
                               lambda: self.practice_dir)
        self.run = None
        self.session_start = time.monotonic()
        self.live = []  # (t_session, tc1, tc2, tc3, heat, sp, sp_tc)
        self.live_max = 4 * 3600 * 4
        self.events = []
        self.temps = [None] * TC_COUNT
        self.faults = [0] * TC_COUNT
        self.history = [[] for _ in range(TC_COUNT)]
        self.observer = model.Observer()
        self.board_heat = False
        self.tripped = False
        self.trip_text = ""
        self.want_heat = False
        self._last_off = 0.0
        self.manual = None  # None | {"mode": "on"} | {"mode": "hold", "tc": n, "temp": C}
        self.manual_ctrl = model.Controller()
        self.last_sample = 0.0
        self.caffeinate = None
        os.makedirs(self.settings.runs_dir(root), exist_ok=True)
        os.makedirs(self.programs_dir, exist_ok=True)
        if self.settings.problem:
            self.event(self.settings.problem)

    def _new_runner(self):
        return prog.Runner(on_event=self._runner_event, on_finish=self._program_finished)

    def _runner_event(self, text):
        self.event(text)
        if text.startswith("Step ") and self.run and self.runner.active():
            self._reforecast()

    def _reforecast(self):
        """Redraw the predicted run from now: the remaining steps, from the current
        readings, so the grey line stays honest when NEXT comes later than assumed."""
        run, runner = self.run, self.runner
        if not run or not runner.program or not run.meta.get("predicted"):
            return
        rest = dict(runner.program, steps=runner.program["steps"][runner.index:])
        temps, now = list(self.temps), run.elapsed()
        s = self.settings.get()

        def work():
            try:
                pv = prog.preview(rest, s, temps)
                old = run.meta.get("predicted") or {"t": [], "tc1": [], "tc2": [], "heat": []}
                keep = [i for i, t in enumerate(old["t"]) if t < now]
                new = {k: [old[k][i] for i in keep] for k in ("t", "tc1", "tc2", "heat")}
                for k in ("tc1", "tc2", "heat"):
                    new[k] += pv[k]
                new["t"] += [round(t + now, 1) for t in pv["t"]]
                run.meta["predicted"] = new
                self.push("predicted", new)
            except Exception:
                traceback.print_exc()

        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- events
    def event(self, text):
        entry = {"t": round(time.monotonic() - self.session_start, 1), "utc": iso(), "text": text}
        with self.lock:
            self.events.append(entry)
            del self.events[:-300]
            if self.run:
                try:
                    self.run.write_event(text)
                except Exception as e:  # a full disk must not stop the board link
                    entry["text"] += " (not saved: %s)" % e
        try:
            print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), text), flush=True)
        except Exception:
            pass
        self.push("event", entry)

    def push(self, kind, payload):
        msg = "event: %s\ndata: %s\n\n" % (kind, json.dumps(payload, separators=(",", ":")))
        with self.clients_lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

    def broadcast_state(self):
        self.push("state", self.state())

    # ---------------------------------------------------------------- mapping
    def amp_of(self, tc):
        return int(self.settings.get()["tcs"][tc - 1]["amp"])

    def slope(self, i, window=3.0):
        h = self.history[i]
        if len(h) < 3:
            return None
        pts = [p for p in h if h[-1][0] - p[0] <= window]
        if len(pts) < 3:
            return None
        n = len(pts)
        mt = sum(p[0] for p in pts) / n
        mv = sum(p[1] for p in pts) / n
        den = sum((p[0] - mt) ** 2 for p in pts)
        return None if den <= 0 else sum((p[0] - mt) * (p[1] - mv) for p in pts) / den

    def current_cutoffs(self):
        if self.manual:
            return self.manual.get("cutoffs") or {}
        if self.runner.program and (self.runner.active() or self.run):
            return self.runner.program.get("cutoffs") or {}
        return {}

    def send_limits(self, cut=None):
        """Board cutoffs (manual control's, else the program's), per amplifier."""
        cut = self.current_cutoffs() if cut is None else cut
        per_amp = {1: 0.0, 2: 0.0, 3: 0.0}
        for tc in (1, 2, 3):
            v = cut.get(str(tc))
            if v:
                amp = self.amp_of(tc)
                per_amp[amp] = v if not per_amp[amp] else min(per_amp[amp], v)
        for amp, v in per_amp.items():
            self.board.send("LIM %d %g" % (amp, v))

    # ---------------------------------------------------------------- board callbacks
    def on_board_ready(self):
        if self.tripped and not (self.runner.state == "tripped"):
            self.board.send("CLEAR")

    def on_board_relay(self, relay):
        """The board's stored relay polarity is the truth; mirror it in settings."""
        if self.settings.get().get("relay") != relay:
            self.settings.update({"relay": relay})
            self.event("Relay wiring on the board is COM-%s; settings updated to match" % relay)

    def on_board_lost(self):
        with self.lock:
            self.board_heat = False
        self.broadcast_state()

    def on_trip(self, reason, amp):
        tcs = self.settings.get()["tcs"]
        idx = [i for i, t in enumerate(tcs) if int(t["amp"]) == amp]
        who = "/".join("TC%d" % (i + 1) for i in idx) or "amplifier %d" % amp
        if reason == "LIMIT":
            limit = (self.current_cutoffs() or {}).get(str(idx[0] + 1)) if idx else None
            reading = self.temps[idx[0]] if idx else None
            text = "Cutoff: %s passed its %s limit%s" % (
                who, ("%g °C" % limit) if limit else "", (" (read %.1f °C)" % reading) if reading is not None else "")
        elif reason == "FAULT":
            text = "Cutoff: %s stopped giving readings" % who
        else:
            text = "Board trip on %s" % who
        with self.lock:
            self.tripped = True
            self.trip_text = text
            self.runner.stop(text, state="tripped")
            self.manual = None
        self.event(text + ". Program stopped, heat off. Clear the cutoff once the cause is fixed.")
        self.broadcast_state()

    def on_sample(self, raw, faults, heat, tripped):
        s = self.settings.get()
        now = time.monotonic()
        with self.lock:
            dt = now - self.last_sample if self.last_sample else 0.25
            for i, t in enumerate(s["tcs"]):
                a = int(t["amp"]) - 1
                v = raw[a]
                self.temps[i] = v
                self.faults[i] = faults[a]
                if v is not None:
                    self.history[i].append((now, v))
                    if len(self.history[i]) > 200:
                        del self.history[i][:-200]
            prev_heat = self.board_heat
            self.board_heat = heat
            if tripped and not self.tripped:
                self.tripped = True
                self.trip_text = self.trip_text or "The board is tripped"
            elif not tripped and self.tripped:
                self.tripped = False
                self.trip_text = ""
            self.last_sample = now
            sp, sp_tc = self.setpoint()
            tsess = round(now - self.session_start, 2)
            self.live.append((tsess, self.temps[0], self.temps[1], self.temps[2], 1 if heat else 0, sp, sp_tc))
            if len(self.live) > self.live_max:
                del self.live[: len(self.live) - self.live_max]
            run_t = None
            if self.run:
                step = str(self.runner.index + 1) if self.runner.active() else ("manual" if self.manual else "")
                try:
                    self.run.write_sample(self.temps, heat, sp, sp_tc, step, self.faults)
                except Exception as e:
                    self.event("Could not save a sample: %s" % e)
                run_t = round(self.run.elapsed(), 2)
            try:
                obs_temps = [self.temps[0], self.temps[1], self.temps[2] if s.get("tc3_is_core") else None]
                self.observer.update(min(dt, 2.0), prev_heat, obs_temps, s)
            except Exception:
                traceback.print_exc()
                self.observer.reset()
            core = self.observer.state.core if self.observer.state else None
        self.push("sample", {
            "t": tsess, "rt": run_t, "tc": self.temps, "heat": 1 if heat else 0, "sp": sp, "sp_tc": sp_tc,
            "faults": self.faults, "tripped": tripped, "core": None if core is None else round(core, 1),
        })

    def setpoint(self):
        if self.runner.active() and self.runner.setpoint is not None:
            return self.runner.setpoint, self.runner.current()["tc"]
        if self.manual and self.manual.get("mode") == "hold":
            return self.manual["temp"], self.manual["tc"]
        return None, None

    # ---------------------------------------------------------------- control loop
    def renew_heat(self):
        """Called right after each sample line: tell the board what the control loop decided."""
        lease = int(self.settings.get().get("lease_ms") or 2000)
        if self.want_heat:
            self.board.send("HEAT 1 %d" % lease)
        elif self.board_heat or time.monotonic() - self._last_off > 2.0:
            self._last_off = time.monotonic()
            self.board.send("HEAT 0")

    def control_loop(self):
        last_tick = time.monotonic()
        last_state = 0.0
        self._last_off = 0.0
        while True:
            time.sleep(0.1)
            now = time.monotonic()
            dt, last_tick = now - last_tick, now
            try:
                s = self.settings.get()
                with self.lock:
                    stale = now - self.last_sample > max(2.0, 4 * float(s.get("sample_ms") or 250) / 1000.0)
                    slopes = [self.slope(i) for i in range(TC_COUNT)]
                    obs = self.observer.state
                    if self.tripped or stale:
                        want = False
                        if self.runner.active():
                            self.runner.tick(now, dt, self.temps, slopes, obs, s)  # keep step timers honest
                    elif self.runner.active():
                        want = self.runner.tick(now, dt, self.temps, slopes, obs, s)
                    elif self.manual and self.manual["mode"] == "on":
                        want = True
                    elif self.manual:
                        tc = self.manual["tc"]
                        temp = self.manual["temp"]
                        want = self.manual_ctrl.output(now, dt, tc, temp, lambda a: temp, self.temps[tc - 1], slopes[tc - 1], obs, s)
                    else:
                        want = False
                    turned_off = self.want_heat and not want
                    self.want_heat = want
                if turned_off:
                    self.board.send("HEAT 0")  # don't wait for the next sample to stop heating
                if now - last_state > 1.0:
                    last_state = now
                    self.broadcast_state()
                    self._windows_awake()
            except Exception:
                traceback.print_exc()

    def _program_finished(self):
        if self.runner.program and self.runner.program.get("end_run") and self.run:
            threading.Thread(target=lambda: (time.sleep(0.3), self.end_run("program finished")), daemon=True).start()

    # ---------------------------------------------------------------- commands
    def start_run(self, program, title, setup, volts):
        if volts not in (None, ""):
            try:
                volts = float(volts)
            except (TypeError, ValueError):
                raise ValueError("variac voltage must be a number")
            self.apply_settings({"variac_V": volts}, quiet=True)
        p = prog.normalize(program) if program else None
        if p and not p["steps"]:
            raise ValueError("the program has no steps")
        predicted = None
        if p:
            try:  # outside the lock: a long preview must not pause control
                pv = prog.preview(p, self.settings.get(), list(self.temps))
                predicted = {k: pv[k] for k in ("t", "tc1", "tc2", "heat")}
            except Exception:
                traceback.print_exc()
        with self.lock:
            if self.run:
                self._finish_run("a new run was started")
            # Practice runs (simulated rig) never take real run numbers.
            runs_dir = self.practice_dir if self.practice else self.settings.runs_dir(self.root)
            prefix = "p" if self.practice else ""
            os.makedirs(runs_dir, exist_ok=True)
            ids = run_ids(runs_dir)
            n = int(ids[-1]) + 1 if ids else 1
            while True:
                rid = prefix + "%03d" % n
                folder = os.path.join(runs_dir, rid[len(prefix):])
                try:
                    os.makedirs(folder)
                    break
                except FileExistsError:
                    n += 1
            s = self.settings.get()
            meta = {
                "run": rid,
                "title": (title or (p["name"] if p else "Recording"))[:120],
                "setup": (setup or "").strip()[:2000],
                "started_utc": iso(),
                "variac_V": s["variac_V"],
                "heater_W": s["heater_W"],
                "heater_rated_V": s["heater_rated_V"],
                "full_power_W": round(model.heater_power(s)),
                "tc_names": [t["name"] for t in s["tcs"]],
                "tc_amps": [int(t["amp"]) for t in s["tcs"]],
                "program": p,
                "settings": s,
                "firmware": self.board.firmware,
                "port": self.board.port,
                "predicted": predicted,
            }
            atomic_write(os.path.join(folder, "run.json"), json.dumps(meta, indent=1) + "\n")
            lines = ["# Run %s — %s" % (rid, meta["title"]), ""]
            lines.append("- Started: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
            lines.append("- Variac: %g V (about %d W at full power)" % (s["variac_V"], meta["full_power_W"]))
            lines.append("- TCs: " + "; ".join("TC%d %s = amplifier %d" % (i + 1, t["name"], int(t["amp"])) for i, t in enumerate(s["tcs"])))
            if meta["setup"]:
                lines.append("- Setup: %s" % meta["setup"].replace("\n", " "))
            if p:
                lines.append("- Program: %s" % p["name"])
                lines += ["  %d. %s" % (i + 1, prog.describe(st)) for i, st in enumerate(p["steps"])]
                cuts = ", ".join("TC%s %g °C" % (k, v) for k, v in p["cutoffs"].items() if v)
                if cuts:
                    lines.append("- Cutoffs: " + cuts)
            atomic_write(os.path.join(folder, "notes.md"), "\n".join(lines) + "\n\n## Comments\n\n")
            self.run = Run(folder, rid, meta)
            self.manual = None
            self.runner = self._new_runner()
            if p:
                self.runner.program = p
            self.event("Run %s started: %s, variac %g V" % (rid, meta["title"], s["variac_V"]))
            if p:
                self.board.send("CLEAR")
                self.tripped, self.trip_text = False, ""
                self.runner.start(p, time.monotonic(), self.temps)
            self.send_limits()
            self._keep_awake(True)
        self.broadcast_state()
        return rid

    def next(self):
        with self.lock:
            moved = self.runner.next(time.monotonic(), self.temps)
        if not moved:
            self.event("NEXT: no program is running")
        self.broadcast_state()

    def stop_heat(self):
        with self.lock:
            busy = self.runner.active() or self.manual
            self.runner.stop("Stopped by operator")
            self.manual = None
            self.want_heat = False
        self.board.send("HEAT 0")
        self.event("Stop: heat off" + ("" if busy else " (nothing was heating)"))
        self.broadcast_state()

    def end_run(self, why="ended by operator"):
        with self.lock:
            self.runner.stop("Run ended")
            self.manual = None
            self.want_heat = False
            self._finish_run(why)
        self.board.send("HEAT 0")
        self.send_limits()  # no run, no program: board cutoffs off
        self.broadcast_state()

    def _finish_run(self, why):
        if not self.run:
            return
        run = self.run
        run.write_event("Run ended: %s" % why)
        run.close()
        meta = dict(run.meta)
        meta.update({"ended_utc": iso(), "samples": run.samples, "duration_s": round(run.elapsed(), 1), "program_state": self.runner.state})
        try:
            atomic_write(os.path.join(run.folder, "run.json"), json.dumps(meta, indent=1) + "\n")
        except OSError:
            pass
        self.run = None
        self._keep_awake(False)
        self.event("Run %s ended (%s), %d samples saved in runs/%s/" % (run.number, why, run.samples, run.number))
        threading.Thread(target=self.refresh_readmes, args=(run.number,), daemon=True).start()

    def refresh_readmes(self, rid):
        """Rewrite runs/<rid>/README.md and runs/README.md (what GitHub shows)."""
        from .runs import write_index, write_run_readme

        try:
            write_run_readme(self.library, rid)
            write_index(self.library)
        except Exception:
            traceback.print_exc()

    def manual_heat(self, mode, tc=None, temp=None, cutoffs=None):
        if mode != "off" and self.tripped:
            raise ValueError("a cutoff has tripped; press Clear cutoff in the red banner first")
        if mode != "off" and not self.run:
            self.start_run(None, "Manual", "", None)  # manual heating is always recorded
        if mode == "hold":
            try:
                tc, temp = int(tc or 1), float(temp)
            except (TypeError, ValueError):
                raise ValueError("type a hold temperature")
            if not 1 <= tc <= 3:
                raise ValueError("TC must be 1, 2 or 3")
        if mode != "off":
            src = cutoffs if cutoffs is not None else self.settings.get().get("manual_cutoffs") or {}
            cut = prog.normalize({"steps": [], "cutoffs": src})["cutoffs"]
        with self.lock:
            if self.runner.active():
                self.runner.stop("Switched to manual control")
                self.event("Program stopped: manual control")
            if mode == "off":
                self.manual = None
                self.event("Manual: heat off")
            else:
                self.send_limits(cut)  # cutoffs reach the board before any heat
                if self.tripped:
                    self.board.send("CLEAR")
                cut_txt = ", ".join("TC%s %g °C" % (k, v) for k, v in cut.items() if v) or "none"
                if mode == "on":
                    self.manual = {"mode": "on", "cutoffs": cut}
                    self.event("Manual: full power (cutoffs %s)" % cut_txt)
                else:
                    self.manual_ctrl.reset()
                    self.manual = {"mode": "hold", "tc": tc, "temp": temp, "cutoffs": cut}
                    self.event("Manual: hold TC%d at %g °C (cutoffs %s)" % (tc, temp, cut_txt))
        if mode == "off":
            self.send_limits()
        self.broadcast_state()

    def clear_trip(self):
        self.board.send("CLEAR")
        with self.lock:
            self.tripped, self.trip_text = False, ""
        self.event("Cutoff cleared")
        self.broadcast_state()

    def restart(self):
        self.event("Restart: reloading settings and reconnecting the board")
        with self.lock:
            self.settings = Settings(self.settings_path)
            self.history = [[] for _ in range(TC_COUNT)]
            self.observer.reset()
        self.board.reconnect()
        self.broadcast_state()

    def apply_settings(self, changes, quiet=False):
        old = self.settings.get()
        new = self.settings.update(changes)
        if new["relay"] != old["relay"] and new["relay"] != self.board.relay:
            self.board.send("RELAY %s" % new["relay"])
            self.event("Relay wiring set to COM-%s (stored on the board)" % new["relay"])
        if new["sample_ms"] != old["sample_ms"]:
            self.board.send("RATE %d" % int(new["sample_ms"]))
        if new["fault_trip_s"] != old["fault_trip_s"]:
            self.board.send("FAULT %d" % int(float(new["fault_trip_s"]) * 1000))
        if new["tcs"] != old["tcs"]:
            with self.lock:
                self.history = [[] for _ in range(TC_COUNT)]
                self.observer.reset()
                if self.run:
                    self.run.meta["tc_names"] = [t["name"] for t in new["tcs"]]
                    self.run.meta["tc_amps"] = [int(t["amp"]) for t in new["tcs"]]
            if [t["amp"] for t in new["tcs"]] != [t["amp"] for t in old["tcs"]]:
                self.event("Thermocouple wiring changed: " + ", ".join("TC%d = amplifier %d" % (i + 1, int(t["amp"])) for i, t in enumerate(new["tcs"])))
            self.send_limits()
        if new["port"] != old["port"] and not self.forced_port:
            self.board.reconnect()
        if new["variac_V"] != old["variac_V"]:
            self.event("Variac set to %g V (about %d W at full power)" % (new["variac_V"], model.heater_power(new)))
        if not quiet:
            self.broadcast_state()
        return new

    def upload_firmware(self, port):
        from . import stk500

        self.event("Uploading firmware to %s; keep the USB cable in" % port)
        self.board.release()
        try:
            stk500.flash(port, self.firmware_hex, log=self.event)
            self.event("Firmware uploaded; reconnecting")
        finally:
            self.board.resume()

    def _windows_awake(self):
        """Windows keeps the 'stay awake' request per thread, so the long-lived control
        thread renews it every second while a run records."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if self.run else 0))
        except Exception:
            pass

    def _keep_awake(self, on):
        """Stop the laptop sleeping while a run records (macOS; Windows: _windows_awake)."""
        try:
            if sys.platform == "darwin":
                if on and not self.caffeinate:
                    self.caffeinate = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
                elif not on and self.caffeinate:
                    self.caffeinate.terminate()
                    self.caffeinate = None
        except Exception:
            pass

    # ---------------------------------------------------------------- programs
    def list_programs(self):
        out = []
        for f in sorted(os.listdir(self.programs_dir), key=str.lower):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.programs_dir, f), encoding="utf-8") as fh:
                        out.append({"file": f[:-5], "program": prog.normalize(json.load(fh))})
                except (OSError, ValueError) as e:
                    out.append({"file": f[:-5], "error": str(e)})
        return out

    def save_program(self, p):
        p = prog.normalize(p)
        if p["name"] in ("", "Untitled"):
            raise ValueError("give the program a name")
        if not p["steps"]:
            raise ValueError("add at least one step")
        name = safe_name(p["name"])
        atomic_write(os.path.join(self.programs_dir, name + ".json"), json.dumps(p, indent=2) + "\n")
        return name

    def delete_program(self, name):
        path = os.path.join(self.programs_dir, safe_name(name) + ".json")
        if os.path.exists(path):
            os.remove(path)

    def preview(self, p, next_after_s):
        p = prog.normalize(p)
        return prog.preview(p, self.settings.get(), self.temps, next_after_s=float(next_after_s or 30))

    # ---------------------------------------------------------------- views
    def state(self):
        s = self.settings.get()
        now = time.monotonic()
        with self.lock:
            obs = self.observer.state
            r = self.runner
            step = r.current()
            return {
                "board": {
                    "status": self.board.status,
                    "detail": self.board.detail,
                    "port": self.board.port,
                    "firmware": self.board.firmware,
                    "relay": self.board.relay,
                    "sim": self.forced_port == "sim://",
                    "heat": self.board_heat,
                    "tripped": self.tripped,
                    "trip": self.trip_text,
                    "stale": now - self.last_sample > 2.0,
                },
                "temps": self.temps,
                "faults": self.faults,
                "core_est": None if obs is None else round(obs.core, 1),
                "want_heat": self.want_heat,
                "manual": {k: v for k, v in self.manual.items() if k != "cutoffs"} if self.manual else None,
                "program": {
                    "state": r.state,
                    "name": r.program["name"] if r.program else "",
                    "steps": [prog.describe(x) for x in r.program["steps"]] if r.program else [],
                    "index": r.index,
                    "step_elapsed": round(now - r.step_started, 1) if r.active() else None,
                    "hold_elapsed": round(now - r.hold_started, 1) if r.active() and getattr(r, "hold_started", None) is not None else None,
                    "step_time": step.get("time") if step else None,
                    "waiting": r.waiting_for_next(),
                    "setpoint": r.setpoint,
                    "message": r.message,
                    "cutoffs": r.program.get("cutoffs") if r.program else None,
                },
                "run": {"id": self.run.number, "title": self.run.meta["title"], "elapsed": round(self.run.elapsed(), 1), "samples": self.run.samples} if self.run else None,
                "settings": s,
                "full_power_W": _safe(lambda: round(model.heater_power(s))),
                "max_surface_C": _safe(lambda: round(model.steady_surface(s["model"], model.heater_power(s), float(s["room_C"])))),
                "session_t": round(now - self.session_start, 1),
            }


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None
