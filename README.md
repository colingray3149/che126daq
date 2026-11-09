# che126daq

Private ChE 126 working collection: Arduino DAQ code, experimental design history, procurement, datasheets, and the shared thermal-model conversation. Imported code and source documents are preserved, not silently standardized. Original files remain in their original locations.

## Start here

- [Quick wiring diagram](WIRING-QUICK.md) — plain text, also opened in Kate.
- [Wiring and safe connection order](docs/wiring.md) — current saved pin map and hardware caveats.
- [Editable experiment settings](experiment.toml) — target, cutoffs, hysteresis and timing; save, then `start exp2` reloads them without a server restart or another firmware upload.
- [Experiment 2 operation](docs/exp2.md) — explicit START/re-arm, optional TC2, editable runtime settings, 30V preset and the requested NC relay's fail-ON limitation.
- [Experiment 3 settings](experiment3.toml) — reversed-probe control mapping and 65V manual preset; `start exp3` uses the deployed v5 single-target program.
- [Experiment 4 staged program](docs/exp2.md#exp4-staged-100-v-program) — `experiment4.toml`, 100°C hold → explicit `next` → 90s ramp to 200°C → boost/700°C hold; deployed v5.
- [Current experiment log](docs/experiment-log.md) — today's reported fixture and decisions, separate from older drafts.
- [All experimental runs, 001–026](runs/README.md) — top-level archive with each run's raw data, event log, notes and available settings/reports; 33,538 sample rows.
- [Completed EXP4/run026 archive](runs/026/notes.md) — operator reported it went fine; raw data, events, settings, measured closeout and assistant refusals. [Full interactive report](runs/026/report.html): download/open locally or open it from a clone.
- [Quick suggested checks](docs/quick-checks.md) — what two thermocouples can and cannot establish.
- [Executed mica-check calculations](models/mica-check/results.md) — cited inputs, conditional plots, reproducible Python.
- [100 V timing calculation](models/heater-timing/results.md) and [minimal control-identification plan](docs/heater-control-plan.md) — explicit sensitivities and a two-to-three-run workflow, not a fabricated warm-up time.
- [Measured run 006 + relay/sand research](docs/relay-sand-control.md) — earlier 500°C/30-minute draft criterion, actual trace/faults, wet-sand sensitivities and runnable calculations; superseded for operating targets by experiment 2.
- [Setup source index](docs/setup-source-index.md) — where the useful setup material is, and which drafts conflict.
- [Activity log](docs/activity-log.md) — what was actually done and observed.
- [Run notes](docs/run-notes.md) — commands, dependencies, and imported-code limitations.
- [Full-run interactive reports](docs/run-notes.md#full-run-interactive-reports) — `python host/report.py runs/023`; offline graphs with every saved sample, complete axes, linked zoom and PNG/SVG exports, without interrupting the DAQ.

## DAQ hub

```sh
nix run path:/home/colin/Projects/che126daq
```

Open **http://127.0.0.1:8765**. The left terminal accepts `help`, `status`,
`start`, `start exp2` / `exp3` / `exp4`, `stop exp2` / `exp3` / `exp4`,
`next`, `stop`, `restart`, `save`, `clear`, `list`, `view 001`, `live`,
`note your comment`, `window 120`, `config`, and `reconnect`;
↑/↓ recalls history. The first matching USB connection **starts logging, never heating**.
`start exp2` creates a fresh saved run and explicitly re-arms without sensor,
temperature, IDLE-state or physical-reset preflight requirements. TC2 is optional
for EXP2/3 and required for EXP4; runtime cutoffs come from the selected file.
`stop exp2` cuts commanded heat but keeps cooldown logging; another START needs no board reset.
Plain `stop` must stop heat before finalizing a run.
`clear` changes only this browser's plot/console; `save` flushes without stopping.
Historical views are labeled and do not interrupt the active recording.

Each run has a short, never-overwritten directory: `runs/001/`, `runs/002/`, …
`data.csv` is flushed per row; `events.csv` records serial/reset/errors;
`notes.md` records metadata and preserves user edits below `## Comments`.
All run folders are version-controlled directly under **[runs/](runs/README.md)**,
including raw data, event logs, notes and every available settings/report file.
The DAQ never automatically commits, pushes or deletes recordings.
No synthetic acquisition mode exists. EXP2 control is explicit;
NC contact wiring cannot fail OFF on loss of Arduino power. See the operating guide.
NaNs plot as gaps; all-zero streams carry a warning, not a claim of valid sensors.

Edit **[hub.toml](hub.toml)** for USB identity/explicit port, baud, storage, retained
plot points and HTTP port. Relative storage resolves beside that file.
Edit **[experiment.toml](experiment.toml)** for heater control. Each `start exp2`
reloads it and sends all settings atomically; editing alone leaves an active
run unchanged. `config` shows edited versus board-applied values. Each run saves
the exact config source and acknowledged settings for reproducibility.
EXP3 selects **[experiment3.toml](experiment3.toml)** with `start exp3`;
`swap_inputs` changes board control roles, while `variac_voltage_V` is recorded
manual-preset metadata, not a power command or temperature scaling factor.
Plots have independent heater/rear temperature axes and show raw source channels.
Run 017's reported reversal is annotated without modifying its raw CSV.
EXP4 selects **[experiment4.toml](experiment4.toml)** with the deployed
v5 host/firmware pair. `next` advances only an in-band 100°C hold; it never
allocates a new recording. EXP4/run026 completed with an operator-reported
successful outcome; its measured record and retained rear-cutoff trip are archived.
The v5 DAQ was launched with `--wait-for-start`; old v4 DAQ/report services
were closed after saving run023. A completed thermal run does not independently
establish calibration or component limits.
Nix uses `$HOME/Projects/che126daq/hub.toml` by default; set `CHE126DAQ_CONFIG`
or pass `--config /absolute/path/hub.toml` for another checkout.
See [run notes](docs/run-notes.md#daq-hub-primary-interface) for launch/service details.
Launch with `--wait-for-start` to connect and display sensor status without
automatically allocating a run. An explicit `start exp3` then allocates the next
numbered folder and applies its settings; no heat starts on connection.


## Layout

| Directory | Contents |
|---|---|
| `firmware/thermocouple_logger/` | Two-channel MAX31855 logger + board-local EXP2 controller; 115200 baud CSV/control telemetry; nominal 2 Hz |
| `firmware/tc_fault/` | Fault/cold-junction diagnostic using the same pin map |
| `firmware/tc_diag/` | Older shared-clock raw-frame diagnostic; DIFFERENT wiring |
| `host/hub.py`, `host/web/`, `hub.toml` | Primary command-first durable DAQ hub; local aiohttp/pyserial/Plotly |
| `host/plot.py` | Superseded original plotter, retained unchanged for provenance; no saving, stale A1/A2 labels |
| `models/thermal-stack/` | Extracted ChatGPT model, five figures, predictions, blank measurement template, original model notes |
| `references/` | Original design PDF, order XLSX, datasheets, course notes, export ZIP; searchable PDF text and spreadsheet CSV views |
| `provenance/claude/` | Readable old session, relevant code-changing calls, historical source snapshots, prior flash backups |
| `provenance/chatgpt/` | Full shared answer, public HTML, structured messages, source URLs, attachment index |
| `provenance/hardware/` | USB identity and raw serial observation |
| `provenance/source-manifest.json` | Original source paths, destinations, SHA-256 hashes; historical reconstructions have a separate index |
| `docs/` | Current collection notes, uncertainties, wiring, verification/activity history |
| `runs/` | Numbered original recordings 001–026; browsable index, raw CSVs, event logs, per-run notes and available settings/reports |

## Status at collection

Arduino Mega ADK detected on `/dev/ttyACM0`. User reports no thermocouples connected. Existing firmware emitted the three-column CSV header and repeated zeros; **not verified temperatures or working amplifier connections**. No firmware uploaded and no heater energized during collection.

Latest saved logger: TC1 CLK/DO/CS = **22/24/26**; TC2 = **28/30/32**. Use the wiring guide before connecting anything. Hardware model information for the amplifiers comes from the old conversation; present jumper positions and amplifier revision were not visually inspected.

The design PDF is a mixed working document, not an approved operating procedure. Battery state of charge, high-temperature fixture safety, heater geometry/power/control, sensor placement, and final experiment remain for user confirmation. ChatGPT model assumptions are not apparatus measurements.

Collection excludes unrelated resumes, portfolios, unrelated chat archives, credentials, and lab-locker-code fixture notes. No relevant DOCX or separate full-account ChatGPT export ZIP was found in Downloads; the actual recent setup source is `ChE 126 Design.pdf`. The model ZIP covers every generated sandbox file linked in the supplied share.
