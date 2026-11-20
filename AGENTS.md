# For an AI assistant working on this repo

The users are students running a lab rig from `daq.py` in a browser. They have no CLI tools;
keep the page self-explanatory and the text short.

## Layout

| File | What it does |
|---|---|
| `daq.py` | entry point: argument parsing, starts the app, server and browser |
| `che126/app.py` | `App`: board callbacks, 10 Hz control loop, runs, manual mode, settings changes |
| `che126/program.py` | program format and validation, `Runner` (step logic, NEXT), `preview()` |
| `che126/model.py` | thermal model, `Observer`, `Controller` (predictive / on-off) |
| `che126/board.py` | serial link with reconnect; `SimBoard` (practice rig); protocol summary |
| `che126/runs.py` | recording, reading old and new run folders, metrics (`METRIC_HELP`), barrier fit, run READMEs |
| `che126/server.py` | HTTP API (list at the top of the file) and server-sent events |
| `che126/settings.py` | defaults (`DEFAULTS`) and validation; user values in `settings.json` |
| `che126/stk500.py` | firmware upload through the Mega bootloader |
| `web/index.html`, `web/app.js`, `web/style.css` | the page (no build step; uPlot charts in `web/vendor/`) |
| `firmware/che126_daq/` | Arduino firmware and compiled `.hex` |
| `programs/*.json` | saved programs (format in `che126/program.py`) |
| `runs/catalog.json` | labels, mapping and reviews for runs 001–068 |
| `analysis/` | findings (`README.md`) and `analyze.py` |

## Common changes

* **New step type or program option:** `program.py` (`normalize`, `describe`, `Runner.tick`),
  then the editor in `web/app.js` (`ACTIONS`, `renderEditor`, `stepText`). `preview()` follows
  automatically because it runs the same `Runner`.
* **New setting:** add it to `DEFAULTS` (and `validate`) in `settings.py`, then a field in
  `renderSettings()` in `web/app.js`.
* **Refit the model** after new runs: fit functions in `analysis/analyze.py` and
  `runs.fit_barrier`; update `DEFAULT_MODEL` in `model.py` and say which runs it came from.
* **Firmware change:** edit the `.ino`, compile with arduino-cli
  (`arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 --output-dir build firmware/che126_daq`),
  copy `build/che126_daq.ino.hex` to `firmware/che126_daq/che126_daq.hex`, bump
  `FIRMWARE_VERSION` in both the `.ino` and `board.py`.
* **Labels for old runs:** edit `runs/catalog.json`; READMEs regenerate on the next run end, or
  call `che126.runs.write_run_readme` / `write_index`.

## Rules

* NEXT, Stop and manual control must always work: no state checks that block the operator.
  Safety lives in the cutoffs the operator sets (enforced on the board) and the lease.
* Never change a run's `data.csv`/`events.csv` after it is recorded.
* Python 3.8+, standard library plus vendored pyserial only. Must run on Windows and macOS.
* Test: `python -m unittest discover tests` (and `tests/test_firmware_sim.py` with the simulator
  from `tests/board_sim/build.sh` on Linux). Check the page in a real browser after UI changes.
