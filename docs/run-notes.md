# Running the DAQ hub and imported code

The hub is the primary interface. Firmware and the historical plotter remain unchanged.

## Arduino

Observed installed dependencies: Arduino AVR Boards **1.8.8**, Adafruit MAX31855 library **1.4.2**, Adafruit BusIO **1.17.4**. Board FQBN: `arduino:avr:megaADK`.

```sh
arduino-cli board list
arduino-cli compile --fqbn arduino:avr:megaADK firmware/thermocouple_logger
```

Compilation does not upload. No upload was performed during this collection. Select the actual port after each replug; `ttyACM0` is today's observation, not a stable device name. Do not replace firmware or switch diagnostic sketches without matching their wiring and serial format first.

`tc_fault` uses the current logger pin map but outputs human-readable diagnostics. `tc_diag` uses an OLD pin map; see [wiring.md](wiring.md). Neither diagnostic output is a compatible input to the CSV plotter.

## DAQ hub (primary interface)

```sh
nix run path:/home/colin/Projects/che126daq
# development, using the same pinned Python dependencies:
nix develop path:/home/colin/Projects/che126daq
python host/hub.py --config /home/colin/Projects/che126daq/hub.toml
```

Open http://127.0.0.1:8765. Plotly is served locally from the Python package,
not a CDN. Server binds IPv4 loopback only. Keep exactly one serial reader;
the hub opens with Linux exclusive access. It does not upload firmware.
`start exp2` explicitly arms compatible board-local heater control; see
[EXP2 operation](exp2.md). Opening/reconnecting may reset the board, which is
unsafe with an energized NC-wired heater: physically disconnect heater power first.
Auto-detection requires the configured VID, PID **and serial number** to match
exactly one device. An explicit port overrides identity selection. No automatic
retry loop: use `reconnect` after correcting a missing/disconnected device.

By default, the first successful serial open automatically starts a saved run
(valid temperature measurements are not required). Launch with `--wait-for-start`
to monitor live sensors without allocating a recording until an explicit START;
this also avoids allocating a baseline run before the next numbered experiment.
`stop` leaves serial monitoring open but discards subsequent samples until
`start`; the graph freezes.
`restart` finalizes and allocates a new run. `save` flushes and refreshes
metadata without stopping. `clear` clears only the requesting browser view.
`list` / `view 001` loads a labeled saved snapshot while live logging continues;
`live` restores the active stream. `note text` always appends to the **active**
run, even while viewing history. `window 120` / `window all` changes the plot
window; zoom/pan and legend toggles are available. `help`, `status`, `config`
and `channels` expose details; unknown commands/errors remain visible.
↑/↓ recalls the last 100 commands in this browser's local storage.

`start exp2` starts a fresh saved run and manually re-arms without pre-start
sensor, temperature, IDLE-state or physical-reset gates. `experiment.toml`
supplies the target, runtime cutoffs, hysteresis and timing; TC2 stays optional.
Cooling alone never re-arms, but an explicit new START works after stop/trip.
`stop exp2` stops heat while retaining cooldown logging. Plain `stop` must
confirm heater stop before finalizing recording. Active control cannot be
silently abandoned by `restart` or `reconnect`. Compatible telemetry, command
acknowledgements and controller transitions are shown/logged; an unavailable
link means the physical heater state is unknown, not guaranteed OFF.

`start exp3` / `stop exp3` have the same lifecycle using `experiment3.toml`,
with reversed probes: raw TC2 is logical TC1/heater, raw TC1 is logical TC2/rear.
Both settings files include the host-only manual `variac_voltage_V` record;
software does not set or measure that voltage. The idle board's boot defaults
are not the selected experiment's settings; explicit START applies that file.

EXP4 uses `start exp4`, `next` and `stop exp4` with `experiment4.toml` and the
deployed v5 host/firmware pair. Its fixed first phases hold 100°C, await explicit
NEXT, then track a 90-second reference to 200°C before measured-crossing boost
and final hold. Both probes are required and rear cutoff is fixed at 85°C.
See [EXP4 policies and limits](exp2.md#exp4-staged-100-v-program).
The v5 host/firmware pair is deployed with `--wait-for-start` after confirmed
heater mains isolation. EXP4/run026 has since completed and is publicly archived.
Keep power physically isolated for any later upload/reset; software deployment
does not establish thermal limits.

EXP5 uses `experiment5.toml`, `start exp5`, `next`, and `stop exp5`.
It retains the first EXP4 stages, then commands full boost until measured700°C,
regulates for60 elapsed seconds from that crossing, and commands heat OFF.
Its required rear cutoff is120°C; EXP4 remains85°C/untimed. See
[completed EXP5/run028](experiment5.md). The operator said run028 went well;
its saved events record measured completion of the60-second target hold, followed
by heat OFF and cooldown. Run027 is the prior supporting recording. Both original
recordings are archived with full-history reports and rendered graph pages.

`hub.toml` configures the DAQ connection/storage/UI; restart the server after editing it.
`experiment.toml`, beside that file, configures control and is reread on every
`start exp2`; no server restart or reflash is needed for experiment edits.
Editing it alone does not change an active controller. `config` shows edited
and applied values; saved runs include the selected `experiment.toml` or
`experiment3.toml`, `experiment-applied.json`, and `run-metadata.json`.
Nix defaults to `$HOME/Projects/che126daq/hub.toml`, regardless of working
directory; override with `CHE126DAQ_CONFIG` or `--config`.
Relative `runs_dir` resolves beside the config, never beside the Nix store copy.
`--runs-dir /tmp/...` and `--port ...` are explicit isolated smoke overrides.

Runs allocate numeric directories by atomic mkdir, increasing beyond existing
numeric entries, never overwriting previous directories. Files:

- `data.csv`: host UTC, independent monotonic host elapsed seconds, original
  board uptime, reset epoch, TC1/TC2 °C, fault/reset/all-zero flags; flushed each row.
- `events.csv`: timestamped startup/header, malformed/oversized rows, disconnect,
  regression and command-stop events. Partial lines wait for newline; oversized
  partial buffers are discarded visibly. Missing/NaN temperatures remain gaps;
  real zeros remain zero with an explicit all-zero caveat. No sensor identity,
  fault cause, calibration or validity is inferred.
- `notes.md`: generated timestamps/config/device/sample count/stop reason plus
  user-owned content after `## Comments` (initially a literal blank line).
  Metadata updates preserve that suffix; deleting the heading causes a visible
  refusal rather than replacing notes. `note` appends timestamped text.

All rows stay on disk; live and historical graphs retain at most `plot_points`
(default 7200). Historical plots use the last retained saved rows. Board resets
increment epochs; x is independent host elapsed time. A disconnected device
leaves the run open, with missing time visible; explicit reconnect resumes it.
Browser refresh/disconnect does not own acquisition. Ctrl-C or SIGTERM finalizes
the run. Abrupt kill/power loss can leave metadata marked recording; per-row
flush is not an fsync/power-loss guarantee. Do not delete/move active run files.
Runs are never automatically committed, pushed or deleted. The operator approved
publishing **all run folders**; `.gitignore` no longer excludes `runs/`.
The [top-level archive index](../runs/README.md) links every recording's original
CSV, events, notes and available settings/metadata/reports. Missing historical
snapshots are not fabricated. Run006's original notes retain a stale zero-count/
`recording` header even though its CSV has819 rows; the index reports CSV counts.

### Full-run interactive reports

The live dashboard retains at most `plot_points`; use the read-only report
generator for **every saved sample**, including runs longer than that limit:

```sh
nix develop
python host/report.py runs/023
xdg-open runs/023/report.html
```

Choose the actual run folder. The output is a self-contained, offline HTML file
with embedded Plotly: no CDN, serial connection, DAQ restart or heater controls.
It includes separate blue TC1/heater and orange TC2/rear graphs, independent
temperature axes, complete axis titles/units, optional linked time zoom, full-run
reset, high-resolution PNG and SVG export, and a raw-CSV snapshot download.

Every archived run001–033 now has `heater.png`, `rear.png` and a `README.md`
that embeds both images for direct GitHub viewing. These1400×700 PNGs were rendered
from the report's actual Plotly graphs with the full x-axis range, not from a
cropped screenshot. They contain every saved sample; missing values remain gaps.
An entirely nonfinite channel is labeled “No finite temperature samples” rather
than fabricated as a zero trace; a lone finite sample is shown as a marker.
The original three actual tests remain prominently labeled in the archive and run
pages; successful EXP5/run028 is separately labeled as the fourth actual test.

Regenerate a run's report and both PNGs with `python host/report.py --png runs/<run>`
(in `nix develop`; kaleido writes the same 1400×700 figures). Earlier archive PNGs were browser exports.
Static images are snapshots: regenerating HTML alone does not update the PNGs.
For an updated image, open the new report, choose **Fit full run**, and use the
camera export on each graph; save the results as `heater.png` and `rear.png`
beside that run's CSV before committing. The browser export used for this archive
was `Plotly.toImage(graph, {format: 'png', width: 1400, height: 700, scale: 1})`.

Run metadata/legacy corrections determine the plotted channel roles; raw CSV
is never reordered or rewritten. Saved controller settings, summary statistics,
recorded events and notes provide context without claiming measured heater power.

Reports take a bounded snapshot of the CSV, including every complete row and
preserving missing readings as gaps; an incomplete trailing row is excluded and
reported. No smoothing/downsampling or voltage rescaling is applied. The report
includes its generation time, first/last sample timestamps and CSV SHA-256.
While the run's saved state is `recording`, it is prominently marked **not final**.
The saved state may remain `recording` after an abrupt shutdown; the report does
not independently determine whether acquisition is still alive.

For automatic updates while recording, run:

```sh
python host/report.py runs/023 --watch
```

The watcher regenerates `report.html` every 15 seconds; the generated page
reloads every 15 seconds and preserves zoom, linked-axis preference and scroll
using browser session storage. Fit-full-run views expand with new data.
Open/reload the report once after starting watch mode. Browser background-tab
throttling or rendering time may delay visible refreshes; generation and page
reload are separate schedules, so check the displayed last-sample timestamp.
The watcher remains tied to the selected run folder, not subsequent runs.
Neither START nor NEXT launches this separate report watcher or opens its page.
For the completed public example, open `runs/026/report.html` from a clone or
download the HTML and open it locally; GitHub's source view is not the plot UI.

Stopping this watcher does not stop acquisition; the page then only reloads
the last generated snapshot. For a static final report, stop the watcher and
rerun without `--watch` after normal run finalization. Only `report.html` is
replaced atomically. Reports are kept beside their source data in the numbered
run folders and included in archive commits; all33 runs have generated HTML
reports and66 rendered PNGs (42,610 saved sample rows across runs001–033).
Opening them does not restart acquisition or control heat.

For a supervised user service, without tying acquisition to a shell:

```sh
systemd-run --user --unit=che126daq-hub --collect \
  --working-directory=/home/colin/Projects/che126daq \
  nix run path:/home/colin/Projects/che126daq
systemctl --user status che126daq-hub
journalctl --user -u che126daq-hub
systemctl --user stop che126daq-hub
```

Stop the existing service before starting another port reader. The service
survives browser/shell closure, not necessarily user logout; no login/boot
autostart or linger setting is installed.

The service left running on 2026-10-30 uses the already-built executable,
GC-rooted at ignored `build/hub`, so it does not wait on Nix cache availability.
After stopping that service, relaunch that same installed build with:

```sh
systemd-run --user --unit=che126daq-hub --collect \
  --working-directory=/home/colin/Projects/che126daq \
  /home/colin/Projects/che126daq/build/hub/bin/che126daq
```

For rebuilding when this workstation's configured private cache is unavailable:

```sh
nix build path:/home/colin/Projects/che126daq \
  --option substituters https://cache.nixos.org --option builders '' \
  --out-link /home/colin/Projects/che126daq/build/hub
```

Commissioning evidence: [activity log](activity-log.md#2026-10-30--interactive-durable-daq-hub).
Real board input was `nan` on both channels; no valid temperature or attached
probe was established. Real historical rendering, live recording during history,
refresh persistence, command history, two laptop layouts, isolated PTY edge
cases and separately labeled synthetic curves/gaps were exercised. All
throwaway scripts/datasets were removed; no permanent tests were added.

## Historical live plotter (superseded)

On this NixOS workstation the original executable script has a nix-shell shebang for matplotlib, pyserial, and tkinter:

```sh
./host/plot.py /dev/ttyACM0
```

Or use an explicitly provisioned Python environment with those packages:

```sh
python host/plot.py /dev/ttyACM0
```

Close other serial readers first. The plot opens the serial port at 115200 baud and may reset the Arduino. It displays the last 20 seconds; **it does not save data to disk**. CSV header is `time_s,t1_C,t2_C`; time comes from board uptime, nominal interval 0.5 seconds. Fault `nan` is displayed as “fault”.

Known imported limitations, intentionally not fixed in this collection:

- Legend still says `(A1)` / `(A2)` from the early analog version. These are stale labels; actual MAX31855 signals use the digital pins in wiring.md.
- Default port picks the first sorted `/dev/ttyACM*`, not board identity. Specify a port explicitly; no-device and unplug/reconnect handling are not robust.
- All-zero MAX31855 frames are not rejected. The initial collection's zeros did not validate wiring or temperature.
- Uptime/reset/wrap behavior, durable logging and metadata are handled by the hub instead. Calibrated uncertainty remains unverified.

## Thermal model

Dependencies: Python, numpy, scipy, matplotlib. Original ZIP README supplies the model's assumptions and limitations. Run into a separate output directory so original generated artifacts are not overwritten:

```sh
python models/thermal-stack/thermal_stack_model.py --out /tmp/che126daq-model-run
```

Optional example parameter changes are scenarios, not heater-control instructions:

```sh
python models/thermal-stack/thermal_stack_model.py --power 30 --coupling 0.30 --h 15 --target 100 --out /tmp/che126daq-model-run
```

The supplied measurement CSV has blank `TC_C` entries; it is not experimental data. Heater power/coupling, footprint, boundary losses, heat capacities, densities, constant conductivities and contact resistance must be checked before comparing to real apparatus.

## Source provenance

`provenance/source-manifest.json` records byte-preserving imports and ZIP extraction. `provenance/claude/code-history/index.json` identifies reconstructed Write/Edit states. Bash-based changes remain in `code-tool-calls.json`; historical snapshots are not asserted to reconstruct every Bash-modified intermediate state. Current copied sources, not those snapshots, are the latest saved files.

Prior `megaadk-flash.bin`/`.hex` backups are labeled `prior-board-flash.*`: they are historical backups, not a verified binary of today's saved logger and not an instruction to flash them.
