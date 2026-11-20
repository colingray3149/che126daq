"""Tests for daq.py. Run from the repository root:

    python -m unittest discover tests -v

No hardware needed. test_firmware_sim.py additionally runs the real firmware in simavr
when the simulator is built (see tests/board_sim/).
"""

import json
import os
import random
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
sys.path.insert(0, ROOT)

from che126 import model, program, stk500  # noqa: E402
from che126.runs import Library, analyze, fit_barrier  # noqa: E402
from che126.settings import DEFAULTS, Settings  # noqa: E402


def settings(**over):
    s = json.loads(json.dumps(DEFAULTS))
    s.update(over)
    return s


def prog(*steps, **kw):
    p = {"name": "t", "steps": list(steps), "cutoffs": kw.get("cutoffs", {}), "end_when": kw.get("end_when", [])}
    return program.normalize(p)


class Plant:
    """Closed loop: runner + controller against the model with mismatched numbers."""

    def __init__(self, s, mismatch=1.0, start=24.0):
        self.s = s
        self.m = {k: v * mismatch for k, v in s["model"].items()}
        self.st = model.ThermalState(start, start, start, start)
        self.obs = model.Observer()
        self.t = 0.0
        self.heat = False
        self.hist = []

    def temps(self):
        return [round(self.st.surf * 4) / 4, round(self.st.rear * 4) / 4, None]

    def run(self, runner, seconds, dt=0.25, on_tick=None):
        log = []
        end = self.t + seconds
        while self.t < end and runner.active():
            temps = self.temps()
            self.hist.append((self.t, temps[0]))
            while self.t - self.hist[0][0] > 3:
                self.hist.pop(0)
            slope = (self.hist[-1][1] - self.hist[0][1]) / (self.hist[-1][0] - self.hist[0][0]) if len(self.hist) > 2 else 0.0
            self.obs.update(dt, self.heat, temps, self.s)
            self.heat = runner.tick(self.t, dt, temps, [slope, 0.0, 0.0], self.obs.state, self.s)
            model.step(self.st, self.m, model.heater_power(self.s, self.heat), self.s["room_C"], dt)
            self.t += dt
            log.append((self.t, self.st.surf, self.heat))
            if on_tick:
                on_tick(self)
        return log


class ProgramTests(unittest.TestCase):
    def test_validation_messages(self):
        with self.assertRaisesRegex(ValueError, "step 1: unknown action"):
            program.normalize({"steps": [{"type": "boil"}]})
        with self.assertRaisesRegex(ValueError, "step 1 temperature is required"):
            program.normalize({"steps": [{"type": "hold", "tc": 1}]})
        with self.assertRaisesRegex(ValueError, "step 1 time is required"):
            program.normalize({"steps": [{"type": "ramp", "tc": 1, "temp": 200}]})
        with self.assertRaisesRegex(ValueError, "TC must be 1, 2 or 3"):
            program.normalize({"steps": [{"type": "full", "tc": 4}]})
        with self.assertRaisesRegex(ValueError, "must be a number"):
            program.normalize({"steps": [{"type": "hold", "tc": 1, "temp": "hot"}]})

    def test_presets_load(self):
        folder = os.path.join(ROOT, "programs")
        names = [f for f in os.listdir(folder) if f.endswith(".json")]
        self.assertGreaterEqual(len(names), 3)
        for f in names:
            with open(os.path.join(folder, f), encoding="utf-8") as fh:
                program.normalize(json.load(fh))

    def test_next_always_advances(self):
        """NEXT works in every state: mid full-power, mid ramp, mid hold, while waiting."""
        events = []
        r = program.Runner(on_event=events.append)
        p = prog({"type": "full", "tc": 1, "temp": 500}, {"type": "ramp", "tc": 1, "temp": 600, "time": 100},
                 {"type": "hold", "tc": 1, "temp": 600, "time": 60}, {"type": "off", "tc": 1})
        temps = [150.0, 30.0, None]
        r.start(p, 0, temps)
        for i in range(4):
            self.assertEqual(r.index, i)
            self.assertTrue(r.next(1.0 + i, temps))
        self.assertEqual(r.state, "done")
        self.assertFalse(r.next(10, temps))

    def test_ramp_starts_from_current_reading(self):
        """Run 068: the old ramp started at 100 C while TC1 read 172 C, so it sat idle."""
        r = program.Runner()
        p = prog({"type": "ramp", "tc": 1, "temp": 200, "time": 90})
        r.start(p, 0, [172.0, 40.0, None])
        r.tick(0.0, 0.1, [172.0, 40.0, None], [0, 0, 0], None, settings())
        self.assertAlmostEqual(r.setpoint, 172.0, places=3)
        r.tick(45.0, 0.1, [180.0, 40.0, None], [0, 0, 0], None, settings())
        self.assertAlmostEqual(r.setpoint, 186.0, places=3)

    def test_hold_timer_starts_at_temperature(self):
        s = settings()
        r = program.Runner()
        r.start(prog({"type": "hold", "tc": 1, "temp": 300, "time": 60}), 0, [24.0, 24.0, None])
        r.tick(10, 0.1, [200.0, 30.0, None], [0, 0, 0], None, s)
        r.tick(500, 0.1, [250.0, 30.0, None], [0, 0, 0], None, s)
        self.assertTrue(r.active(), "the hold must not time out before reaching 300 C")
        r.tick(501, 0.1, [299.0, 30.0, None], [0, 0, 0], None, s)
        r.tick(560, 0.1, [300.0, 30.0, None], [0, 0, 0], None, s)
        self.assertTrue(r.active())
        r.tick(561.5, 0.1, [300.0, 30.0, None], [0, 0, 0], None, s)
        self.assertEqual(r.state, "done")

    def test_wait_for_next_keeps_holding(self):
        s = settings()
        r = program.Runner()
        r.start(prog({"type": "full", "tc": 1, "temp": 100, "wait": True}, {"type": "off", "tc": 1}), 0, [24.0, 24.0, None])
        self.assertTrue(r.tick(0, 0.1, [50.0, 24.0, None], [0, 0, 0], None, s))
        r.tick(1, 0.1, [101.0, 24.0, None], [0, 0, 0], None, s)
        self.assertEqual(r.state, "waiting")
        self.assertEqual(r.index, 0)
        r.tick(100, 0.1, [90.0, 24.0, None], [0, 0, 0], None, s)
        self.assertEqual(r.index, 0, "waits for NEXT, never moves on by itself")
        r.next(101, [90.0, 24.0, None])
        self.assertEqual(r.index, 1)

    def test_full_power_until_next(self):
        r = program.Runner()
        r.start(prog({"type": "full", "tc": 1}), 0, [24.0, 24.0, None])
        for t in range(0, 600, 50):
            self.assertTrue(r.tick(t, 0.1, [24.0 + t, 24.0, None], [0, 0, 0], None, settings()))
        self.assertTrue(r.waiting_for_next())

    def test_finish_early_condition(self):
        finished = []
        r = program.Runner(on_finish=lambda: finished.append(1))
        r.start(prog({"type": "full", "tc": 1}, end_when=[{"tc": 2, "op": ">=", "temp": 85}]), 0, [24.0, 24.0, None])
        self.assertTrue(r.tick(0, 0.1, [400.0, 80.0, None], [0, 0, 0], None, settings()))
        self.assertFalse(r.tick(1, 0.1, [400.0, 85.5, None], [0, 0, 0], None, settings()))
        self.assertEqual(r.state, "done")
        self.assertEqual(finished, [1])

    def test_missing_reading_does_not_heat_toward_a_temperature(self):
        r = program.Runner()
        r.start(prog({"type": "full", "tc": 1, "temp": 300}), 0, [None, 24.0, None])
        self.assertFalse(r.tick(0, 0.1, [None, 24.0, None], [0, 0, 0], None, settings()))


class ControlTests(unittest.TestCase):
    def closed_loop_hold(self, mode, target, volts, mismatch, seed):
        random.seed(seed)
        s = settings(variac_V=volts)
        s["control"]["mode"] = mode
        plant = Plant(s, mismatch)
        r = program.Runner()
        r.start(prog({"type": "hold", "tc": 1, "temp": target, "time": 600}), 0, plant.temps())
        log = plant.run(r, 1800)
        reached = [x for x in log if x[1] >= target - 2]
        self.assertTrue(reached, "never reached %g C" % target)
        t0 = reached[0][0]
        settled = [x[1] for x in log if x[0] > t0 + 60]
        peak = max(x[1] for x in log)
        return peak, min(settled), max(settled)

    def test_predictive_hold_no_big_overshoot(self):
        for target, volts, mismatch in ((300, 70, 1.0), (300, 100, 0.85), (500, 100, 1.15), (700, 100, 1.0), (150, 115, 0.9)):
            peak, lo, hi = self.closed_loop_hold("predictive", target, volts, mismatch, target)
            self.assertLess(peak, target + 15, "overshoot at %g C, %g V, mismatch %g" % (target, volts, mismatch))
            self.assertGreater(lo, target - 12, "sagged at %g C, %g V, mismatch %g" % (target, volts, mismatch))
            self.assertLess(hi, target + 12)

    def test_onoff_without_model(self):
        for target, volts in ((300, 100), (500, 85)):
            peak, lo, hi = self.closed_loop_hold("onoff", target, volts, 1.0, 1)
            self.assertLess(peak, target + 15)
            self.assertGreater(lo, target - 12)

    def test_voltage_scales_power(self):
        self.assertAlmostEqual(model.heater_power(settings(variac_V=120)), 500.0)
        self.assertAlmostEqual(model.heater_power(settings(variac_V=60)), 125.0)

    def test_preview_of_presets(self):
        s = settings()
        with open(os.path.join(ROOT, "programs", "700 C, 60 s hold (EXP5-6 style).json"), encoding="utf-8") as f:
            p = program.normalize(json.load(f))
        pv = program.preview(p, s)
        self.assertLess(pv["peak_tc1"], 712)
        self.assertGreater(pv["peak_tc1"], 695)
        self.assertFalse([w for w in pv["warnings"] if "cutoff" in w])
        self.assertEqual(len(pv["t"]), len(pv["tc1"]))

    def test_preview_flags_unreachable_and_cutoff(self):
        pv = program.preview(prog({"type": "hold", "tc": 1, "temp": 1400, "time": 10}), settings(variac_V=60), max_s=600)
        self.assertTrue(any("above what" in w for w in pv["warnings"]))
        pv = program.preview(prog({"type": "full", "tc": 1, "temp": 600}, cutoffs={"1": 400}), settings())
        self.assertTrue(any("cutoff" in w for w in pv["warnings"]))


class RunDataTests(unittest.TestCase):
    lib = Library(lambda: os.path.join(ROOT, "runs"), lambda: None)

    def test_legacy_mapping(self):
        d = self.lib.load("068")
        self.assertEqual(max(v for v in d["tc1"] if v is not None), 419.0)  # raw tc2_C = heater side
        self.assertEqual(max(v for v in d["tc2"] if v is not None), 110.0)
        self.assertTrue(any(d["heat"]))

    def test_known_results(self):
        a = analyze(self.lib.load("036"), 100, 300, 120)
        self.assertEqual(a["tc1"]["peak"], 714.0)
        self.assertEqual(a["tc2"]["peak"], 80.25)
        self.assertAlmostEqual(a["tc1_reach"]["700"], 248.4, delta=1)
        self.assertAlmostEqual(a["barrier"]["rear_gain"], 0.2, delta=0.03)

    def test_every_run_loads(self):
        for r in self.lib.list():
            d = self.lib.load(r["id"])
            self.assertEqual(len(d["t"]), len(d["tc1"]))
            self.lib.detail(r["id"])

    def test_catalog_covers_old_runs(self):
        cat = self.lib.catalog()
        for i in range(1, 69):
            self.assertIn("%03d" % i, cat)


class FirmwareFileTests(unittest.TestCase):
    def test_hex_parses(self):
        start, image = stk500.read_hex(os.path.join(ROOT, "firmware", "che126_daq", "che126_daq.hex"))
        self.assertEqual(start, 0)
        self.assertGreater(len(image), 4000)
        self.assertLess(len(image), 0x3E000)  # below the bootloader


class ApiTests(unittest.TestCase):
    """The whole app in practice mode, driven over HTTP like the page does."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        for d in ("web", "programs", "analysis", "firmware"):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(cls.tmp, d))
        os.makedirs(os.path.join(cls.tmp, "runs"))
        shutil.copytree(os.path.join(ROOT, "runs", "036"), os.path.join(cls.tmp, "runs", "036"))
        shutil.copy(os.path.join(ROOT, "runs", "catalog.json"), os.path.join(cls.tmp, "runs"))
        from che126.app import App
        from che126.server import serve

        cls.app = App(cls.tmp, forced_port="sim://")
        cls.server = serve(cls.app, os.path.join(cls.tmp, "web"), 0)
        cls.url = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.app.board.start()
        threading.Thread(target=cls.app.control_loop, daemon=True).start()
        deadline = time.time() + 10
        while time.time() < deadline and cls.app.temps[0] is None:
            time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.app.end_run()
        cls.app.board.close()
        cls.server.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=10) as r:
            return json.loads(r.read())

    def post(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_page_and_state(self):
        with urllib.request.urlopen(self.url + "/", timeout=5) as r:
            self.assertIn(b"CHE 126 DAQ", r.read())
        st = self.get("/api/state")
        self.assertEqual(st["board"]["status"], "connected")
        self.assertIsNotNone(st["temps"][0])

    def test_run_lifecycle(self):
        code, r = self.post("/api/cmd", {"cmd": "start", "title": "api test", "setup": "mica / Al", "variac_V": 90,
                                         "program": {"name": "p", "steps": [{"type": "full", "tc": 1, "temp": 40}, {"type": "hold", "tc": 1, "temp": 45}]}})
        self.assertEqual(code, 200, r)
        rid = r["run"]
        self.assertTrue(rid.startswith("p"), "practice runs must not take real run numbers")
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "practice-runs", rid[1:])))
        time.sleep(1.5)
        self.assertEqual(self.post("/api/cmd", {"cmd": "next"})[0], 200)
        self.assertEqual(self.post("/api/cmd", {"cmd": "note", "text": "hello"})[0], 200)
        st = self.get("/api/state")
        self.assertEqual(st["program"]["index"], 1)
        self.assertEqual(st["settings"]["variac_V"], 90)
        self.assertEqual(self.post("/api/cmd", {"cmd": "stop"})[0], 200)
        time.sleep(0.5)
        self.assertEqual(self.post("/api/cmd", {"cmd": "end"})[0], 200)
        d = self.get("/api/runs/" + rid)
        self.assertEqual(d["meta"]["setup"], "mica / Al")
        self.assertTrue(any("hello" in e["text"] for e in d["events"]))
        self.assertIn("hello", d["notes"], "a note typed during the run belongs in notes.md")
        self.assertTrue(any("NEXT" in e["text"] for e in d["events"]))
        data = self.get("/api/runs/%s/data" % rid)
        self.assertGreater(len(data["t"]), 3)
        self.assertEqual(self.post("/api/runs/%s/notes" % rid, {"text": "my comment"})[0], 200)
        self.assertEqual(self.get("/api/runs/" + rid)["notes"], "my comment")
        with open(os.path.join(self.tmp, "practice-runs", rid[1:], "notes.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Setup: mica / Al", text)
        self.assertIn("## Comments\n\nmy comment", text)

    def test_bad_input_is_a_plain_400(self):
        code, r = self.post("/api/cmd", {"cmd": "start", "program": {"steps": [{"type": "ramp", "tc": 1, "temp": 200}]}})
        self.assertEqual(code, 400)
        self.assertIn("time is required", r["error"])
        self.assertEqual(self.post("/api/settings", {"variac_V": -5})[0], 400)
        self.assertEqual(self.post("/api/settings", {"relay": "maybe"})[0], 400)
        self.assertEqual(self.post("/api/cmd", {"cmd": "hold", "tc": 1})[0], 400)
        self.assertEqual(self.post("/api/cmd", {"cmd": "explode"})[0], 400)
        req = urllib.request.Request(self.url + "/api/cmd", data=b"not json", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 400)
        # Another website posting a form or a cross-origin request must not reach the heater.
        for headers in ({"Content-Type": "text/plain"}, {"Content-Type": "application/json", "Origin": "http://evil.example"}):
            req = urllib.request.Request(self.url + "/api/cmd", data=b'{"cmd":"heat_on"}', headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=5)
            self.assertIn(cm.exception.code, (403, 415))
        self.assertIsNone(self.get("/api/state")["manual"])
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.url + "/runs/036/../../daq.py", timeout=5)

    def test_preview_and_programs(self):
        code, pv = self.post("/api/preview", {"program": {"name": "x", "steps": [{"type": "hold", "tc": 1, "temp": 200, "time": 30}]}, "next_after_s": 10})
        self.assertEqual(code, 200)
        self.assertGreater(pv["peak_tc1"], 190)
        code, r = self.post("/api/programs", {"name": "My test / program", "steps": [{"type": "off", "tc": 1, "time": 5}]})
        self.assertEqual(code, 200)
        names = [p["file"] for p in self.get("/api/programs")["programs"]]
        self.assertIn(r["file"], names)
        self.post("/api/programs/delete", {"file": r["file"]})
        self.assertNotIn(r["file"], [p["file"] for p in self.get("/api/programs")["programs"]])

    def test_cutoff_trips_and_clears(self):
        code, _ = self.post("/api/cmd", {"cmd": "start", "program": {"name": "c", "steps": [{"type": "full", "tc": 1}], "cutoffs": {"1": 35}}})
        self.assertEqual(code, 200)
        deadline = time.time() + 40
        while time.time() < deadline and not self.app.tripped:
            time.sleep(0.2)
        self.assertTrue(self.app.tripped)
        st = self.get("/api/state")
        self.assertEqual(st["program"]["state"], "tripped")
        self.assertIn("TC1", st["board"]["trip"])
        time.sleep(1)
        self.assertFalse(self.get("/api/state")["board"]["heat"])
        self.post("/api/cmd", {"cmd": "end"})
        self.post("/api/cmd", {"cmd": "clear"})
        time.sleep(0.6)
        self.assertFalse(self.get("/api/state")["board"]["tripped"])

    def test_reconnect_and_restart(self):
        self.assertEqual(self.post("/api/cmd", {"cmd": "reconnect"})[0], 200)
        self.assertEqual(self.post("/api/cmd", {"cmd": "restart"})[0], 200)
        deadline = time.time() + 10
        while time.time() < deadline and self.get("/api/state")["board"]["status"] != "connected":
            time.sleep(0.2)
        self.assertEqual(self.get("/api/state")["board"]["status"], "connected")


class SettingsTests(unittest.TestCase):
    def test_corrupt_file_falls_back(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        with open(path, "w") as f:
            f.write("{nope")
        s = Settings(path)
        self.assertIn("could not be read", s.problem)
        self.assertEqual(s.get()["variac_V"], DEFAULTS["variac_V"])

    def test_partial_file_keeps_defaults(self):
        path = os.path.join(tempfile.mkdtemp(), "settings.json")
        with open(path, "w") as f:
            json.dump({"variac_V": 85, "control": {"mode": "pi"}}, f)
        s = Settings(path).get()
        self.assertEqual(s["variac_V"], 85)
        self.assertEqual(s["control"]["mode"], "pi")
        self.assertEqual(s["control"]["min_pulse_s"], DEFAULTS["control"]["min_pulse_s"])


if __name__ == "__main__":
    unittest.main()
