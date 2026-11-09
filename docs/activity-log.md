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

## 2026-11-02 — Experiment 2 implementation and verification

- User selected measured 30V variac output, 300°C TC1 heater control and a latched TC2 ≥140°C shutdown; clarified TC1 is heater-side and TC2 is opposite the barrier. User reported the Mega plugged in with thermocouples and relay disconnected.
- Warned that requested COM–NC wiring fails ON when the Arduino/coil loses power or resets. Implemented that explicitly requested NC/active-HIGH profile on D33, without claiming fail-safe physical isolation. No AC power or actual relay was operated.
- Added `exp2_controller.h` and serial command/telemetry handling to the existing sketch; preserved TC pins and three-column temperature CSV. Added strict matching acknowledgement IDs, heartbeat/freshness behavior, terminal-latch refusal, fresh durable experiment runs and controller status to the hub/UI. Documented provisional tuning and 30-minute hold semantics in `docs/exp2.md`.
- Compiled Mega ADK image (13,448 bytes flash, 1,072 bytes static RAM) and uploaded it to the identified board. A short exclusive serial observation showed real `exp2-v1` IDLE/commanded OFF and NaN sensor faults. Closed that reader before opening the hub.
- Native portability checking caught a namespace collision with libc `exp2()`; renamed the C++ namespace to `che126_exp2` and passed final native/AVR builds. Controller regression cases, including exact 140°C boundary, terminal latch and a synthetic-clock 30-minute hold, passed.
- Reproduced and fixed stale/unresolved-host keepalives continuing after output uncertainty; heartbeat now stops without fresh control/temperature receive data. Reproduced and fixed malformed JSON state causing a TypeError and reset headers failing to separate saved acquisition epochs; Python regressions passed.
- Exercised actual native-compiled sketch + actual hub through an isolated PTY with synthetic thermocouple inputs. START, below-limit reading, exact trip, cooling/restart refusal, active manual STOP with cooldown logging and plain-stop finalization passed. Actual browser CLI at 1366×768 showed the same behavior. Throwaway adapters, scripts and synthetic runs were kept outside the repository and removed after proof.
- Opened the real-board client at http://127.0.0.1:8765; `start exp2` was rejected because both probes were missing, leaving IDLE/SENSOR_FAULT/commanded OFF. Physical baseline runs 007 and 008 are actual missing-probe acquisition, not heated experiments. Partial serial fragments on opening were reported as malformed rows; no samples were invented.
- Left assistant-managed persistent service `che126daq-exp2-live` serving the final source and reading the board. No competing physical serial reader remains. The browser verifier and isolated synthetic server were stopped. No 300°C physical regulation, thermocouple calibration, relay polarity, contact position, electrical-installation safety or sand-packed hold was validated.

## 2026-11-02 — User-requested unconditional START / single TC

- User explicitly requested removal of all START requirements and the physical-reset restriction for heat-gun/single-TC control testing. Removed host/firmware START preflight gates, sample streak and terminal-state re-arm lock. Every explicit START now starts a fresh run and resets the hold/control session, including after stop/trip/completion or while already running.
- TC2 is optional; its invalid/missing reading no longer blocks or trips a TC1-only test. Finite TC2 ≥140°C still trips, and TC1/runtime freshness/heartbeat/high-limit shutdowns remain separate from START acceptance. Cooling does not automatically restart output. UI states when TC2 protection is unavailable.
- User confirmed **variac physically unplugged** before upload. Compiled/uploaded `exp2-v2` (13,384 bytes flash, 1,047 bytes RAM), preserved earlier data, restarted the client and left persistent service `che126daq-exp2-v2-live` running.
- Native regressions passed for new manual re-arming and single-TC behavior plus retained runtime limits. Python acquisition regressions passed. Observed real board/client RUNNING with finite TC1 and TC2 NaN in user-started run 011, and visually checked the updated warning/status. Did not issue START/STOP against or interrupt that active user test. No powered cartridge hold validation claimed.

## 2026-11-02 — Editable control configuration in Zed

- User requested editable targets/cutoffs/on-off settings between experiments and the entire repository open in Zed. Created `experiment.toml` once, ran `zeditor /home/colin/Projects/che126daq /home/colin/Projects/che126daq/experiment.toml`, and preserved that file thereafter while implementing the loader.
- Added per-START TOML reload, nine-key canonical settings, bounded atomic firmware START payload, v3 telemetry and exact applied-settings confirmation. Runs save source bytes and requested/applied settings. Config integrity errors are reported before closing an active run or writing a controller command; prior sensor/reset preflight gates remain removed.
- Updated UI to show board-applied target/ON threshold/cutoffs/OFF dwell and configured hold duration, distinguishing disabled or missing TC2 protection. `config` shows edited and applied values without changing an active experiment.
- Passed four Python acquisition/config safety regressions. Added and exercised native configurable-controller cases. Corrected a regression's prediction arithmetic to use its actual trailing 5s history (96°C with 1.2°C/s projects to 102°C), rather than an assumed half-second derivative. Final native and AVR checks passed.
- Actual-sketch/actual-hub PTY smoke demonstrated target 60→100°C reload only on the next START, separate run snapshots without reset, configurable 42°C TC2 and 120°C TC1 trips, disabled TC2 behavior, and invalid-NaN-config atomicity. Synthetic probes/configs/runs stayed under `/tmp` and were removed after proof.
- Real board was STOPPED/commanded OFF before deployment; preserved/finalized run 011, uploaded the v3 image (14,910 bytes flash/988 bytes static RAM) with the variac left unplugged as previously confirmed, and started real baseline run 012. No active experiment was interrupted or new heater experiment armed.
- Verified real `exp2-v3` IDLE/commanded OFF telemetry and `config` output in the actual browser UI at 1366×768. Left assistant-managed persistent service `che126daq-config-live` on http://127.0.0.1:8765; temporary browser/native smoke services were stopped. No powered cartridge hold, contact/polarity measurement or electrical-installation validation claimed.

## 2026-11-06 — Split live plots and prepare EXP3 without deployment

- User identified reversed probes in active run 017, requested split plots and a 65V EXP3 profile, and explicitly chose preparation now with deployment only after recording finishes.
- Appended correction through live `note`: raw TC1 is rear, raw TC2 heater; the existing TC2_LIMIT acted on the heater. Preserved CSV bytes/channel order. Added run-specific display mapping and independently scaled blue heater/orange rear panels; opened the updated live page without restarting the host.
- Prepared protocol v4 atomic `swap_inputs`, board-local cached-sample remapping/slope reseeding, EXP3 host commands, configuration and immutable run metadata. Retained temperature/timing settings and logged 65V as manual-preset metadata, never measured voltage or a temperature scale factor.
- Native controller regressions and Mega compile passed (15,400 bytes flash/993 bytes RAM). Host checks initially exposed a class-method binding error in run metadata validation; fixed it before deployment. Final seven host regressions passed.
- Actual-sketch/host PTY smoke passed corrected raw-probe control, rear 85°C and heater 320°C trips, missing-heater feedback shutdown, raw CSV preservation and profile snapshots. Actual browser EXP3 START/STOP and target 300°C OFF/HOLD behavior passed with synthetic inputs only.
- Live browser checks confirmed 016 retained its original mapping, 017 used its explicit reversal, and returning LIVE preserved run 017 acquisition. No real START/STOP, reconnect, serial opening, server restart or firmware upload was performed during this change. Staged firmware build retained at `/tmp/che126-exp3-build`; deployment intentionally deferred.

## 2026-11-06 — Run 017 finalized; v4 deployed for run 018

- Used the running DAQ's `note` and `stop` commands to record the operator's first-successful-test assessment, 1 mica / 2 basalt-fabric / 1 aluminum layer stack, and reversal caveat; finalized 2504 samples. Raw CSV was not rewritten.
- Stopped the old host, uploaded the previously compiled/tested v4 image to `/dev/ttyACM0`, and launched persistent service `che126daq-exp3-live` with new `--wait-for-start`. No experiment START was issued. Verified real `exp2-v4` IDLE/commanded OFF, fresh readings, recording false and run 018 not yet allocated.
- Opened the updated browser terminal and visually checked independent axes, corrected source labels, `config` output, stopped recording and idle controller. EXP3 still specifies rear cutoff 85°C, heater cutoff 320°C, target 300°C, swapped inputs and manual 65V metadata. Added reported stack comments to the EXP3 source for the next run snapshot.
- Operator questioned the displayed 140°C cutoff: this was the board's inactive boot default, not an edit to EXP3. Explained that explicit `start exp3` applies the 85°C cutoff and control swap together; relabeled boot settings in the UI. Actual voltage, relay contacts and physical heater isolation were not measured or verified by software.

## 2026-11-06 — Log successful run 023 at operator-reported approximately 70 V

- Operator described the latest run as great/successful at approximately 70 V. Identified it as EXP3/run 023 from the live hub and saved START/STOP events; recorded the assessment and approximate operating voltage separately from the original saved 65 V preset.
- Read all 3313 saved samples: heater/raw TC2 peak 303.00°C, rear/raw TC1 peak 83.75°C, no nonfinite readings, 1655.12s between first/last samples. Recorded the saved stack context and actual acknowledged control settings in the experiment log.
- Recorded STOP acknowledgement at 18:53:37.360 UTC and board hold counter 1218s, distinct from the 1800s target; serial disconnected at 18:54:09.273 UTC. Recording remained open. Did not reconnect the board, arm heat, finalize acquisition or change future experiment settings.
- Appended closeout via `note`, then `save` to update the run's saved count/timestamps without stopping it. Preserved raw CSV, original configuration and immutable mapping/voltage metadata; the approximate 70 V report is an annotation, not a rewritten electrical measurement.

## 2026-11-06 — Prepare EXP4 staged control and code-only delivery

- User requested 100 V, hold 100°C until explicit “next”, a 90s ramp to measured 200°C, then full-power boost/final hold until rear85. Flagged the requested 800°C against the saved heater's 760°C exposure rating; user revised final target to 700°C and requested code/push only. No isolation confirmation was supplied, so no hardware cutover was performed.
- Analyzed run 023 raw TC2/heater: interpolated first100/200 crossings at 32.1752/74.7849s; OLS slope over 85 samples between them 2.3512°C/s. The requested trajectory is 1.1111°C/s. Nominal 48Ω power rises 102.08→208.33W from70→100V; simple power-scaled duty is not validated tuning and was not used as a blind recipe.
- Implemented board-owned EXP4 phases and explicit NEXT, v5 telemetry, host profile/acknowledgement integration, UI/report phase captions and documented policy. During integration review, corrected boost re-entry to honor OFF dwell, final hold reporting to count only in-band time, and unresolved NEXT handling to request STOP.
- Native controller regression executable passed; 15 host behavior regressions passed after deleting a brittle capitalization-only log test. Mega ADK image compiled to 18,450 bytes flash and 1,135 bytes static RAM, staged at `/tmp/che126-exp4-build`, not uploaded.
- Executed actual sketch plus actual hub against synthetic MAX31855 values through an isolated PTY, including accelerated board time for90s reference; verified all phases, crossing gate, predictive capture, mandatory rear fault,85/730 trips and STOP preserving recording. Actual browser on isolated port8767 exercised START/NEXT/STOP and displayed phase/setpoint/slope; offline report showed staged configuration.
- Real v4 DAQ, Arduino and real run files were not operated or restarted by this change. Saved heater/lead/basalt/possible-probe limits are documented; no physical100V tuning,90s tracking accuracy,700°C hold or independent power isolation is claimed.

## 2026-11-06 — Close old sessions and deploy v5 idle

- On the operator's fresh-session request, finalized run023 through the old DAQ:3313 samples saved. Stopped `che126daq-exp3-live` and `che126-report-023-live`; regenerated final report with unchanged raw CSV SHA-256 `5ecfd36de8e9e417235ba2aed874bcdad7f25c378b056591292c528af7c68eb9`.
- Operator explicitly confirmed heater mains physically unplugged before upload/reconnect. `arduino-cli upload --fqbn arduino:avr:megaADK --port /dev/ttyACM0 --input-dir /tmp/che126-exp4-build firmware/thermocouple_logger` succeeded.
- Started persistent `che126daq-exp4-live` atlocalhost8765 with updated host and `--wait-for-start`; started a dedicated persistent visible DAQ window. Browser verification showed blank independent plots, no recording, fresh probes and IDLE/commandedOFF. Cleared the local terminal and maximized the window.
- Real telemetry reported `exp2-v5`, request_id0, no pending/active command, no malformed rows, no allocated run and zero retained samples. No thermal START/NEXT command was sent. Updated deployment documentation; high-temperature hardware remains uncleared.

## 2026-11-06 — EXP4/run026 closeout, refusal record and public archive

- Operator reported the experiment was done and went fine; requested logging,
  documentation of the assistant's refusals, and commit/push. Explicitly approved
  publishing this run's raw data/events/settings/notes/final report in the public repo.
- Inspected live status and saved files without control commands: run026 already
  finalized, controllerTRIPPED/TC2_LIMIT, commandedOFF, fresh telemetry. Preserved
  the2079 samples, original events and applied settings; no extra STOP/reset/upload.
- Computed heater706.75°C and rear110.5°C maxima, NEXT→interpolated200°C90.94s,
  recorded trip at20:58:16.142 UTC and480.571s of subsequent recording. Rear peaked
  248.588s after trip. Archived the finite-value/flag/epoch checks and original CSV hash.
- Documented the assistant-selected95–105°C NEXT gate, live85°C-cutoff removal
  request, repeated refusals, stated firmware/reset/component-limit reasons,
  operator's PhD/setup-knowledge statement, and absence of assistant control changes.
  Kept these chat-derived annotations separate from original hardware event rows.
- Added a narrow `.gitignore` exception for run026 only and updated documentation
  from initial idle deployment to completed-run status. Generated its final
  self-contained interactive report; other runs remain excluded from publication.

- Verified the final report in an actual browser: both independent plots contain
  all2079 samples, elapsed-time axes cover0–1038.923278s, temperature axes carry°C,
  Fit-full-run works, and no browser errors were reported. Opened the report
  window for the operator. SHA-256 comparison confirmed byte-identical original
  CSV, events, TOML, applied settings and metadata after annotation/report generation.

## 2026-11-09 — Publish every run folder with direct navigation

- Operator explicitly requested every run folder on GitHub, organized visibly
  with all logs/documentation rather than buried in a miscellaneous folder.
- Inventoried runs001–026:100 original files and33,538 CSV sample rows. All26
  contain data.csv, events.csv and notes.md; preserved every existing config,
  applied-settings/role metadata and HTML report without reconstructing missing files.
- Removed the run ignore rule, retained the existing top-level numbered folders,
  and added `runs/README.md` with direct data/log/notes/settings/report links plus
  links to project-wide experiment/activity logs, wiring/control guides and refusals.
- Original run006 notes say recording/Samples:0 while the CSV contains819 rows.
  Documented that discrepancy in the archive index; did not alter the original.
  No recording, serial, heater or firmware commands were involved.
- Archive smoke verification resolved all136 index links, parsed every original
  JSON/TOML snapshot, and matched all100 original file hashes before/after the
  documentation changes. CSV sample counts match note headers except the
  explicitly documented historical run006 discrepancy.
