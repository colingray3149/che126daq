# che126daq

Private ChE 126 working collection: Arduino DAQ code, experimental design history, procurement, datasheets, and the shared thermal-model conversation. Imported code and source documents are preserved, not silently standardized. Original files remain in their original locations.

## Start here

- [Quick wiring diagram](WIRING-QUICK.md) — plain text, also opened in Kate.
- [Wiring and safe connection order](docs/wiring.md) — current saved pin map and hardware caveats.
- [Setup source index](docs/setup-source-index.md) — where the useful setup material is, and which drafts conflict.
- [Activity log](docs/activity-log.md) — what was actually done and observed.
- [Run notes](docs/run-notes.md) — commands, dependencies, and imported-code limitations.

## Layout

| Directory | Contents |
|---|---|
| `firmware/thermocouple_logger/` | Latest saved two-channel MAX31855 logger; 115200 baud CSV; nominal 2 Hz |
| `firmware/tc_fault/` | Fault/cold-junction diagnostic using the same pin map |
| `firmware/tc_diag/` | Older shared-clock raw-frame diagnostic; DIFFERENT wiring |
| `host/plot.py` | Original live two-channel plot; rolling 20 seconds; does not save a recording |
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
