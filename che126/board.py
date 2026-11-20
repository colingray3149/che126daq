"""Serial link to the che126-daq firmware (firmware/che126_daq), plus a practice board.

Firmware protocol, one line each way (115200 baud):
  board -> S,<ms>,<t1>,<t2>,<t3>,<f1>,<f2>,<f3>,<heat>,<tripped>   every sample
           #ID che126-daq <version> relay=<NC|NO>   #TRIP <LIMIT|FAULT> <amp>
           #LEASE   #OK ...   #ERR ...
  host  -> HEAT 1 <lease_ms> | HEAT 0 | LIM <amp> <C> | FAULT <ms> | RATE <ms>
           CLEAR | RELAY NC|NO | ID | CFG
t1..t3 are amplifiers 1..3 (pins 22/24/26, 28/30/32, 34/36/38); the app maps them
to TC1..TC3 using Settings > Thermocouples.
"""

from __future__ import annotations

import math
import queue
import random
import re
import threading
import time

import serial
import serial.tools.list_ports

from . import model

BAUD = 115200
FIRMWARE_VERSION = "1"
ARDUINO_VIDS = (0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4)


def list_ports():
    ports = []
    for p in serial.tools.list_ports.comports():
        desc = p.description or ""
        ports.append({
            "device": p.device,
            "description": desc,
            "arduino": bool(p.vid in ARDUINO_VIDS or "arduino" in desc.lower()),
        })
    ports.sort(key=lambda p: (not p["arduino"], p["device"]))
    return ports


class BoardLink:
    """Keeps a connection open, reconnecting forever; calls back into the app."""

    def __init__(self, app):
        self.app = app
        self.ser = None
        self.port = None
        self.lock = threading.Lock()
        self.status = "disconnected"  # disconnected | connecting | connected | wrong_firmware | no_response
        self.detail = ""
        self.firmware = None
        self.relay = None
        self.paused = threading.Event()  # set while the firmware uploader owns the port
        self.wake = threading.Event()
        self.drop_requested = False
        self.last_line = 0.0
        self.stopped = False
        self.thread = threading.Thread(target=self._run, name="board", daemon=True)

    def start(self):
        self.thread.start()

    def pick_port(self):
        forced = self.app.forced_port or self.app.settings.get().get("port")
        if forced:
            return forced
        for p in list_ports():
            if p["arduino"]:
                return p["device"]
        return None

    def send(self, line):
        with self.lock:
            ser = self.ser
            if not ser:
                return False
            try:
                ser.write((line + "\n").encode("ascii"))
                return True
            except (serial.SerialException, OSError, ValueError) as e:
                self.app.event("Write to board failed: %s" % e)
                self.drop_requested = True
                return False

    def reconnect(self):
        self.drop_requested = True
        self.wake.set()

    def release(self):
        """Close the port and stop reconnecting (firmware upload)."""
        self.paused.set()
        self.reconnect()
        deadline = time.time() + 3
        while self.ser is not None and time.time() < deadline:
            time.sleep(0.05)

    def resume(self):
        self.paused.clear()
        self.wake.set()

    def _set(self, status, detail):
        if (status, detail) != (self.status, self.detail):
            self.status, self.detail = status, detail
            self.app.broadcast_state()

    def _close(self, why):
        with self.lock:
            ser, self.ser = self.ser, None
        if ser:
            try:
                ser.close()
            except Exception:
                pass
            self.app.event("Board disconnected (%s)" % why)
        self.firmware = None
        self.app.on_board_lost()

    def _open(self, port):
        if port.startswith("sim://"):
            return SimBoard(self.app)
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = BAUD
        ser.timeout = 0.2
        ser.write_timeout = 1.0
        ser.open()
        return ser

    def _configure(self):
        s = self.app.settings.get()
        self.send("RELAY %s" % ("NO" if s.get("relay") == "NO" else "NC"))
        self.send("RATE %d" % int(s.get("sample_ms") or 250))
        self.send("FAULT %d" % int(max(0.0, float(s.get("fault_trip_s") or 0)) * 1000))
        self.app.send_limits()

    def _run(self):
        wait = 1.0
        while not self.stopped:
            if self.paused.is_set():
                self._set("disconnected", "firmware upload in progress")
                self.wake.wait(0.5)
                self.wake.clear()
                continue
            port = self.pick_port()
            if not port:
                self._set("disconnected", "no Arduino found; plug in the USB cable")
                self.wake.wait(2.0)
                self.wake.clear()
                continue
            self.port = port
            self._set("connecting", port)
            try:
                ser = self._open(port)
            except (serial.SerialException, OSError, ValueError) as e:
                self._set("disconnected", "%s: %s" % (port, _short(e)))
                self.wake.wait(wait)
                self.wake.clear()
                wait = min(wait * 1.5, 5.0)
                continue
            wait = 1.0
            self.drop_requested = False
            with self.lock:
                self.ser = ser
            self.firmware = None
            self.app.event("Opened %s" % port)
            self._read(ser, port)
            self.wake.wait(0.5)
            self.wake.clear()

    def _read(self, ser, port):
        opened = time.monotonic()
        self.last_line = opened
        asked = 0.0
        buf = b""
        while not self.stopped:
            if self.drop_requested:
                self._close("reconnect")
                return
            now = time.monotonic()
            if self.firmware is None and now - asked > 1.0 and now - opened > 0.3:
                asked = now
                self.send("ID")
            if self.firmware is None and now - opened > 6.0 and self.status not in ("wrong_firmware", "no_response"):
                self._set("no_response", "%s does not answer; upload the firmware (Settings)" % port)
            if self.firmware and now - self.last_line > 3.0:
                self._close("no data for 3 s")
                return
            try:
                chunk = ser.read(getattr(ser, "in_waiting", 0) or 1)
            except (serial.SerialException, OSError, TypeError, AttributeError, ValueError) as e:
                self._close(_short(e) or "read failed")
                return
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self.last_line = time.monotonic()
                try:
                    self._line(raw.decode("ascii", "replace").strip(), port)
                except Exception as e:  # never let one bad line kill the link
                    self.app.event("Ignored bad line from board (%s)" % e)
            if len(buf) > 4096:
                buf = b""

    def _line(self, line, port):
        if not line:
            return
        if line.startswith("S,"):
            if not self.firmware:
                return
            parts = line.split(",")
            if len(parts) != 10:
                return
            try:
                temps = [float(x) for x in parts[2:5]]
                faults = [int(x) for x in parts[5:8]]
            except ValueError:
                return
            temps = [t if math.isfinite(t) else None for t in temps]
            self.app.on_sample(temps, faults, parts[8] == "1", parts[9] == "1")
        elif line.startswith("#ID "):
            m = re.match(r"#ID che126-daq (\S+) relay=(NC|NO)", line)
            if not m:
                return
            first = self.firmware is None
            self.firmware, self.relay = m.group(1), m.group(2)
            self._set("connected", port)
            if first:
                self.app.event("Board ready on %s (firmware %s, relay %s)" % (port, self.firmware, self.relay))
                self._configure()
                self.app.on_board_ready()
        elif line.startswith("#TRIP"):
            p = line.split()
            self.app.on_trip(p[1] if len(p) > 1 else "TRIP", int(p[2]) if len(p) > 2 and p[2].isdigit() else 0)
        elif line.startswith("#LEASE"):
            self.app.event("Board switched heat off: this computer stopped renewing it")
        elif line.startswith("#ERR"):
            self.app.event("Board: %s" % line[5:])
        elif line.startswith("#CTRL") or line.startswith("time_s,"):
            if self.status != "wrong_firmware":
                self._set("wrong_firmware", "the board runs the old EXP firmware; upload che126-daq in Settings")
                self.app.event("Old EXP firmware on %s; this app needs the che126-daq firmware" % port)

    def close(self):
        self.stopped = True
        self.wake.set()
        with self.lock:
            ser, self.ser = self.ser, None
        if ser:
            try:
                ser.close()
            except Exception:
                pass


def _short(e):
    return str(e).split("\n")[0][:160]


class SimBoard:
    """Practice board: speaks the firmware protocol over a fake port.

    The plant is the thermal model with slightly different numbers than the
    controller's copy, plus 0.25 C quantisation and noise, so practice runs look
    like real ones (overshoot, lag, rear rising late). Amplifier 2 = heater side,
    1 = barrier rear, 3 = cartridge core (internal TC).
    """

    def __init__(self, app):
        self.app = app
        self.out = queue.Queue()
        self.lim = [0.0, 0.0, 0.0]
        self.over = [0, 0, 0]
        self.fault_ms = 0
        self.rate = 0.25
        self.heat_req = False
        self.heat_until = 0.0
        self.tripped = False
        room = float(app.settings.get().get("room_C", 24.0))
        self.state = model.ThermalState(room, room, room, room)
        self.mismatch = {k: v * random.uniform(0.85, 1.15) for k, v in model.DEFAULT_MODEL.items()}
        self.last = time.monotonic()
        self.next_sample = self.last + 0.3
        self.relay = "NC"
        self.out.put(b"#ID che126-daq " + FIRMWARE_VERSION.encode() + b" relay=NC\n")

    in_waiting = 0

    def close(self):
        pass

    def write(self, data):
        for line in data.decode().splitlines():
            self._cmd(line.split())

    def _cmd(self, w):
        if not w:
            return
        now = time.monotonic()
        c = w[0]
        if c == "HEAT":
            if w[1:2] == ["0"]:
                self.heat_req = False
            elif self.tripped:
                self.out.put(b"#ERR tripped; send CLEAR first\n")
            else:
                self.heat_req = True
                self.heat_until = now + (int(w[2]) / 1000.0 if len(w) > 2 else 2.0)
        elif c == "LIM":
            self.lim[int(w[1]) - 1] = float(w[2])
            self.over[int(w[1]) - 1] = 0
            self.out.put(b"#OK LIM\n")
        elif c == "FAULT":
            self.fault_ms = int(w[1])
            self.out.put(b"#OK FAULT\n")
        elif c == "RATE":
            self.rate = max(0.1, int(w[1]) / 1000.0)
            self.out.put(b"#OK RATE\n")
        elif c == "CLEAR":
            self.tripped = False
            self.over = [0, 0, 0]
            self.out.put(b"#OK CLEAR\n")
        elif c == "RELAY" and len(w) > 1:
            self.relay = w[1]
            self.heat_req = False
            self.out.put(("#ID che126-daq %s relay=%s\n" % (FIRMWARE_VERSION, self.relay)).encode())
        elif c == "ID":
            self.out.put(("#ID che126-daq %s relay=%s\n" % (FIRMWARE_VERSION, self.relay)).encode())

    def read(self, n):
        deadline = time.monotonic() + 0.1
        while True:
            try:
                return self.out.get_nowait()
            except queue.Empty:
                pass
            if time.monotonic() >= deadline:
                return b""
            self._advance()
            time.sleep(0.01)

    def _advance(self):
        now = time.monotonic()
        dt, self.last = now - self.last, now
        if self.heat_req and now > self.heat_until:
            self.heat_req = False
            self.out.put(b"#LEASE\n")
        on = self.heat_req and not self.tripped
        s = self.app.settings.get()
        room = float(s.get("room_C", 24.0))
        model.step(self.state, self.mismatch, model.heater_power(s, on), room, dt)
        if now < self.next_sample:
            return
        self.next_sample = now + self.rate
        st = self.state
        temps = [st.rear, st.surf, st.core]
        temps = [round((v + random.gauss(0, 0.1)) * 4) / 4 for v in temps]
        for i in range(3):
            if self.lim[i] > 0 and temps[i] >= self.lim[i]:
                self.over[i] += 1
                if self.over[i] >= 2 and not self.tripped:
                    self.tripped = True
                    self.heat_req = False
                    self.out.put(b"#TRIP LIMIT %d\n" % (i + 1))
            else:
                self.over[i] = 0
        on = self.heat_req and not self.tripped
        ms = int(now * 1000) & 0x7FFFFFFF
        self.out.put(("S,%d,%.2f,%.2f,%.2f,0,0,0,%d,%d\n" % (ms, temps[0], temps[1], temps[2], on, self.tripped)).encode())
