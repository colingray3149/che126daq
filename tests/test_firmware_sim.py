"""The real firmware (firmware/che126_daq) on a simulated ATmega2560, driven by the app.

Needs the simulator binary (Linux): build it with tests/board_sim/build.sh, and the
firmware .elf from arduino-cli. Skipped otherwise:

    BOARD_SIM=/tmp/board_sim FIRMWARE_ELF=/path/che126_daq.ino.elf python -m unittest tests.test_firmware_sim -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
sys.path.insert(0, ROOT)

SIM = os.environ.get("BOARD_SIM", "")
ELF = os.environ.get("FIRMWARE_ELF", "")


def wait_for(cond, seconds, step=0.1):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return False


@unittest.skipUnless(SIM and ELF and os.path.exists(SIM) and os.path.exists(ELF), "simulator not built")
class FirmwareSim(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for d in ("web", "programs"):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(self.tmp, d))
        self.tty = os.path.join(self.tmp, "tty")
        self.ctl = os.path.join(self.tmp, "ctl")
        os.mkfifo(self.ctl)
        self.sim = subprocess.Popen([SIM, ELF, self.tty, self.ctl], stderr=subprocess.PIPE, text=True)
        self.ctl_f = open(self.ctl, "w")
        wait_for(lambda: os.path.exists(self.tty), 5)
        from che126.app import App

        self.app = App(self.tmp, forced_port=self.tty)
        self.events = []
        orig = self.app.event

        def capture(text):
            self.events.append(text)
            orig(text)

        self.app.event = capture
        self.app.board.start()
        self.assertTrue(wait_for(lambda: self.app.board.status == "connected" and self.app.temps[0] is not None, 15), self.app.board.detail)

    def tearDown(self):
        self.app.board.close()
        self.ctl_f.write("QUIT\n")
        self.ctl_f.close()
        try:
            self.sim.wait(3)
        except subprocess.TimeoutExpired:
            self.sim.kill()
        self.sim.stderr.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plant(self, line):
        self.ctl_f.write(line + "\n")
        self.ctl_f.flush()

    def control(self):
        threading.Thread(target=self.app.control_loop, daemon=True).start()

    def test_reads_mapped_channels(self):
        # Harness: amplifier 2 = heater side (24.5 C), amplifier 1 = rear (24.0 C), 3 missing.
        self.assertAlmostEqual(self.app.temps[0], 24.5, delta=0.6)
        self.assertAlmostEqual(self.app.temps[1], 24.0, delta=0.6)
        self.assertIsNone(self.app.temps[2])
        self.assertEqual(self.app.faults[2], 8)

    def test_program_heats_then_stops(self):
        self.control()
        self.app.start_run({"name": "fw", "steps": [{"type": "full", "tc": 1, "temp": 30}]}, "fw", "", None)
        self.assertTrue(wait_for(lambda: self.app.board_heat, 5), "relay never turned on")
        self.assertTrue(wait_for(lambda: self.app.runner.state == "done", 60), "never reached 30 C")
        self.assertTrue(wait_for(lambda: not self.app.board_heat, 3), "relay stayed on after the program")
        self.app.end_run()

    def test_board_cutoff_trips_without_the_computer(self):
        self.app.send_limits = lambda: None  # only the board's own limit below
        self.app.board.send("LIM 2 100")
        self.app.board.send("HEAT 1 5000")
        self.assertTrue(wait_for(lambda: self.app.board_heat, 3))
        self.plant("SET 2 150")
        self.assertTrue(wait_for(lambda: self.app.tripped, 3), "board did not trip")
        self.assertTrue(any("TC1 reached its limit" in e for e in self.events))
        self.assertTrue(wait_for(lambda: not self.app.board_heat, 2))
        self.app.board.send("HEAT 1 5000")
        time.sleep(1)
        self.assertFalse(self.app.board_heat, "HEAT 1 must be refused while tripped")
        self.plant("SET 2 30")
        time.sleep(1)
        self.app.board.send("CLEAR")
        self.assertTrue(wait_for(lambda: not self.app.tripped, 3))

    def test_lease_expires_when_computer_goes_quiet(self):
        self.app.board.send("HEAT 1 600")
        self.assertTrue(wait_for(lambda: self.app.board_heat, 2))
        self.assertTrue(wait_for(lambda: not self.app.board_heat, 2), "heat stayed on after the lease")
        self.assertTrue(wait_for(lambda: any("stopped renewing" in e for e in self.events), 2))

    def test_single_glitch_does_not_trip(self):
        self.app.board.send("LIM 2 500")
        time.sleep(0.6)
        self.plant("GLITCH 2")
        time.sleep(1.5)
        self.assertFalse(self.app.tripped, "one 2048 C frame must not trip the cutoff")

    def test_sensor_fault_trips_when_enabled(self):
        self.app.board.send("FAULT 1000")
        self.app.board.send("LIM 1 200")
        self.plant("FAULT 1 1")
        self.assertTrue(wait_for(lambda: self.app.tripped, 4))
        self.assertTrue(any("stopped giving readings" in e for e in self.events))
        self.plant("FAULT 1 0")

    def test_relay_polarity_persists(self):
        self.app.board.send("RELAY NO")
        self.assertTrue(wait_for(lambda: self.app.board.relay == "NO", 3))
        self.app.board.send("RELAY NC")
        self.assertTrue(wait_for(lambda: self.app.board.relay == "NC", 3))


if __name__ == "__main__":
    unittest.main()
