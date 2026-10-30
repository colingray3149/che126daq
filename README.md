# che126daq

Private ChE 126 working collection: Arduino DAQ code, experimental design history, procurement, datasheets, and the shared thermal-model conversation. Imported code and source documents are preserved, not silently standardized. Original files remain in their original locations.

## Start here

- [Quick wiring diagram](WIRING-QUICK.md) — plain text, also opened in Kate.
- [Wiring and safe connection order](docs/wiring.md) — current saved pin map and hardware caveats.
- [Current experiment log](docs/experiment-log.md) — today's reported fixture and decisions, separate from older drafts.
- [Quick suggested checks](docs/quick-checks.md) — what two thermocouples can and cannot establish.
- [Executed mica-check calculations](models/mica-check/results.md) — cited inputs, conditional plots, reproducible Python.
- [100 V timing calculation](models/heater-timing/results.md) and [minimal control-identification plan](docs/heater-control-plan.md) — explicit sensitivities and a two-to-three-run workflow, not a fabricated warm-up time.
- [Setup source index](docs/setup-source-index.md) — where the useful setup material is, and which drafts conflict.
- [Activity log](docs/activity-log.md) — what was actually done and observed.
- [Run notes](docs/run-notes.md) — commands, dependencies, and imported-code limitations.

## DAQ hub

```sh
nix run path:/home/colin/Projects/che126daq
```

Open **http://127.0.0.1:8765**. The left terminal accepts `help`, `status`,
`start`, `stop`, `restart`, `save`, `clear`, `list`, `view 001`, `live`,
`note your comment`, `window 120`, `config`, and `reconnect`; ↑/↓ recalls history.
The first successful matching USB connection **automatically starts durable logging**.
Closing/refreshing the browser does not stop recording. `stop` finalizes a run;
`clear` changes only this browser's plot/console; `save` flushes without stopping.
Historical views are labeled and do not interrupt the active recording.

Each run has a short, never-overwritten directory: `runs/001/`, `runs/002/`, …
`data.csv` is flushed per row; `events.csv` records serial/reset/errors;
`notes.md` records metadata and preserves user edits below `## Comments`.
Runs are ignored by Git. No synthetic acquisition or heater controls exist.
NaNs plot as gaps; all-zero streams carry a warning, not a claim of valid sensors.

Edit **[hub.toml](hub.toml)** for USB identity/explicit port, baud, storage, retained
plot points and HTTP port. Relative storage resolves beside that file.
Nix uses `$HOME/Projects/che126daq/hub.toml` by default; set `CHE126DAQ_CONFIG`
or pass `--config /absolute/path/hub.toml` for another checkout.
See [run notes](docs/run-notes.md#daq-hub-primary-interface) for launch/service details.


## Layout

| Directory | Contents |
|---|---|
| `firmware/thermocouple_logger/` | Latest saved two-channel MAX31855 logger; 115200 baud CSV; nominal 2 Hz |
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

## Status at collection

Arduino Mega ADK detected on `/dev/ttyACM0`. User reports no thermocouples connected. Existing firmware emitted the three-column CSV header and repeated zeros; **not verified temperatures or working amplifier connections**. No firmware uploaded and no heater energized during collection.

Latest saved logger: TC1 CLK/DO/CS = **22/24/26**; TC2 = **28/30/32**. Use the wiring guide before connecting anything. Hardware model information for the amplifiers comes from the old conversation; present jumper positions and amplifier revision were not visually inspected.

The design PDF is a mixed working document, not an approved operating procedure. Battery state of charge, high-temperature fixture safety, heater geometry/power/control, sensor placement, and final experiment remain for user confirmation. ChatGPT model assumptions are not apparatus measurements.

Collection excludes unrelated resumes, portfolios, unrelated chat archives, credentials, and lab-locker-code fixture notes. No relevant DOCX or separate full-account ChatGPT export ZIP was found in Downloads; the actual recent setup source is `ChE 126 Design.pdf`. The model ZIP covers every generated sandbox file linked in the supplied share.
