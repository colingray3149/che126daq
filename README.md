# CHE 126 thermal-barrier DAQ

Runs the heater experiments: reads the thermocouples, switches the heater relay, runs
step programs (heat to, ramp, hold, off), records every run, and shows past runs.

## Start it

1. **Python 3.8 or newer.** Windows: install from python.org and tick *Add python.exe to PATH*.
   Mac: install from python.org. Nothing else to install; everything else is in this folder.
2. **Get the folder:** on GitHub, *Code → Download ZIP*, unzip it (or `git clone`).
3. **Run `daq.py`:** open the folder in VS Code (or Zed), open `daq.py`, press **Run**.
   In a terminal: `python daq.py` (Windows) or `python3 daq.py` (Mac).
4. The page opens at **http://127.0.0.1:8765**. Keep the terminal open: closing it stops
   the DAQ and turns the heater off.

**Practice first:** `python daq.py --sim` (VS Code: Run and Debug → *Practice (simulated rig)*)
runs everything against a simulated rig that heats like the real one. The header says
*PRACTICE* in yellow, and practice runs are saved in `practice-runs/` (p001, p002…), not `runs/`.

## Before heating

* USB plugged in, page header shows the board's port in green.
* Thermocouple readings look right (room temperature, no "no reading").
* **Variac voltage** typed in the New run box (it sets the power the controller expects).
* Setup box filled in: barrier layers in order, sand, anything you changed.
* The relay is wired COM–NC: **the heater is powered whenever the Arduino is unpowered or
  resetting.** Turn the variac on only after the page shows the board connected; turn it off
  before unplugging USB or closing the laptop.

## Running an experiment

**Program tab:** build the steps (Full power until, Ramp, Hold, Off), cutoffs and finish
conditions. The *Predicted run* beside it simulates the program before you heat: expected
TC1/TC2 curves, heater on/off, overshoot, cutoff trips. Save, then *Use on Live*.

**Live tab:** pick the program, type the variac voltage and setup, **Start run**.
**NEXT** jumps to the next step at any time (also the N key). **Stop heat** turns the heater
off and keeps recording the cool-down. **End run** closes the recording. *Manual* heats or
holds a temperature without a program; it always records, and its cutoffs are the two boxes
under it. Grey dashes on the charts are the predicted run;
shaded bands are heater on.

**Runs tab:** every run with its plots, numbers (hover a label for how it is calculated), notes
and files. Tick runs and press *Compare* to overlay them. **Findings** has the analysis of runs
001–068 and what to test next, the history of the rig, and the hardware notes.

## Where things are

| | |
|---|---|
| `runs/NNN/` | one folder per run: `data.csv`, `events.csv`, `notes.md` (your comments), `run.json`, `plot.png` |
| `programs/` | saved programs (JSON, editable in the Program tab) |
| `analysis/` | findings across runs, figures, `analyze.py` |
| `docs/hardware.md` | wiring, the TC513, safety; `docs/datasheets/` |
| `docs/history.md` | what was built, run and changed, day by day |
| `settings.json` | your settings (created when you save the Settings tab) |
| `firmware/` | Arduino firmware; upload it from Settings → Board → *Upload firmware* |
| `che126/`, `web/` | the program itself; `AGENTS.md` explains it for an AI assistant |
| `archive/` | the earlier EXP2–EXP8 software and notes, kept for reference |

## If something goes wrong

| You see | Do |
|---|---|
| *No board* | Plug in USB; pick the port in Settings → Board; press Reconnect. |
| *Old firmware on board* or *Board not answering* | Settings → Board → Upload firmware (about 10 s). |
| *Cutoff: TC2 reached its limit* | The board turned the heater off. Fix the cause, then *Clear cutoff*. |
| *Lost contact with daq.py* | The terminal was closed or crashed. Run `daq.py` again; the page reconnects. |
| A TC shows "no reading" / "open TC" | Thermocouple unplugged or broken; check its amplifier wiring. |
| Wrong TC on top | Settings → Thermocouples: set which amplifier each TC is wired to. |
| Port 8765 busy | `python daq.py --http-port 8766`. |

Tests: `python -m unittest discover tests`.
