"""Regenerate the figures and numbers in analysis/README.md.

    python analysis/analyze.py        (needs matplotlib: python -m pip install matplotlib)

Uses the same run loader, metrics and thermal model as the DAQ page, so every
number here matches what the Runs tab shows.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "vendor"))
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from che126 import model  # noqa: E402
from che126.runs import Library, analyze  # noqa: E402
from che126.settings import DEFAULTS  # noqa: E402

lib = Library(lambda: os.path.join(ROOT, "runs"), lambda: None)
CAT = lib.catalog()
OUT = HERE
plt.rcParams.update({"figure.dpi": 110, "font.size": 10, "axes.grid": True, "grid.alpha": 0.3})


def data(rid):
    return lib.load(rid)


def shifted(rid, key):
    d = data(rid)
    a = analyze(d, None, None, 120)
    t0 = a.get("heat_start_s") or 0
    pts = [((t - t0) / 60, v) for t, v in zip(d["t"], d[key]) if v is not None]
    return [p[0] for p in pts], [p[1] for p in pts]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("wrote", name)


LABEL = {
    "026": "026 EXP4 (85 °C rear cutoff)",
    "028": "028 EXP5 (stack not recorded)",
    "036": "036 mica / 2 fiberglass / Al",
    "040": "040 mica / 3 ceramic / Al",
    "030": "030 EXP5 repeat (rear tripped)",
    "033": "033 EXP5 repeat (rear tripped)",
}

# 1-2. The 700 C runs, aligned at the first heater-on.
fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
for rid in ("026", "028", "036", "040", "030", "033"):
    x, y = shifted(rid, "tc1")
    ax[0].plot(x, y, label=LABEL[rid], lw=1.4, ls="-" if rid not in ("030", "033") else ":")
    x, y = shifted(rid, "tc2")
    ax[1].plot(x, y, label=LABEL[rid], lw=1.4, ls="-" if rid not in ("030", "033") else ":")
ax[0].set_ylabel("TC1 heater side, °C")
ax[1].set_ylabel("TC2 barrier rear, °C")
ax[1].set_xlabel("minutes after the heater first switched on")
ax[1].axhline(120, color="k", lw=0.8, ls="--")
ax[1].text(0.2, 122, "120 °C rear cutoff", fontsize=8)
ax[0].legend(fontsize=8, loc="lower right")
ax[0].set_xlim(0, 20)
save(fig, "fig1_700C_runs.png")

# 3. Run068: the TC513 cut the heater once and never turned it back on.
d = data("068")
s = json.loads(json.dumps(DEFAULTS))
room = d["tc1"][0]


def replay(off_at):
    st = model.ThermalState(room, room, room, room)
    prev = d["t"][0]
    xs, surf, core = [], [], []
    for i, t in enumerate(d["t"]):
        dt = t - prev
        prev = t
        relay = d["heat"][i - 1] if i else 0
        on = bool(relay) and (off_at is None or t < off_at)
        model.step(st, s["model"], model.heater_power(s, on), room, dt)
        xs.append(t / 60)
        surf.append(st.surf)
        core.append(st.core)
    return xs, surf, core


def rms_after(surf, t_from):
    e = [(m - v) ** 2 for t, m, v in zip(d["t"], surf, d["tc1"]) if v is not None and t >= t_from]
    return math.sqrt(sum(e) / len(e))


best = min(range(280, 346, 2), key=lambda off: rms_after(replay(off)[1], 240))
x_on, s_on, _ = replay(None)
x_off, s_off, c_off = replay(best)
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.plot([t / 60 for t in d["t"]], d["tc1"], color="#e8590c", lw=2, label="measured TC1 (heater side)")
ax.plot(x_on, s_on, color="#868e96", ls="--", label="model, heater on whenever the DAQ relay was on")
ax.plot(x_off, s_off, color="#1c7ed6", ls="--", label="model, heater power stops at %d:%02d" % (best // 60, best % 60))
ax.plot(x_off, c_off, color="#1c7ed6", ls=":", lw=1, label="model cartridge core (same case)")
for i in range(1, len(d["t"])):
    if d["heat"][i - 1]:
        ax.axvspan(d["t"][i - 1] / 60, d["t"][i] / 60, color="orange", alpha=0.06, lw=0)
ax.set_ylim(0, 900)
ax.set_xlabel("minutes since start (shaded: DAQ relay on)")
ax.set_ylabel("°C")
ax.set_title("Run 068: after 5:02 the heater behaved as if switched off for good (fit ±%.0f °C)" % rms_after(s_off, 240))
ax.legend(fontsize=8)
save(fig, "fig2_run068_tc513.png")
print("run068 best heater-off time %d s, rms %.1f C" % (best, rms_after(s_off, 240)))

# 4. Stored heat: full power until 100 C, then off (run068 start) vs model.
st = model.ThermalState(room, room, room, room)
xs, ms, mc = [], [], []
t = 0.0
while t < 240:
    on = 0.4 <= t < 36.4
    model.step(st, s["model"], model.heater_power(s, on), room, 0.5)
    t += 0.5
    xs.append(t)
    ms.append(st.surf)
    mc.append(st.core)
fig, ax = plt.subplots(figsize=(9, 4))
mask = [i for i, tt in enumerate(d["t"]) if tt <= 240]
ax.plot([d["t"][i] for i in mask], [d["tc1"][i] for i in mask], color="#e8590c", lw=2, label="measured TC1, run 068")
ax.plot(xs, ms, color="#1c7ed6", ls="--", label="model TC1")
ax.plot(xs, mc, color="#1c7ed6", ls=":", label="model cartridge core")
ax.axvspan(0.4, 36.4, color="orange", alpha=0.12, label="heater on")
ax.axhline(100, color="k", lw=0.7, ls="--")
ax.set_xlabel("seconds")
ax.set_ylabel("°C")
ax.set_title("Heat stored in the cartridge: switching off at 100 °C still coasts to 187 °C")
ax.legend(fontsize=8)
save(fig, "fig3_stored_heat.png")

# 5. Rear rise vs energy in, for the runs that reached 700 C.
fig, ax = plt.subplots(figsize=(6.5, 4.5))
rows = []
for rid in ("026", "028", "036", "040", "030", "033", "068"):
    cat = CAT.get(rid, {})
    a = analyze(data(rid), cat.get("voltage"), cat.get("heater_W"), 120)
    e, rise = a.get("energy_kJ"), a.get("tc2_rise")
    rows.append((rid, a))
    if rid == "068":
        continue
    ax.scatter(e, rise, s=40)
    ax.annotate(rid, (e, rise), textcoords="offset points", xytext=(5, 3), fontsize=9)
ax.set_xlabel("energy in while the relay was on, kJ (upper bound)")
ax.set_ylabel("TC2 rise, °C")
ax.set_title("Rear rise grows with heat input")
save(fig, "fig4_rise_vs_energy.png")

# 6. Model predictions: the 700 C program at different variac voltages.
from che126 import program as prog  # noqa: E402

p = prog.normalize(json.load(open(os.path.join(ROOT, "programs", "700 C, 60 s hold (EXP5-6 style).json"))))
fig, ax = plt.subplots(figsize=(9, 4.4))
for v in (70, 85, 100, 115):
    sv = json.loads(json.dumps(DEFAULTS))
    sv["variac_V"] = v
    pv = prog.preview(p, sv, None, next_after_s=30)
    ax.plot([t / 60 for t in pv["t"]], pv["tc1"], label="%d V: TC1 peak %d °C, core %d °C%s" % (v, pv["peak_tc1"], pv["peak_core"], ", trips 730" if any("cutoff" in w for w in pv["warnings"]) else ""))
ax.axhline(730, color="k", lw=0.7, ls="--")
ax.set_xlabel("minutes")
ax.set_ylabel("predicted TC1, °C")
ax.set_title("Predicted 700 °C / 60 s program with the 500 W cartridge")
ax.legend(fontsize=8)
save(fig, "fig5_voltage_preview.png")

with open(os.path.join(OUT, "metrics.json"), "w") as f:
    json.dump({rid: a for rid, a in rows}, f, indent=1)
print("wrote metrics.json")
