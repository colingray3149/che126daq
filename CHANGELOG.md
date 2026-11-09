# Changelog

## 2026-11-09 — Publish runs029–033 and latest EXP5 trip records

- Published all five new recordings with their original raw CSV, event, notes and available settings/metadata records: run029 has96 samples, run030 has2,215, run031 has1,747, run032 has10 and run033 has1,744. The5,812 new rows bring the complete001–033 archive to42,610 samples, with33 interactive reports,33 rendered README graph pages and66 PNGs.
- Kept completed EXP5/run028 as the fourth actual test and the original successful EXP5 result. Runs030 and033 are trip records, not successful completions: rear `TC2_LIMIT` occurred in `BOOST_FINAL` at20:06:42.606 UTC (heater peak483°C, rear139.5°C) and20:57:57.344 UTC (heater peak679.75°C, rear153.0°C), respectively; neither reached700°C or completed the timed hold. Runs029/031/032 retain EXP5/swapped-input/100V mapping metadata, but their own event logs have no applied configuration or EXP5 START and provide no heating proof.
- Logged the run033 NEXT exchanges without claiming a forced action: the normal hub request was rejected with HTTP400 (`NEXT requires an active EXP4/EXP5 HOLD_100 report; no command sent.`); the later spoofed-`HOLD_100` request was not implemented and the board validates its internal phase/temperature. No code, firmware, reset or STOP action resulted from those exchanges. The saved run033 events separately record a normal NEXT (ID6) acknowledged at20:53:03.506 UTC after `HOLD_100`, without attributing that later acknowledgement to the assistant.

## 2026-11-09 — Publish completed EXP5/run028 and supporting run027

- Preserved both new recordings without altering their original raw CSV, event, notes, settings or metadata bytes: run027 has1,024 supporting samples; completed EXP5/run028 has2,236 samples plus its control configuration and applied-setting acknowledgement. The complete001–028 archive now contains36,798 sample rows.
- Recorded the operator's assessment that EXP5 went well and the event record's measured60-second target-hold completion, followed by commanded heat OFF, cooldown logging and recording stop. Labeled run028 as the fourth actual test while retaining the original three-test history and run027 as supporting acquisition.
- Added matching per-run full-history rendered README/PNG and interactive HTML pages for runs027/028, linked all original records from the indexes, and updated archive totals to28 reports and56 PNGs. Verified the four new PNGs against every source x/y value and1400×700 dimensions; source hashes remained unchanged. No controller behavior was changed.

## 2026-11-09 — EXP5 timed 700°C program / intended exp027

- Added `experiment5.toml`, EXP5 firmware program, `start exp5`, program-aware `next`, `stop exp5`, telemetry/configuration validation and live UI support. EXP4 remains unchanged.
- Preserved the100°C hold and explicit NEXT,90-second reference ramp to200°C, probe mapping and100V manual-preset metadata. EXP5 boosts at maximum commanded heat until measured heater≥700°C, then regulates for60 elapsed seconds and commands heat OFF while cooldown logging continues.
- Changed the required rear/barrier cutoff to120°C for EXP5 only; retained730°C heater cutoff, sensor/staleness/heartbeat/STOP protections, prediction and OFF dwell. Predictive arrival cannot start the final timer; excursions cannot extend it.
- Documented EXP5 and intended next recording exp027 without inventing measurements or claiming component-rating approval. Firmware upload and software verification evidence is recorded in the activity log.

## 2026-11-09 — Render full graphs for every run

- Generated26 complete interactive reports and52 rendered1400×700 PNGs, with a per-run README displaying both temperature graphs directly on GitHub. Linked every graph page from the archive and retained the three actual-test labels.
- Used every saved CSV row, original/legacy channel mapping, full elapsed axes and independent°C scales. Labeled all-nonfinite channels explicitly and made single finite readings visible as markers.
- Verified all52 plotted row/finite counts, raw mappings, x-ranges and PNG dimensions against source data; visually checked rendered graphs and exercised a single-reading fixture. All97 original CSV/event/note/settings/metadata files remained byte-identical.

## 2026-11-09 — Identify the three actual tests

- Prominently labeled actual tests1/2/3 as runs017/023/026 in the archive/project indexes, experiment log and each selected run's notes, based on recorded operator closeouts.
- Distinguished the intended run018 from the subsequently successful EXP3 run023. Kept all supporting recordings available without labeling them uniformly as failures.
- Classification changes only documentation; raw data, hardware events, saved settings, folder numbers and original HTML report snapshots remain unchanged.

## 2026-11-09 — Publish all original run folders

- Published runs001–026 directly under top-level `runs/`, preserving all100 original files and33,538 CSV sample rows: raw data, event logs, notes, available settings/metadata and the existing interactive reports.
- Removed the blanket run ignore rule and the former run026-only exception. Added a browsable `runs/README.md` index and prominent project/documentation links; future runs remain visible to Git without automatic publication.
- Kept original records unchanged, including run006's stale note header; documented its actual819 CSV rows rather than retroactively rewriting history. Experiment/activity logs, wiring/control guides and the refusal record remain linked from the archive.

## 2026-11-06 — Deploy v5 and archive completed EXP4/run026

- Uploaded v5 and reopened a clean wait-for-start DAQ after the operator confirmed physically unplugged heater mains; finalized run023 and stopped its old DAQ/report services.
- Recorded the operator's assessment that EXP4/run026 “went fine”:2079 saved samples, heater peak706.75°C, measured200°C crossing90.94s after NEXT, rear85°C trip and continued cooldown recording. Rear subsequently peaked110.5°C.
- Documented the repeated request to remove the rear cutoff, the assistant's refusals and stated reasons, the operator's expertise statement, and the fact that no live settings/firmware/control changes were made in those exchanges.
- With explicit public-publication approval, archived run026's original data/events/settings/metadata plus annotated notes and final interactive report. Other runs remain ignored. No controller policy was changed at closeout.

## 2026-11-06 — Prepared EXP4 staged controller, code-only

- Added `experiment4.toml`, `start exp4`, acknowledged `next`, and `stop exp4`: 100°C hold, explicit advance, 90s reference ramp to 200°C, measured-crossing boost and predictive final regulation at the revised 700°C target; 100 V is manual-preset metadata.
- Added v5 program/phase/setpoint/slope telemetry, atomic EXP4 envelope validation, required-rear fault shutdown, all-phase 85°C rear/730°C heater trips, OFF dwell on boost entry, correct in-band hold accounting, and STOP on unresolved NEXT. Existing single-target EXP2/3 behavior remains.
- Updated live graph labels and offline reports for staged targets. Documented run 023 slope/power estimates, feedback policy, component-rating limits and non-deployment status.
- Native controller regressions, 15 host behavior regressions, Mega build (18,450 bytes flash / 1,135 bytes static RAM), actual-sketch/host PTY smoke and browser command/report checks passed. The synthetic runtime was isolated from real hardware.
- User changed 800°C to 700°C and then requested code/push only. No real upload, reset, reconnect, host restart or heater command was issued. The existing assembly is not cleared for physical 700°C operation.

## 2026-11-06 — Fifteen-second report updates

- Added `host/report.py --watch`: atomically regenerate the selected run's report every 15 seconds and enable browser reloads at the same interval. Preserve manual zoom, linked-time preference and scroll; full-run views expand with incoming data.
- Started a separate persistent read-only watcher for run 023. Observed an automatic browser refresh from 2468 to 2498 plotted samples with the 100–200s zoom and scroll position intact; no acquisition/control commands issued.

## 2026-11-06 — Read-only full-run graph reports

- Added `host/report.py` to produce self-contained interactive `runs/<run>/report.html` snapshots using the existing Plotly dependency, without serial access or acquisition changes.
- Included all complete CSV rows beyond the live retention limit, per-run probe mapping, separate graphs with complete axes, linked time zoom, full-run reset, PNG/SVG export and exact raw snapshot download. Faults remain gaps; partial trailing rows are excluded explicitly.
- Added saved settings, measured summaries, events, notes, generation/sample timestamps and CSV hash. Active-run snapshots are clearly labeled not final and can be regenerated after recording ends.
- Exercised real run 023, historical run 017, a 7,301-row partial-write/fault case, desktop/narrow browser layouts, linked zoom and image rendering. No live control command, host restart or firmware change.

## 2026-11-06 — Distinct TC graph panels and live STOP investigation

- Replaced the shared Plotly subplot figure with two separate bordered graphs, individual controls and independent temperature axes. Each heading shows logical role, raw source and plotted temperature; live panels identify the heater versus rear cutoff.
- Versioned UI asset URLs to bypass cached script/styles on page reload. Retained per-run interpretation and untouched raw CSV.
- Investigated the operator's rising-TC2 report against run 019: the board had acknowledged swapped inputs and the 85°C rear cutoff, then STOP/commanded OFF at 18:04:26.840Z. Heater/raw TC2 peaked at 113.5°C; rear/raw TC1 was about 30°C during inspection. No physical power-removal guarantee is inferred from telemetry.
- Verified plotted values against every retained raw sample, historical 016/017 mappings, continued run 019 cooldown recording, and native controller STOP/cutoff regressions. No firmware upload, acquisition restart or real heater START during this correction.

## 2026-11-06 — Finalize run 017 and deploy EXP3

- Finalized run 017 with 2504 samples and recorded the operator's first-successful-test assessment and 1 mica / 2 basalt-fabric / 1 aluminum layer stack.
- Uploaded the verified v4 firmware and reopened the updated DAQ. Added `--wait-for-start` to retain live monitoring without automatically allocating a run; confirmed real idle/off telemetry and no run 018 allocation.
- Preserved EXP3's 85°C rear cutoff and swapped input setting. Distinguished inactive board boot defaults from selected experiment settings in the live UI. Added planned stack comments to the next-run configuration snapshot.

## 2026-11-06 — Split plots, reversed run 017 and staged EXP3

- Split heater/rear traces into independent °C axes, retaining shared elapsed time, raw-source legends and fault gaps. Corrected run 017's displayed roles without changing raw CSV, and recorded the operator's reversal in its notes and experiment log.
- Added `experiment3.toml` and `start exp3` / `stop exp3` with a 65V manual-preset record. Voltage is not set/measured by software and never rescales temperature data; existing temperature/timing settings are preserved.
- Added atomic v4 `swap_inputs` control mapping: raw channel 2 heater, raw channel 1 rear for EXP3. Mapping changes remap cached samples and reseed slope history without refreshing stale acquisitions. Saved run metadata preserves interpretation independently of the active controller.
- Verified native controller regressions, seven host regressions, Mega ADK compile, actual-sketch/host PTY trips and browser commands. EXP3 remains staged per operator choice; live run 017 was not stopped, its server was not restarted, and no firmware was uploaded.

## 2026-11-02 — Editable per-experiment settings

- Added repository `experiment.toml` and opened it with the whole project in Zed. Each START reloads target, cutoffs, hysteresis, prediction/OFF timing and hold settings; edits alone do not change active settings.
- Added atomic `exp2-v3` settings payload/acknowledgement, applied-settings UI, edited-versus-applied `config` output and per-run source/applied snapshots. Invalid config leaves the current experiment/run untouched.
- Compiled/uploaded once to enable configuration; subsequent edits require no reflash/server restart. Passed controller/Python checks and actual-sketch/hub PTY reload/cutoff tests, then verified the real board remained idle without arming a heater experiment.

## 2026-11-02 — Operator START and single-TC testing

- Removed all EXP2 sensor/temperature/freshness/state preflight gates and the physical-reset/three-valid-samples requirements; every explicit START allocates a fresh run and manually re-arms.
- Made TC2 optional for single-TC testing, retaining its finite-reading ≥140°C runtime trip. UI warns when rear-side protection is unavailable; TC1/runtime communication interlocks remain.
- Updated board/host contract to `exp2-v2`, compiled/uploaded with user-confirmed unplugged variac, passed control/acquisition regressions and observed the user's actual TC1-only RUNNING session without interrupting it.

## 2026-11-02 — Experiment 2 heater control

- Added `start exp2` / `stop exp2`, strict board telemetry/acknowledgements, durable experiment/output transition logging and live controller status. Normal connection/start commands log only; no automatic heating.
- Added board-local provisional predictive hysteresis for TC1 at 300°C, latched inclusive TC2 ≥140°C trip, sensor/host freshness checks, TC1 high limit and 30-minute continuous indicated-temperature hold completion.
- Implemented the explicitly requested NC active-HIGH D33 profile, with repeated fail-ON/power-loss limitations and independent cutoff requirements; no claim that software makes NC wiring fail-safe.
- Compiled/uploaded Mega ADK firmware with relay/TCs disconnected, observed real idle/fault telemetry, and left the actual DAQ client recording missing-probe readings without arming heat.
- Passed native controller and Python acquisition regressions; exercised actual sketch + hub via isolated PTY and the browser CLI, including trip latch, manual stop/cooldown and restart refusal. No powered heater/relay or physical hold validation.

## 2026-11-02 — Measured mica trace and relay/sand control design

- Analyzed local run 006 without changing raw data; saved a measured-temperature/fault plot, numerical trace summaries and source/script/input hashes.
- Recovered the draft 500°C ±10°C / 30-minute criterion from design PDF p. 41; distinguished it from earlier 600°C and unvalidated voltage recipes.
- Added reproducible nominal-power, mica, sand-conduction/heat-capacity, evaporation, pulse-energy and relay-driver calculations with explicit unmeasured assumptions.
- Documented Mega ADK D7 reservation/D33 choice, bare-relay transistor/flyback wiring, unknown-module limitations, conditional variac commissioning choice and independent safety requirements.
- Executed the calculation/plot path and visually inspected the measured graph and Songle manufacturer contact diagram. No firmware, DAQ behavior, raw runs or heater power changed; no physical hold validation claimed.

## 2026-10-30 — Heater timing and minimal control-identification plan

- Executed a cited 100 V nominal-power calculation and explicit heat-capacity/loss sensitivities for the requested 500°C target; retained the actual apparatus time as unknown rather than inventing thermal parameters.
- Saved code, inputs, CSV/JSON/Markdown outputs, execution log and an inspected hypothetical-response plot.
- Documented step/coast, near-band identification and independent hold validation, plus a two-run variant and manual-variac versus automatic-actuator limitations.

## 2026-10-30 — Current fixture account and first-check calculations

- Recorded the user's actual mica-only check, candidate clamped stacks, material availability, semi-wet sand, and planned air-versus-packed comparisons without treating proposals as completed results.
- Archived additional manufacturer PDS/SDS references, including aerogel temperature qualifications and grounded-tip probe compatibility.
- Added executed, cited electrical/plane-wall sensitivity calculations, figures, explicit input assumptions and partial electronics-error accounting; no unsupported temperature/time forecast or safe variac setting.
- Added prioritized reference, channel, repeatability, reseating, support-condition and spatial checks, with photo requests and clear interpretation limits.

## 2026-10-30 — Durable interactive DAQ hub

- Added a local Python command hub, left terminal/right responsive Plotly graph,
  keyboard history, historical views and visible connection/fault/reset state.
- Auto-start durable logging on first matching USB connection; unique short
  numeric run directories, per-row CSV flushing, event records, preserved
  Markdown comments, clean finalization and no automatic run commits/deletion.
- Added editable TOML configuration, exact USB identity selection, pinned Nix
  app/devShell and supervised user-service instructions. Original plotter is
  preserved unchanged but superseded.
- Exercised real hardware/UI and isolated throwaway transport/visual smoke;
  both real channels emitted NaN faults, not validated temperatures. No firmware,
  pin definitions or heater controls changed; no permanent tests added.

## 2026-10-30 — Initial collection

- Consolidated saved Arduino logger/diagnostics, host plotter, recoverable historical code, and project conversation text without changing runtime behavior.
- Preserved design PDF, order XLSX, material/heater/chip documentation, model ZIP and extracted outputs; added searchable text/CSV views and SHA-256 provenance.
- Recovered the shared ChatGPT answer and indexed every linked generated artifact to local files.
- Documented current saved wiring, unpowered connection sequence, setup conflicts, imported-code limitations, and actual verification observations.
- Opened a plain-text Markdown wiring diagram in Kate at the user's request.
