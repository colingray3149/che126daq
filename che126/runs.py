"""Run folders: recording new runs, reading old ones, and the numbers shown per run.

runs/NNN/
  data.csv     one row per sample (new runs: time_s, utc, tc1_C, tc2_C, tc3_C, heat,
               setpoint_C, setpoint_tc, step, fault1..3)
  events.csv   what happened, with time since start
  notes.md     header written at start, your comments below "## Comments"
  run.json     settings, program, variac voltage and TC mapping used (new runs)
  plot.png     picture of the run (made by the page after the run ends)
runs/catalog.json  hand-written labels, setup and review for the runs before this app
                   (which raw channel was which TC, what the barrier was, how it went)

Runs 001-068 came from the earlier EXP2-EXP8 software: their data.csv has raw
channels tc1_C..tc3_C in amplifier order and catalog.json says which was which.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import threading
import time
from datetime import datetime

from .util import atomic_write, fnum, iso

NEW_HEADER = ["time_s", "utc", "tc1_C", "tc2_C", "tc3_C", "heat", "setpoint_C", "setpoint_tc", "step", "fault1", "fault2", "fault3"]

METRIC_HELP = {
    "peak": "Highest valid reading in the run, and when it happened (time since the run started).",
    "reach": "Time from the heater first switching on until TC1 first read at least this temperature.",
    "max_rate": "Fastest TC1 rise over any 20-second window.",
    "tc2_rise": "TC2 peak minus TC2 at the start of the run.",
    "tc2_delay": "How long after TC1's peak TC2 peaked. Positive: the rear kept heating after the heater side started cooling.",
    "dwell700": "Total time TC1 read 700 °C or more.",
    "heat_on": "Total time the relay was on (heat permitted). With the TC513 in the circuit, the TC513 may still have switched the heater off.",
    "energy": "Heater-on time × full power at the run's variac voltage (P = rated W × (V / rated V)²). An upper bound: losses and TC513 switching are not counted.",
    "rear_gain": "From a fitted barrier model: how many °C the rear would eventually rise per °C of heater-side rise if both were held steady. Lower = better barrier. Fit error shown in brackets.",
}


class Run:
    """An open recording."""

    def __init__(self, folder, number, meta):
        self.folder = folder
        self.number = number
        self.meta = meta
        self.start_mono = time.monotonic()
        self.data_f = open(os.path.join(folder, "data.csv"), "w", encoding="utf-8", newline="")
        self.data = csv.writer(self.data_f)
        self.data.writerow(NEW_HEADER)
        self.events_f = open(os.path.join(folder, "events.csv"), "w", encoding="utf-8", newline="")
        self.events = csv.writer(self.events_f)
        self.events.writerow(["time_s", "utc", "event"])
        self.samples = 0
        self.last_flush = 0.0

    def elapsed(self):
        return time.monotonic() - self.start_mono

    def write_sample(self, temps, heat, sp, sp_tc, step, faults):
        self.data.writerow([
            "%.3f" % self.elapsed(), iso(), fnum(temps[0]), fnum(temps[1]), fnum(temps[2]),
            1 if heat else 0, fnum(sp, 1), sp_tc or "", step, faults[0], faults[1], faults[2],
        ])
        self.samples += 1
        now = time.monotonic()
        if now - self.last_flush > 1.0:
            self.data_f.flush()
            self.last_flush = now

    def write_event(self, text):
        self.events.writerow(["%.3f" % self.elapsed(), iso(), text])
        self.events_f.flush()

    def close(self):
        for f in (self.data_f, self.events_f):
            try:
                f.flush()
                f.close()
            except OSError:
                pass


def run_ids(runs_dir):
    if not os.path.isdir(runs_dir):
        return []
    return sorted(d for d in os.listdir(runs_dir) if re.fullmatch(r"\d{3,}", d) and os.path.isdir(os.path.join(runs_dir, d)))


def notes_split(text):
    """(header, comments) split at the '## Comments' heading of notes.md."""
    m = re.search(r"^## Comments[^\n]*\n", text, re.M)
    if not m:
        return text.rstrip() + "\n\n", ""
    return text[: m.end()], text[m.end():].strip("\n")


def _float(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


class Library:
    def __init__(self, runs_dir_fn, active_run_fn):
        self.runs_dir = runs_dir_fn
        self.active = active_run_fn
        self.cache = {}
        self.lock = threading.Lock()

    def catalog(self):
        try:
            with open(os.path.join(self.runs_dir(), "catalog.json"), encoding="utf-8") as f:
                return json.load(f).get("runs", {})
        except (OSError, ValueError):
            return {}

    def folder(self, rid):
        if not re.fullmatch(r"\d{3,}", rid or ""):
            raise KeyError(rid)
        path = os.path.join(self.runs_dir(), rid)
        if not os.path.isdir(path):
            raise KeyError(rid)
        return path

    def meta(self, rid):
        try:
            with open(os.path.join(self.folder(rid), "run.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _cached(self, rid, name, build):
        path = os.path.join(self.folder(rid), "data.csv")
        try:
            st = os.stat(path)
            key = (st.st_mtime, st.st_size)
        except OSError:
            key = None
        with self.lock:
            hit = self.cache.get((rid, name))
            if hit and hit[0] == key:
                return hit[1]
        value = build()
        with self.lock:
            self.cache[(rid, name)] = (key, value)
        return value

    def load(self, rid):
        """Arrays for plots/analysis: t (s), tc1..tc3 (C or None), heat (0/1), sp, sp_tc."""
        return self._cached(rid, "data", lambda: self._load(rid))

    def _load(self, rid):
        folder = self.folder(rid)
        out = {"t": [], "tc1": [], "tc2": [], "tc3": [], "heat": [], "sp": [], "sp_tc": []}
        try:
            with open(os.path.join(folder, "data.csv"), encoding="utf-8", errors="replace") as f:
                rows = list(csv.reader(f))
        except OSError:
            return out
        if not rows:
            return out
        header = rows[0]
        if "host_elapsed_s" in header:
            return self._load_legacy(rid, folder, header, rows[1:])
        col = {n: i for i, n in enumerate(header)}

        def get(r, name):
            i = col.get(name)
            return _float(r[i]) if i is not None and i < len(r) else None

        for r in rows[1:]:
            t = get(r, "time_s")
            if t is None:
                continue
            out["t"].append(t)
            for k in ("tc1", "tc2", "tc3"):
                out[k].append(get(r, k + "_C"))
            out["heat"].append(1 if get(r, "heat") else 0)
            out["sp"].append(get(r, "setpoint_C"))
            sp_tc = get(r, "setpoint_tc")
            out["sp_tc"].append(int(sp_tc) if sp_tc else None)
        return out

    def _load_legacy(self, rid, folder, header, rows):
        cat = self.catalog().get(rid, {})
        mapping = cat.get("map") or {"tc1": 2, "tc2": 1, "tc3": 3}
        col = {n: i for i, n in enumerate(header)}
        out = {"t": [], "tc1": [], "tc2": [], "tc3": [], "heat": [], "sp": [], "sp_tc": []}
        start_epoch = None
        for r in rows:
            try:
                t = float(r[col["host_elapsed_s"]])
            except (ValueError, IndexError, KeyError):
                continue
            if start_epoch is None:
                try:
                    start_epoch = datetime.fromisoformat(r[col["utc"]]).timestamp() - t
                except (ValueError, KeyError, IndexError):
                    pass
            out["t"].append(t)
            for logical in ("tc1", "tc2", "tc3"):
                raw = mapping.get(logical)
                name = "tc%d_C" % raw if raw else None
                i = col.get(name)
                v = _float(r[i]) if i is not None and i < len(r) else None
                # Old firmware wrote 0.00 for a dead amplifier line and 2048 for a garbled frame.
                if v is not None and (v == 0.0 or v >= 1800):
                    v = None
                out[logical].append(v)
            out["sp"].append(None)
            out["sp_tc"].append(None)
        changes = []
        try:
            with open(os.path.join(folder, "events.csv"), encoding="utf-8", errors="replace") as f:
                for row in csv.reader(f):
                    if len(row) < 2 or start_epoch is None:
                        continue
                    m = re.search(r"heater_on=(True|False) -> [^;]*?heater_on=(True|False)", row[1])
                    if not m:
                        continue
                    try:
                        changes.append((datetime.fromisoformat(row[0]).timestamp() - start_epoch, m.group(2) == "True"))
                    except ValueError:
                        continue
        except OSError:
            pass
        state, j = False, 0
        for t in out["t"]:
            while j < len(changes) and changes[j][0] <= t:
                state = changes[j][1]
                j += 1
            out["heat"].append(1 if state else 0)
        return out

    def events(self, rid):
        try:
            with open(os.path.join(self.folder(rid), "events.csv"), encoding="utf-8", errors="replace") as f:
                rows = list(csv.reader(f))
        except OSError:
            return []
        out = []
        if rows and rows[0][:1] == ["time_s"]:
            for r in rows[1:]:
                if len(r) >= 3:
                    out.append({"t": _float(r[0]), "text": r[2]})
            return out
        # Legacy: utc,event. Times relative to the first data sample.
        start = None
        try:
            with open(os.path.join(self.folder(rid), "data.csv"), encoding="utf-8", errors="replace") as f:
                rd = csv.reader(f)
                h = next(rd)
                first = next(rd)
                start = datetime.fromisoformat(first[h.index("utc")]).timestamp() - float(first[h.index("host_elapsed_s")])
        except (OSError, StopIteration, ValueError):
            pass
        for r in rows[1:]:
            if len(r) < 2:
                continue
            try:
                ts = datetime.fromisoformat(r[0]).timestamp()
            except ValueError:
                continue
            if start is None:
                start = ts
            text = re.sub(r"; ?(Serial report, not physical proof|serial report, not physical proof)\.?", "", r[1])
            out.append({"t": round(ts - start, 1), "text": text})
        return out

    def started(self, rid, meta):
        if meta.get("started_utc"):
            return meta["started_utc"]
        try:
            with open(os.path.join(self.folder(rid), "data.csv"), encoding="utf-8", errors="replace") as f:
                f.readline()
                first = f.readline().split(",")
            if first and "T" in first[0]:
                return first[0]
            if len(first) > 1 and "T" in first[1]:
                return first[1]
        except OSError:
            pass
        try:
            with open(os.path.join(self.folder(rid), "events.csv"), encoding="utf-8", errors="replace") as f:
                f.readline()
                return f.readline().split(",")[0] or None
        except OSError:
            return None

    def summary(self, rid, cat=None):
        cat = cat if cat is not None else self.catalog().get(rid, {})
        meta = self.meta(rid)
        active = self.active()
        return {
            "id": rid,
            "title": meta.get("title") or cat.get("title") or "",
            "category": cat.get("category") or ("test" if meta.get("program") else ("recording" if meta else "other")),
            "started": self.started(rid, meta),
            "setup": meta.get("setup") or cat.get("setup") or "",
            "voltage": meta.get("variac_V") or cat.get("voltage"),
            "new": bool(meta),
            "recording": active == rid,
            "path": "runs/%s/" % rid,
        }

    def list(self):
        cat = self.catalog()
        out = []
        for rid in run_ids(self.runs_dir()):
            try:
                out.append(self.summary(rid, cat.get(rid, {})))
            except (KeyError, OSError):
                continue
        return out

    def notes(self, rid):
        try:
            with open(os.path.join(self.folder(rid), "notes.md"), encoding="utf-8", errors="replace") as f:
                return notes_split(f.read())[1]
        except OSError:
            return ""

    def save_notes(self, rid, text):
        path = os.path.join(self.folder(rid), "notes.md")
        header = "# Run %s\n\n## Comments\n" % rid
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                header, _ = notes_split(f.read())
            if "## Comments" not in header:
                header += "## Comments\n"
        atomic_write(path, header + "\n" + text.strip() + "\n")

    def detail(self, rid):
        folder = self.folder(rid)
        cat = self.catalog().get(rid, {})
        meta = self.meta(rid)
        images = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
        files = sorted(f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and not f.endswith(".tmp"))
        volts = meta.get("variac_V") or cat.get("voltage")
        heater_w = meta.get("heater_W") or cat.get("heater_W")
        rated_v = meta.get("heater_rated_V") or cat.get("heater_rated_V") or 120
        names = meta.get("tc_names") or cat.get("tc_names") or ["Heater side", "Barrier rear", "TC3"]
        return {
            "summary": self.summary(rid, cat),
            "review": cat.get("review") or "",
            "meta": dict({k: meta.get(k) for k in ("run", "title", "setup", "program", "variac_V", "full_power_W", "tc_names", "tc_amps", "ended_utc", "predicted")},
                         tc_shown=[bool(t.get("show", True)) for t in (meta.get("settings") or {}).get("tcs", [])] or None) if meta else {},
            "notes": self.notes(rid),
            "images": images,
            "files": files,
            "analysis": self._cached(rid, "analysis", lambda: analyze(self.load(rid), volts, heater_w, rated_v)),
            "metric_help": METRIC_HELP,
            "events": self.events(rid)[-500:],
            "tc_names": names,
        }


def analyze(d, volts, heater_w, rated_v):
    t = d["t"]
    if len(t) < 2:
        return {}
    heat_start = next((ti for ti, h in zip(t, d["heat"]) if h), None)
    res = {"duration_s": round(t[-1] - t[0], 1), "samples": len(t), "heat_start_s": heat_start}
    for k in ("tc1", "tc2", "tc3"):
        pts = [(v, ti) for ti, v in zip(t, d[k]) if v is not None]
        if pts:
            peak = max(pts)
            res[k] = {"start": round(pts[0][0], 2), "peak": round(peak[0], 2), "peak_t": round(peak[1], 1), "end": round(pts[-1][0], 2)}
    base = heat_start if heat_start is not None else t[0]
    if "tc1" in res:
        reach = {}
        for level in (100, 200, 400, 600, 700):
            for ti, v in zip(t, d["tc1"]):
                if ti >= base and v is not None and v >= level:
                    reach[str(level)] = round(ti - base, 1)
                    break
        res["tc1_reach"] = reach
        best, j = 0.0, 0
        tc1 = d["tc1"]
        for i in range(len(t)):
            if tc1[i] is None:
                continue
            while t[i] - t[j] > 20:
                j += 1
            k = j
            while k < i and tc1[k] is None:
                k += 1
            if k < i and t[i] - t[k] >= 5:
                best = max(best, (tc1[i] - tc1[k]) / (t[i] - t[k]))
        res["tc1_max_rate"] = round(best, 2)
        dwell = 0.0
        for i in range(1, len(t)):
            v = tc1[i - 1]
            if v is not None and v >= 700 and t[i] - t[i - 1] < 5:
                dwell += t[i] - t[i - 1]
        if dwell:
            res["tc1_dwell700_s"] = round(dwell, 1)
    if "tc1" in res and "tc2" in res:
        res["tc2_rise"] = round(res["tc2"]["peak"] - res["tc2"]["start"], 2)
        res["tc2_delay_s"] = round(res["tc2"]["peak_t"] - res["tc1"]["peak_t"], 1)
        if res["tc1"]["peak"] - res["tc1"]["start"] > 100 and res["tc2_rise"] > 5:
            fit = fit_barrier(t, d["tc1"], d["tc2"])
            if fit:
                res["barrier"] = fit
    on = 0.0
    for i in range(1, len(t)):
        if d["heat"][i - 1] and t[i] - t[i - 1] < 5:
            on += t[i] - t[i - 1]
    if on:
        res["heat_on_s"] = round(on, 1)
        if volts and heater_w:
            p = float(heater_w) * (float(volts) / float(rated_v)) ** 2
            res["power_W"] = round(p)
            res["energy_kJ"] = round(p * on / 1000.0, 1)
    return res


def fit_barrier(t, hot, rear):
    """Fit the two-stage barrier model (see model.py) with TC1 as the driving input.

    Returns rear_gain = steady rear rise per degree of heater-side rise, the three
    rates, and the RMS fit error. Coordinate descent in log space; well under a
    second for a typical run.
    """
    pts = [(ti, h, r) for ti, h, r in zip(t, hot, rear) if h is not None and r is not None]
    if len(pts) < 50:
        return None
    # Thin to about 1 sample per second.
    thin, last = [], -1e9
    for p in pts:
        if p[0] - last >= 1.0:
            thin.append(p)
            last = p[0]
    pts = thin
    room = pts[0][2]

    def err(a1, a2, b):
        m = r = room
        e = 0.0
        for i in range(1, len(pts)):
            dt = pts[i][0] - pts[i - 1][0]
            if dt > 10:
                dt = 10
            m += dt * (a1 * (pts[i - 1][1] - m) - a2 * (m - r))
            r += dt * (a2 * (m - r) - b * (r - room))
            e += (r - pts[i][2]) ** 2
        return e / (len(pts) - 1)

    x = [0.0015, 0.005, 0.004]
    cur = err(*x)
    steps = [0.6, 0.6, 0.6]
    for _ in range(60):
        improved = False
        for k in range(3):
            for f in (1 + steps[k], 1 / (1 + steps[k])):
                y = list(x)
                y[k] *= f
                e = err(*y)
                if e < cur:
                    x, cur, improved = y, e, True
        if not improved:
            steps = [s / 2 for s in steps]
            if max(steps) < 0.01:
                break
    a1, a2, b = x
    gain = 1.0 / (1.0 + b / a2 + b / a1)
    return {"rear_gain": round(gain, 3), "a1": round(a1, 5), "a2": round(a2, 5), "b": round(b, 5), "rmse_C": round(math.sqrt(cur), 2)}


def _mmss(s):
    if s is None:
        return "—"
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60)


def write_run_readme(lib, rid):
    """runs/NNN/README.md: what GitHub shows when you open the folder."""
    folder = lib.folder(rid)
    d = lib.detail(rid)
    sm, a = d["summary"], d["analysis"]
    names = d["tc_names"]
    lines = ["# Run %s%s" % (rid, " — " + sm["title"] if sm["title"] else ""), ""]
    meta = [sm["started"][:16].replace("T", " ") + " UTC" if sm["started"] else None,
            "%g V" % float(sm["voltage"]) if sm["voltage"] else None,
            "%s long" % _mmss(a.get("duration_s")) if a else None, sm["category"]]
    lines.append(" · ".join(x for x in meta if x))
    lines.append("")
    if sm["setup"]:
        lines += ["**Setup:** " + sm["setup"], ""]
    if d["review"]:
        lines += [d["review"], ""]
    prog = (d["meta"] or {}).get("program")
    if prog:
        from .program import describe

        lines.append("**Program:** " + prog["name"])
        lines += ["%d. %s" % (i + 1, describe(s)) for i, s in enumerate(prog["steps"])]
        lines.append("")
    rows = []
    for k, i in (("tc1", 0), ("tc2", 1), ("tc3", 2)):
        if k in a:
            rows.append("| TC%d %s peak | %.1f °C at %s |" % (i + 1, names[i] if i < len(names) else "", a[k]["peak"], _mmss(a[k]["peak_t"])))
    for lvl, t in (a.get("tc1_reach") or {}).items():
        rows.append("| TC1 reached %s °C after heat on | %s |" % (lvl, _mmss(t)))
    if a.get("tc2_rise") is not None:
        rows.append("| TC2 rise | %.1f °C |" % a["tc2_rise"])
    if a.get("barrier"):
        rows.append("| Fitted rear gain | %.2f (±%.1f °C) |" % (a["barrier"]["rear_gain"], a["barrier"]["rmse_C"]))
    if a.get("heat_on_s"):
        rows.append("| Relay on | %s |" % _mmss(a["heat_on_s"]))
    if rows:
        lines += ["| | |", "|---|---|"] + rows + [""]
    for img in d["images"]:
        lines += ["![%s](%s)" % (img, img), ""]
    notes = d["notes"].strip()
    if notes:
        lines += ["## Comments", "", notes, ""]
    lines.append("Files: " + " · ".join("[%s](%s)" % (f, f) for f in d["files"] if f != "README.md"))
    atomic_write(os.path.join(folder, "README.md"), "\n".join(lines) + "\n")


def write_index(lib):
    """runs/README.md: the key runs first, then every run."""
    runs = lib.list()
    key = [r for r in runs if r["category"] in ("test", "partial") or r["new"]]
    out = ["# Runs", "",
           "Open the DAQ page (`python daq.py`) and use the Runs tab to plot, compare and annotate these.",
           "Each folder holds `data.csv`, `events.csv`, `notes.md` and pictures. Labels for runs 001–068 are in",
           "[catalog.json](catalog.json); the findings across runs are in [../analysis/README.md](../analysis/README.md).", "",
           "## Tests", "", "| Run | Date | What |", "|---|---|---|"]
    for r in reversed(key):
        out.append("| [%s](%s/) | %s | %s |" % (r["id"], r["id"], (r["started"] or "")[:10], r["title"] or r["category"]))
    out += ["", "## Everything else", ""]
    rest = [r for r in runs if r not in key]
    out.append(", ".join("[%s](%s/) %s" % (r["id"], r["id"], r["category"]) for r in rest))
    atomic_write(os.path.join(lib.runs_dir(), "README.md"), "\n".join(out) + "\n")
