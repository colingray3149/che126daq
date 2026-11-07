# Experiments 2, 3 and 4: operator-controlled START

## EXP4: staged 100 V program

**2026-11-06 deployment status:** after code-only preparation, the operator
requested fresh updated sessions and explicitly confirmed heater mains power
was physically unplugged. Uploaded the verified v5 Mega image and restarted
the v5 host with `--wait-for-start`. Live telemetry confirmed `exp2-v5`,
IDLE, commanded heat OFF, fresh probes and no recording. No START was sent.
Run 023 was finalized at 3313 samples; old DAQ/report services were closed.
The requested final target remains **700°C**, revised from 800°C.
Firmware deployment does **not** clear the assembly for high-temperature operation.

**Later run outcome:** EXP4/run026 is complete; the operator reported that it
“went fine.” Its2079 samples include a706.75°C recorded heater peak, the retained
rear85°C trip and cooldown. See the [published run archive](../runs/026/notes.md)
for exact phase timings, post-trip rear rise and the requested refusal record.
The deployment paragraph above describes the initial idle state, not closeout.

### Hardware limits are not cleared

The saved [4877K305 heater specification](https://www.mcmaster.com/4877K305/)
lists maximum exposure **1400°F = 760°C** and lead exposure **840°F ≈449°C**.
The saved basalt datasheet lists **1200°F ≈649°C**; the possible Adafruit
probe documented in `references/current-check/probe.txt` is rated **500°C**,
and the actual installed probe identity is unverified. The earlier 800°C
request exceeds even the heater's catalog limit.

**The 700°C code setting is not approval to run the existing assembly.**
A rear TC below 85°C does not establish safe heater-lead or intermediate-layer
temperatures. The provisional 730°C software heater trip is not an independent
cutoff or an overshoot guarantee. Probe attachment/calibration, compatible
temperature ratings, lead routing, mounting and an independent power disconnect
must be established before physical commissioning. Keep heater power physically
isolated for upload/reset: the selected NC contact can close on power/reset loss.

### Commands and phase policy

`experiment4.toml` records a **100 V manual preset**, final target **700°C**,
heater trip **730°C**, required rear trip **85°C**, hysteresis **3°C**,
prediction lead **5s**, minimum OFF dwell **5s**, band **±5°C**, no final hold
timer, and the existing reversed-probe mapping. Voltage is never set/measured
by this software. Raw TC2 supplies logical TC1/heater; raw TC1 supplies TC2/rear.

1. **`start exp4` → HEAT_100 / HOLD_100.** Allocate a new run, acknowledge
   the staged program and settings, and regulate toward 100°C. Far below the
   target, ON can be continuous; approaching it, predictive OFF overrides a
   preference for longer ON periods. Entering 95–105°C qualifies HOLD_100;
   leaving that band returns to HEAT_100. There is no automatic timed advance.
2. **Explicit `next` → RAMP_200.** The host and board require the active
   HOLD_100 phase and an in-band heater reading. Start a board-clock reference
   `R(t) = 100 + 100 × min(t / 90s, 1)` °C. Duplicate, early, stale or
   out-of-band NEXT is rejected, not queued. NEXT does not allocate another run.
   Once deployed, an explicit operator “next” in assistant chat authorizes one
   `next` command to the DAQ; no background chat timer advances the experiment.
3. **Measured heater ≥200°C → BOOST_FINAL.** The measured crossing, not expiry
   of 90s, advances the phase. An early crossing advances early. If the heater
   is still below 200°C at 90s, finish the approach with ON permitted after
   minimum OFF dwell; the timer alone never claims the target was reached.
4. **BOOST_FINAL → HOLD_FINAL.** Request continuous ON, subject to OFF dwell
   and all interlocks, until the positive-slope forecast intercepts the final
   target. Then cut OFF and use predictive hysteresis around 700°C. This
   deliberately stops full-power boost before foreseeable overshoot, rather
   than leaving power permanently ON after reaching the target.
5. **HOLD_FINAL continues until STOP or a trip.** No 30-minute completion
   timer. State is HOLD only while actually inside the configured final band;
   `hold_s` is continuous in-band time, not time since predictive capture.

`stop exp4` sends universal STOP and retains cooldown recording; plain `stop`
also finalizes the recording after confirming commanded OFF. Unresolved NEXT
or a mismatched accepted acknowledgement triggers best-effort STOP, never a
NEXT retry. A valid rejected NEXT leaves the current trajectory alone.

### Estimation and feedback policy

Run 023's operator reported approximately **70 V**, while its immutable preset
metadata remains 65 V. Analysis uses the reported 70 V only as an approximation.
First upward crossings are linearly interpolated between adjacent heater/raw
TC2 samples; slopes below use actual host elapsed timestamps:

| Run 023 heating quantity | Value |
|---|---:|
| First 100°C crossing, elapsed | 32.1752s |
| First 200°C crossing, elapsed | 74.7849s |
| 100→200°C interval | 42.6098s |
| Least-squares slope over 85 samples in that interval | 2.3512°C/s |
| Requested 100→200°C reference slope | 1.1111°C/s |
| Nominal ON power at 70 V, assuming 48 Ω | 102.08 W |
| Nominal ON power at 100 V, assuming 48 Ω | 208.33 W |

The historical fit is `sum((t-mean(t))*(T-mean(T))) / sum((t-mean(t))²)`.
Power ratio is `(100/70)² = 2.0408`; simply scaling the measured slope would
give 4.7984°C/s and a 23.16% average duty for 1.1111°C/s. **Neither is a
validated plant model or an implemented fixed-duty recipe.** Actual voltage
history, losses, heat capacity, lag, moisture and changing boundaries are not
identified by that calculation. In particular, forcing ON longer than OFF is
not defensible for the requested slow ramp at twice the nominal input power.

Online feedback reuses the bounded 16-entry history at nominal 500ms sampling:
`slope = (latest valid heater - oldest valid heater within 5s) / actual elapsed`.
This is a trailing secant, **not** the historical least-squares fit. The forecast
is `T + max(slope, 0) × 5s`. For a stationary hold, cut when that forecast reaches
the target. During the unsaturated ramp, compare it with the future reference
`R(t + 5s)`; ON re-entry also requires temperature below current reference minus
3°C and at least 5s since OFF. OFF/trips are immediate, not delayed by dwell.
At the saturated 200°C reference the predictive deadband is bypassed until
actual crossing, to avoid stalling just below the phase boundary.

Rear ≥85°C and heater ≥730°C override all active phases and latch OFF. Unlike
EXP2/3, EXP4 requires a finite rear reading; missing/nonfinite rear trips
`TC2_FAULT`. Invalid heater feedback, 1500ms sample staleness, 2500ms heartbeat
timeout and explicit STOP also override every phase. These are software
commands; relay contact welding, bad probe contact and NC power-loss behavior
still require independent protection. Physical tracking within exactly 90s and
700°C performance have not been demonstrated.

## EXP3: reversed probes and 65V preset

**Historical deployment status:** v4 was uploaded after run 017 finished.
The host reopened with `--wait-for-start`, avoiding automatic run allocation;
later run 023 used EXP3. EXP4/v5 is now prepared in source only. No new upload,
reset, reconnect or live experiment command was issued while preparing EXP4.

Edit [`../experiment3.toml`](../experiment3.toml), save, and use
`start exp3`. Use `stop exp3` to command heat OFF while keeping cooldown logging.
EXP2 continues to select `experiment.toml` and its original input mapping.

For EXP3, **logical TC1 = heater = raw channel 2 (28/30/32)** and
**logical TC2 = rear = raw channel 1 (22/24/26)**. `swap_inputs = true`
selects this mapping for regulation and runtime cutoffs, not just the graph.
Raw CSV columns remain the physical channel order for every profile.
The initial EXP3 file retains target 300°C, hysteresis 3°C, heater cutoff 320°C,
enabled rear cutoff 85°C, prediction lead/minimum OFF time 5s each,
hold band ±5°C and continuous hold 1800s.

`variac_voltage_V = 65.0` records the intended manually set RMS voltage.
It is not measured by the DAQ and does not adjust the variac, scale temperature
data, or automatically retune the controller. Nominal 65V ON power is 88.02W
at the catalog-derived 48Ω, versus 18.75W at 30V (4.694×).
The existing control tuning has not been physically validated at 65V.

Runnable nominal-power calculation (constant resistance assumption):

```python
resistance_ohm = 120.0**2 / 300.0
for voltage in (30.0, 65.0):
    print(voltage, voltage**2 / resistance_ohm, voltage / resistance_ohm)
print("power ratio:", (65.0 / 30.0)**2)
```

### Plots and saved interpretation

The blue/top **TC1 HEATER** and orange/bottom **TC2 REAR** are separate graph
panels, each with its own temperature axis, zoom controls and elapsed-time axis.
The time window command applies to both. Panel headings show the raw source
and latest plotted temperature; live panels show their respective cutoffs.
For EXP3, the 85°C rear cutoff applies to raw TC1, **not** raw TC2/heater;
the heater target is 300°C and its separate high cutoff is 320°C.
No voltage normalization is applied to measured temperatures.
Browser asset URLs are versioned; open the updated page or refresh an older
tab to load changed graphs. Updating files cannot replace JavaScript already
running in an old tab.
Run 017 has an explicit reversed-probe correction in its notes and
`host/web/run-mappings.json`; this does not reinterpret other old runs.
New experiment runs persist profile, mapping and voltage preset in
`run-metadata.json` alongside configuration snapshots. Historical graph mapping
comes from the viewed run, not the current controller.

The display warns when its interpreted probe placement differs from the
controller's currently applied mapping. At boot the board has inactive defaults
(including 140°C rear cutoff and no swap); explicit `start exp3` applies the
file's 85°C rear cutoff and swapped inputs atomically. Do not confuse boot
defaults with edited EXP3 settings. In run 017, `TC2_LIMIT` acted on the heater
probe, not the intended rear probe.

## Editable settings — open in Zed

Edit **[`../experiment.toml`](../experiment.toml)**, save, then type **`start exp2`**.
Each START rereads the file and sends a complete atomic settings snapshot.
No DAQ restart or further reflash is needed for edits. Editing alone does not
change an active run. The live display shows the board-applied values;
`config` shows both edited and applied settings.

| Key | Meaning |
|---|---|
| `target_C` | Desired TC1 heater temperature; normal OFF threshold |
| `hysteresis_C` | ON threshold = target minus this amount |
| `tc1_cutoff_C` | Runtime TC1 high-temperature trip |
| `tc2_cutoff_C` | Runtime rear-side trip when enabled and TC2 is readable |
| `tc2_cutoff_enabled` | `false` disables TC2's temperature trip; TC2 remains optional |
| `prediction_lead_s` | Predictive OFF look-ahead; 0 disables prediction |
| `min_off_s` | Minimum OFF time before another ON command |
| `hold_band_C` | Continuous hold band is target ± this amount |
| `hold_s` | Continuous seconds in band before completion; 0 disables timed completion |

Times normalize to whole milliseconds and temperature parameters to six
significant digits for the board codec. Invalid/missing/malformed config is
reported before changing the existing run or sending START; there is no silent
fallback to old/default settings. Each started run saves the exact source as
`experiment.toml` and requested/acknowledged values as `experiment-applied.json`.
The firmware acknowledgement must match the requested values.

This file does **not** set variac voltage or change relay wiring/polarity.
Runtime sensor/communications protection remains on the board. Choose settings
within the actual equipment limits; editing a number does not raise a hardware rating.


## Commands

Open **http://127.0.0.1:8765** and type:

```text
start exp2
```

Every START creates a **new numbered run folder** and explicitly re-arms the controller. There is **no sensor/temperature preflight, valid-sample streak, IDLE-state requirement, or physical-reset requirement**. START works after STOP, TRIPPED and COMPLETE, and another START while running begins another run/hold timer. Existing data is never overwritten. The connected board still has to receive/acknowledge the command; transport failure is reported honestly, not presented as successful control.

```text
stop exp2
```

Commands heat OFF and retains cooldown logging in the same folder. Plain `stop` stops control before finalizing recording. A new explicit `start exp2` re-arms without resetting the board. Cooling alone never re-arms a tripped controller. Connecting/reconnecting hardware starts logging, not heating.

## Single-thermocouple testing

**TC1 controls toward `target_C` (initially 300°C). TC2 is optional.** A missing/faulty TC2 does not block START or trip a TC1-only test. If `tc2_cutoff_enabled` is true and TC2 provides a finite reading **≥`tc2_cutoff_C`** (initially 140°C), the runtime cutoff commands heat OFF until another explicit START.

**Rear-side protection is unavailable while TC2 is disconnected/invalid or its cutoff is disabled.** The live UI says so. Do not mistake a missing TC2 for a protected barrier experiment.

Runtime protections are separate from START acceptance: invalid/nonpositive TC1, stale TC1 acquisition (1500ms), lost host heartbeat (2500ms), or TC1 ≥`tc1_cutoff_C` (initially 320°C) command heat OFF. A START with no usable TC1 is accepted, but the runtime feedback interlock will keep/cut heat OFF. A high valid/enabled TC2 reading is handled before a TC1 fault. No sensor, temperature, three-good-samples, IDLE-state or physical-reset preflight gate has been reintroduced.

## Wiring

| Device | Arduino connections | Role |
|---|---|---|
| TC1 amplifier | CLK/DO/CS **22/24/26** | Heater-side feedback |
| TC2 amplifier | CLK/DO/CS **28/30/32** | Optional opposite-barrier measurement / 140°C runtime trip |
| Relay module | **+ → 5V, − → GND, S → D33** | Requested active-HIGH, COM–NC profile |

Documented Adafruit MAX31855 amplifier VIN → 5V, GND → GND; probe leads go to its marked +/− terminals. Identify channels by amplifier wiring, not probe appearance. Unplug USB and all supplies before wiring. No relay contact/mains conductor connects to Arduino GND. Protective earth is not a heater return.

For the requested **COM–NC** power contacts, **D33 HIGH energizes the coil and commands heater OFF; LOW commands heat ON**. Verify actual module polarity/contact wiring with heater power disconnected. The displayed ON/OFF is a command, not independently measured contact position or current.

**NC fails ON when Arduino/coil power disappears or resets.** Software cannot prevent that interval. Keep an independent high-limit disconnect and manual disconnect; COM–NO with its matching output profile is the recommended fail-off physical arrangement. Do not change contact wiring without changing/validating the output profile. A variac normally provides no mains isolation; keep mains terminals enclosed/dry and the heater sheath correctly earthed.

## Control settings and voltage

Keep the initial preset at **30V RMS measured at the heater**. The catalog 300W/120V heater has nominal `R=120²/300=48 ohm`, so nominal ON power is `30²/48=18.75W` and current `30/48=0.625A`. Actual input must be measured; no claim this power reaches 300°C in wet sand. Runnable calculations/sources: `models/relay-sand/calculate.py`, `inputs.json`.

Provisional predictive hysteresis, not fitted PID:

- ON at `TC1 <= target_C - hysteresis_C` after `min_off_s`, provided the prediction is below target.
- OFF immediately when `TC1 + max(recent_TC1_slope,0)*prediction_lead_s >= target_C`; safety OFF is also immediate.
- The slope uses actual elapsed sample time over a trailing approximately 5s window. ON pulses may be shorter than the OFF dwell. Avoid fast mechanical-relay cycling.
- With `hold_s > 0`, complete after that many continuous seconds inside `target_C ± hold_band_C`. Leaving the band resets the timer. `hold_s = 0` disables timed completion. Explicit START always begins a new hold timer.

These are indicated-temperature control settings, not calibrated surface-temperature guarantees. No actual packed-sand hold or relay polarity has been validated. TC2 can continue warming after power is cut because stored heat remains. Do not raise voltage automatically to compensate for wet sand/drying.

## Reset detection

The Arduino does not detect its reset button as an experiment event. Reset restarts the program, initializes its RAM state and emits the CSV startup header/controller boot report with uptime near zero. The hub uses that header and uptime regressions to separate acquisition epochs. **Reset is no longer needed to re-arm EXP2.** Keep heater power disconnected before any reset/upload because of the NC wiring.

## Firmware / checks

Deployed protocol is **`exp2-v5`**, a clean host/firmware cutover. It adds `program`, `phase`, `setpoint_C` and `slope_C_per_s`; `tc2_required` is true for EXP4 and false for the single-target EXP2/3 program. The nested settings retain the existing ten fields. CSV stays `time_s,t1_C,t2_C` in raw physical order. EXP4 uses `EXP4 START` with the existing settings payload and `EXP4 NEXT <id>`; universal `EXP2 STOP` and `EXP2 PING` remain. Exact-ID acknowledgements and board-owned runtime control remain. Host and firmware were replaced together after the operator confirmed physically unplugged heater power; subsequent physical run026 is archived with its measured results and operator assessment.

```sh
arduino-cli compile --fqbn arduino:avr:megaADK firmware/thermocouple_logger
# Stop the serial reader and physically unplug the variac before upload:
arduino-cli upload --fqbn arduino:avr:megaADK --port /dev/ttyACM0 firmware/thermocouple_logger
nix-shell -p gcc --run \
  'c++ -std=c++17 -Wall -Wextra -pedantic tests/exp2_controller_test.cpp -o /tmp/exp2-controller-test && /tmp/exp2-controller-test'
nix-shell -p 'python3.withPackages (p: [p.aiohttp p.pyserial p.plotly])' \
  --run 'python -m unittest discover -s tests -p "test_*.py"'
```

Earlier v2 verification (before editable settings): the user confirmed the variac physically unplugged before upload. Mega ADK compile/upload succeeded (13,384 bytes flash / 1,047 bytes static RAM). Native and Python regressions passed, and the user's real TC1-only RUNNING session was observed without interrupting it. No powered cartridge hold or electrical-installation validation was claimed.

### Editable-settings verification

- Created `experiment.toml` in the repository and opened the whole project plus that file in Zed. Did not rewrite the operator's file after opening it.
- Mega ADK v3 compile/upload succeeded: **14,910 bytes flash, 988 bytes static RAM**. Deployment was performed while the real controller reported STOPPED/commanded OFF; no active experiment was interrupted. The variac was left unplugged as previously confirmed.
- Native controller regressions passed for atomic payload parsing, changed target/hysteresis/prediction/OFF dwell/cutoffs/hold settings, disabled TC2, untimed hold, invalid-candidate rejection and retained runtime/re-arm behavior. Python acquisition/config safety regressions passed.
- Exercised the actual sketch and actual hub through an isolated PTY. Changing a fixture file from target 60°C to 100°C left the first active configuration at 60°C until the next START; the next START applied 100°C without a board reset and saved a different run folder/source snapshot. Configured TC2 cutoff 42°C and TC1 cutoff 120°C tripped at those readings. Disabling TC2 bypassed only that cutoff. NaN configuration left the current run, request ID and applied settings unchanged.
- Visually checked actual UI settings/disabled-cutoff display at 1366×768. On the real board, observed `exp2-v3` IDLE/commanded OFF with all nine reported settings, and exercised the `config` command against the operator's actual file without arming a new experiment. Left the configurable client running at http://127.0.0.1:8765.
- These are firmware/configuration checks, not a powered cartridge hold, sensor calibration, relay-contact measurement or approval of the NC mains installation.

### EXP3 verification, 2026-11-06

- Native control regressions passed for swapped heater/rear input behavior, malformed swap rejection, mapping changes, cached-sample/slope reseeding and stale acquisition preservation.
- Seven Python host regressions passed, including swap acknowledgement mismatch shutdown, raw CSV preservation and saved/history mapping after restart.
- Prepared Mega ADK image compiled to **15,400 bytes flash / 993 bytes static RAM** in `/tmp/che126-exp3-build`. It was **not uploaded**.
- Executed actual sketch and host through an isolated PTY using synthetic probes and copied config. Raw channel 2 at 85°C did not trigger the rear cutoff; raw channel 1 at 85°C did. Raw channel 2 at 320°C triggered the heater limit; missing raw channel 2 triggered feedback shutdown. Saved CSV retained raw order and run metadata recorded EXP3/swap/65V.
- In the actual browser command interface against that isolated runtime, `config` showed both profiles, `start exp3` armed the mapped controller, raw heater 300°C switched OFF into HOLD, and `stop exp3` retained cooldown logging. The 65V metadata and mapped raw-source labels were visually checked.
- Visually checked the live split plots and historical 016/017 mapping without a live control command. Real run 017 continued recording on v3 throughout. Synthetic services/scaffolding were removed after proof; the staged Mega build remains for deferred deployment. No physical 65V control tuning or 300°C hold was validated.

### EXP4 software verification, 2026-11-06

- Native controller regressions passed: atomic envelopes, early/duplicate NEXT, phase transitions, 90s reference and actual-crossing gate, predictive capture, boost OFF dwell, in-band hold accounting, required-rear/overtemperature/STOP/staleness interlocks, mapping and wrapping timestamps.
- Fifteen host behavior regressions passed, including envelope rejection before run mutation, program acknowledgement, NEXT timeout/mismatch STOP, raw-data preservation and retained recording. Removed a brittle log-capitalization test rather than pinning incidental message wording.
- Mega ADK build passed: **18,450 bytes flash / 1,135 bytes static RAM**. Image staged under `/tmp/che126-exp4-build`, **not uploaded**.
- Actual sketch executed natively with synthetic thermocouples and an isolated PTY to the actual host on port 8767. Advanced simulated board time in 500ms steps with synthetic heartbeats. Demonstrated 100°C hold, explicit NEXT, ~150°C reference halfway, reference 200°C without false phase advance, measured-200 boost, predictive capture and final hold, rear85 trip, required-rear NaN trip, heater730 trip and STOP retaining recording.
- Actual browser against that isolated runtime verified `start exp4`, `next`, moving-setpoint/phase/slope labels and `stop exp4`. The offline report showed the staged program and saved phases. No real thermal-ramp accuracy, relay-contact state, physical 700°C operation or assembly suitability was validated.

