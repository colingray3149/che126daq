# Activity log

## 2026-10-30 — Initial consolidation

### Request and scope

Collected existing ChE 126 DAQ/Arduino code, experimental setup/planning sources, order form, downloaded material/heater documentation, thermal model files and the supplied shared ChatGPT conversation. User will specify the experiment and refinement goals later. This collection does not adopt a draft procedure or standardize code behavior.

### Work completed

- Located `blossoming-panda`'s old Claude pane titled “Arduino Mega ADK thermocouple logger”; used its saved session `c01abf05-72d5-4b9f-99b7-0a3729022dfd` without typing into or altering that session.
- Copied current sketchbook firmware and plotter, recoverable Write/Edit historical snapshots, relevant code-changing tool calls, and historical board-flash backups. Historical snapshots explicitly exclude automatic reconstruction of Bash edits.
- Copied original design PDF, materials-order XLSX, downloaded mica/basalt/heater PDFs, MAX31855 datasheet, recovered Tempco heater instructions, OEM board docs/schematic/photo, course background, older DAQ concept note and Arduino installation module.
- Extracted page-marked PDF text and separate spreadsheet formula/cached-value CSV views. Preserved all originals in place; no unrelated personal archives or credentials imported.
- Preserved thermal-model ZIP and safely extracted all ten members. Captured the complete public shared-chat answer from embedded HTML data; saved HTML/JSON/Markdown/source links. All eight sandbox-linked generated artifacts resolve to local files, including the ZIP itself. Both uploaded material PDFs are available locally with matching names/sizes.
- Wrote a setup source index separating dated sections, undated drafts, purchasing evidence, actual code/hardware observations, and unresolved conflicts.
- Wrote source-backed current wiring/power-order guidance. At the user's request, wrote `WIRING-QUICK.md` with a plain-text header diagram and opened it in a dedicated Kate instance; user acknowledged it.
- Created GitHub repository `colingray3149/che126daq` with `gh repo create --private` for the initial import.

### Observed hardware

`arduino-cli board list --format json` identified Arduino Mega ADK at `/dev/ttyACM0`, FQBN `arduino:avr:megaADK`, VID:PID `2341:0044`. User reported no thermocouples connected. Approximately five seconds of existing serial output at 115200 baud showed the expected `time_s,t1_C,t2_C` header and repeated `0.00,0.00`; startup contained a few undecodable bytes. Raw capture and USB identity are in `provenance/hardware/`.

These zeros are not accepted temperature measurements, proof of a working interface, or proof of a failed amplifier. No firmware was uploaded, no wires were moved by the assistant, and no heater was energized. Opening/configuring the port may have reset the board. Loaded firmware binary was not read back or compared with saved code.

### Verification actually exercised

- All three copied sketches compiled successfully using `arduino-cli compile --fqbn arduino:avr:megaADK`: `thermocouple_logger`, `tc_fault`, `tc_diag`. Diagnostics' different wiring/output contracts remain documented.
- Executed the imported thermal model with its default parameters and `--out /tmp/che126daq-model-smoke`. It completed and produced five PNG figures, a predictions CSV and a blank measurements template. This proves execution, not physical correctness. Output reported ideal resistance increase 0.023226%; hypothetical bare case reached 100°C at 5.86 minutes, aluminum case did not reach it within 30 minutes under those assumptions.
- Verified SHA-256 of every byte-preserving import against its recorded source hash and confirmed all exported JSON parsed. All linked generated chat artifacts were present locally.
- `gitleaks dir` with archive traversal scanned the collected inputs and reported no leaks before publication preparation. This is not a guarantee that arbitrary scientific documents contain no sensitive information.

Python smoke/extraction environment: Nix-provisioned Python 3.14.8 with numpy, scipy, matplotlib, pyserial, tkinter and openpyxl. Installed Arduino versions are captured in `references/environment/installed-arduino-tools.txt`.

### Open facts for the next working session

- Intended experiment, fixture, material stack, heater/control/power measurement and safety review remain for user clarification.
- Present amplifier silkscreen/revision, actual jumper positions, probe identity and interface fault behavior are not physically verified.
- Plotter is visualization only, has stale A1/A2 legend labels, and is not a durable data recorder. No experimental time-series dataset was located among the collected sources.
- The recent setup source found is PDF, not DOCX. The recent ZIP is model artifacts, not a full-account ChatGPT export. No separate relevant DOCX/full export was found in Downloads.
- No claim that design-document “final” headings, charged-cell placeholders, high-temperature recipes, regulatory statements or AI model predictions are validated or approved.

## 2026-10-30 — Interactive durable DAQ hub

### Implementation

- Added `host/hub.py`, `host/web/`, `hub.toml`, pinned `flake.nix`/`flake.lock`;
  aiohttp + pyserial + locally served Plotly, IPv4 localhost only. No shell
  execution, heater control, firmware upload or pin changes. Original plotter
  remains unchanged and is explicitly superseded.
- First matching serial connection automatically records. Atomic numeric run
  directories contain per-row-flushed CSV, event CSV and Markdown metadata;
  user-owned Comments content survives save/finalization. Browser view/history
  state never owns acquisition. Runs are ignored by Git.
- Documented commands, configuration, fault/reset/time semantics, bounded plots,
  shutdown, and the absence of fsync/power-loss guarantees.

### Real observations and checks

- Started with `nix run path:/home/colin/Projects/che126daq` under a user systemd
  service. Matched the configured Mega ADK USB identity and opened `/dev/ttyACM0`
  at 115200. User reported amplifiers newly connected; probe attachment was not
  assumed. Current firmware emitted **nan on TC1 and TC2**, not verified
  temperatures. Saved CSV contains literal `nan` plus channel fault flags;
  rendered plots show gaps and explicit fault text.
- Typed help, status, start, note, save, config, channels, window, a deliberately
  unknown command, stop, restart, list, view, clear and live into the actual
  browser terminal. Reconnect also reopened the real board, kept run 005 active,
  and visibly reported possible board reset. No two serial readers were run.
- Commissioning created real `runs/001` through `runs/005`, kept locally and
  excluded from commits. Run 001 finalized with 171 rows and its commissioning
  comment intact. Short command/deployment gaps are commissioning interruptions,
  not an uninterrupted experimental record.
- While the graph stayed HISTORICAL run 001, active run 003 advanced from 60 to
  61 rows. Browser refresh kept run 003 recording and advanced from 62 to 65
  rows. Up recalled `live`; Down restored the empty command draft.
- Final deployed startup visibly recorded malformed partial row `,nan,nan` and
  board-time regressions, including buffered 116.0 → 112.5 and startup → 0.5;
  events and reset epochs preserved these observations. Their hardware cause
  was not diagnosed. Reopening serial may reset the board.
- Visually inspected actual browser screenshots at **1366×768 and 1280×720**
  (reported browser device scale 1.25). Left terminal/right graph, axes, TC1/TC2
  legend and fault/recording status fit without page overflow. Rendered saved
  real run 001 with a clear historical label.
- Since real readings were all NaN, a **separate, explicitly labeled synthetic
  `/tmp` saved fixture on port 8766** exercised two colored/solid-dashed curves
  and a visible TC1 NaN gap. Clicked Plotly zoom-in, pan selection and reset
  controls. This was visual evidence only, never real acquisition.
- Throwaway isolated PTY/server smoke passed headers, partial rows, malformed
  ASCII/numerics, NaNs, preserved actual zeros/all-zero warning, board regression,
  command errors, save/stop/restart, comments manually edited outside the app,
  active recording during history, clean shutdown metadata, directories 001→002
  →003 across process restarts, simulated disconnect and failed reconnect.
  A focused close smoke also proved oversized partial reporting, draining two
  complete pending rows on close, and visible incomplete-row discard on close/
  simulated disconnect. No permanent tests were added. Scripts and synthetic
  datasets were removed after proof.
- Final `nix run path:/home/colin/Projects/che126daq --option substituters
  https://cache.nixos.org --option builders '' -- --help` worked from `/tmp`.
  The workstation's configured `10.77.0.11:5000` cache was unavailable and
  delayed one deployment; local build with the public cache avoided that delay.
  The final app packages `host/` rather than referencing the entire collection.

### Left running

`che126daq-hub.service` is a supervised transient **user** systemd service,
running the built executable
`/nix/store/h0m8xq8i91jqsapfxwyhkx0hx6m6r29b-che126daq/bin/che126daq`.
It is GC-rooted at ignored `build/hub`; storage is the repository's `runs/`.
The page is open in a dedicated Helium window at http://127.0.0.1:8765.
Stop with `systemctl --user stop che126daq-hub`. No boot/login autostart or
logout-linger configuration was installed. Both channels remain faults;
probe identity/attachment, amplifier wiring and valid temperatures remain
unverified. No heater was energized or controlled by this work.

## 2026-10-30 — User setup rundown and mica-check calculations

- Recorded the user's current apparatus and decision status in
  `docs/experiment-log.md`: variac assumption, cinderblock/semi-wet sand,
  cut 2 × 6 inch specimens, top clamps/bottom clip, candidate layer orders,
  unavailable aerogel, current wire-held two-probe mica-only check, and later
  packed comparative trials. No heating result or adopted safety recommendation
  was invented from the description.
- Added `docs/quick-checks.md`: reference/co-location, channel/fault checks,
  untouched versus reseated repeats, probe/channel swaps, spatial sensitivity,
  air → dry-packed → air comparison, and later aluminum/layer comparisons.
  Each suggestion states its observable and its interpretation limit.
- Retrieved and archived manufacturer aerogel PDS/SDS, sand PDS/SDS, Samsung
  cell SDS and readable product-page captures in `references/current-check/`, with
  source URLs/retrieval times/SHA-256. Indexed existing heater/mica/basalt/chip
  PDFs and new references in `docs/current-check-sources.md`.
- Checked the actual heater's rated versus heated dimensions, catalog
  conductivity reference conditions, aerogel short-time-flame qualification,
  and possible Adafruit #3245 electrically connected probe-tip limitation.
- Implemented and executed `models/mica-check/calculate.py` using cited
  `inputs.json`. It generated electrical-power CSV, geometry/sensitivity CSVs,
  Markdown/JSON results, run log and three rendered figures. It does not
  forecast a safe variac setting or an absolute apparatus temperature/time
  without missing contact, heat-flow, storage and boundary-condition inputs.
- Inspected all rendered plots. An overlapping area-plot footnote was moved
  into the subtitle before final regeneration. Scientific computations used
  the already-provisioned Nix Python environment with numpy/matplotlib;
  the report includes a portable NixOS reproduction command.
- Parent independently inspected the hub's real UI screenshot, localhost API
  and saved `runs/005/data.csv`/`notes.md` after the builder completed.
  Acquisition was active; both channel values were still fault/NaN. No second
  serial reader, firmware upload or heater command was used. The raw saved
  commissioning data are not a successful temperature-validation experiment.
- Pre-publication scanning flagged website-issued tokens in raw vendor HTML.
  Replaced those pages with readable text captures without scripts/styles/HTML
  attributes rather than publishing irrelevant tokens. Original source PDFs
  remain byte-preserved; both downloaded HTML and published text hashes are
  recorded in the source index. Raw HTML was kept outside the repository.

## 2026-10-30 — 100 V / 500°C question and control-identification plan

- User requested time to 500°C at 100 V and the quickest useful two-to-three
  runs for estimating a later constant-temperature control recipe.
- Executed `models/heater-timing/calculate.py` with cited heater rating and
  energy-balance/first-order references. Recorded nominal power/current,
  no-loss capacity dependence, linear-loss reachability and explicitly
  hypothetical capacity/loss scenarios. The script leaves actual apparatus
  time unknown: no measured thermal capacity, loss model or valid heated
  identification trace has been supplied.
- Saved input/code hashes, result JSON/Markdown, sensitivity CSV, trace CSV,
  execution log and an inspected rendered figure. Scenario parameters are
  labeled arbitrary, not measured or likely bounds.
- Wrote `docs/heater-control-plan.md`: a step/coast run, near-operating-band
  up/down steps and an independent planned 30-minute hold; or combine the two
  identification sections and use the second run for validation. No such
  physical runs have been performed by the assistant.
- Distinguished a manual boost/hold recipe from later feedforward plus PI
  with a real controllable actuator. No numeric gains, boost duration,
  hold voltage, safe voltage ceiling or software variac interface invented.
- Retained the probe upper-limit/grounding, current installation and fault
  prerequisites; did not energize a heater, alter firmware, open another
  serial reader or change the running DAQ service.
