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
