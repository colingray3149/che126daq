# Relay + variac control for the sand-packed fixture

**Operating update:** the user subsequently selected **EXP2: TC1 = 300°C heater, TC2 ≥140°C latched trip, 30V preset and COM–NC relay wiring**. See [the implemented EXP2 operating guide](exp2.md). This document preserves the earlier research/design-target analysis; its “no control deployed” statements describe that earlier analysis, not the updated firmware's capabilities.

## Decision

Design target recovered from **ChE 126 Design.pdf p. 41: hot rod/barrier-interface reading 500°C ±10°C for 30 minutes**. The original clock starts on first reaching 500°C, and leaving 490–510°C invalidates the hold. This is a draft experiment criterion, not safety approval. An earlier undated section (p. 32) says 600°C; do not mix those protocols. The latest discussion independently requested a 30-minute hold. The old p. 36 recipe of 100 V boost / 55 V hold was a proposal, not measured identification.

Recommended architecture: **fixed, manually limited variac output + automatic heater switching, controller on the Mega, PC only logging**. A relay cannot adjust the variac voltage; it selects zero or the preset voltage. Use the measured hot-side location for feedback and the other TC as a separately logged experimental output, not a second variable forced to match the hot side. For final tight regulation, prefer a suitable AC zero-cross SSR with slow PI and an independent safety disconnect. The Songle can support a slow hysteresis trial if the actual packed plant tolerates its minimum dwell/temperature ripple; that feasibility is not established by the existing run.

**Do not run the 500°C program with the present evidence gaps.** Possible ordered Adafruit #3245 probes are only specified up to 500°C, leaving no margin even for the required 510°C band edge, and their grounded junctions are incompatible with the MAX31855 arrangement. Use identified, electrically compatible ungrounded probes rated above the target, foreseeable overshoot and independent-trip setting. The actual heater mounting, wet-sand exposure suitability, protective earth, variac, driver/module and independent cutoff remain unverified. No firmware was changed and no heater/serial device was operated for this analysis.

## What was found and read

- Private pushed repository: <https://github.com/colingray3149/che126daq>, branch `main`; GitHub reported last push 2026-10-30 17:51:54 UTC when checked. Local checkout: `/home/colin/Projects/che126daq`.
- `firmware/thermocouple_logger/thermocouple_logger.ino`: two MAX31855s, 500 ms nominal sampling, CSV at 115200; **logging only, no heater actuator**. `host/hub.py` / `host/web/` are the durable DAQ hub.
- Original downloaded design and materials have preserved copies under `references/design`, `references/orders`, `references/datasheets`; searchable versions under `references/text`. Originals remain in Downloads, including `school/` for the heater PDF.
- `models/thermal-stack/` graphs and `thermal_predictions.csv` are **synthetic**, not measurements. Earlier `mica-check` and `heater-timing` results are explicitly conditional calculations.
- Six local acquisition runs exist. Runs 001–004 have no finite TC readings. Run 005 is mostly commissioning/faults and near-room-temperature readings. **Run 006 is the heated mica-only trace** consistent with the user's description. Its notes still say zero samples/recording, but the actual CSV contains 819 samples; metadata is stale after disconnection. Raw data and metadata were not modified. Runs are Git-ignored: a pushed code repository is not a backup of these local measurements.

## Measured evidence, not a fitted heater model

Executed analysis: [calculate.py](../models/relay-sand/calculate.py), [inputs](../models/relay-sand/inputs.json), [results JSON](../models/relay-sand/results.json), [measured plot](../models/relay-sand/run006.png).

| Run 006 observation | TC1 | TC2 |
|---|---:|---:|
| Initial recorded reading, °C | 24.5 | 25.0 |
| Peak recorded reading, °C | 219.75 | 261.00 |
| Peak host elapsed time, s | 87.067 | 78.020 |
| Fastest approximately 10 s finite-window regression, °C/s | 3.251 | 5.294 |
| Fault samples / 819 | 60 | 59 |

The rate windows are 60.534–70.484 s (TC1) and 27.657–37.012 s (TC2). They require at least 9.3 s coverage and no internal finite-data gap longer than 1.3 s; they are descriptive slopes, **not fitted plant gains**. The largest simultaneous difference is 91°C at 61.137 s: TC1 167.75°C, TC2 258.75°C. Never subtract the two different-time peaks to claim a barrier temperature drop. Both channels fault together in 59 rows (7.204%); at least one faults in 60 rows.

TC2 is hotter during heating, but no saved annotation establishes which physical face it occupied. Verify channel identity physically; do not silently call TC1 the hot side. The 9.047 s peak separation is **not** an identified power-off coast or dead time. Neither load voltage/watts nor power-off time was logged. Abrupt later cooling changes could involve contact/boundary changes; their cause cannot be recovered from temperature alone.

A thin insulator slows heat flux; it does not fix the rear face at ambient. Catalog mica thickness 0.032 in = 0.8128 mm, k = 0.3 W/(m·K). Fourier's ideal plane-wall resistance is `R = thickness/(k*area)`. For the whole 2×6 in sheet, R = 0.350 K/W; for the heater diameter×heated-length projection, R = 5.375 K/W. Neither projection is the measured contact area. Unknown contact/spreading resistance, wire bridges, edge losses and sand bypass paths prevent extracting mica conductivity from the two traces. The observed rear heating is entirely compatible with finite barrier resistance and thermal soak; the trace does not establish that mica has no thermal effect.

## Semi-wet sand: explicit approximations

[Smits et al. (2009), pp. 4 and 6](https://api.mountainscholar.org/server/api/core/bitstreams/734815a7-9c1c-4679-ae98-1c491ae33d74/content) measured room-temperature sand conductivities about **0.24–0.30 W/(m·K) dry** and **2.5–2.9 saturated**, depending on packing. Those are not measured QUIKRETE values or a 500°C property table. [Ochsner, Eq. 13-2/Table 13-1](https://open.library.okstate.edu/rainorshine/chapter/13-2-soil-thermal-properties/) provides the mixture heat-capacity relation and constituent values used here.

Two physical changes matter: moisture initially increases heat transport/storage, and evaporating water consumes energy; after local drying that sink decreases and effective conductivity changes. An open atmospheric sand pack cannot remain liquid-wet at 500°C next to the heater. A dry inner zone / wet outer zone and moving evaporation front form. Do not seal or confine steam. The cold face can also heat via sand around the barrier, not just through the mica.

To expose sensitivity, not forecast the apparatus, use a homogeneous constant-k annulus:

`Q_radial = 2*pi*k*L*(T_hot - T_outer)/ln(r_outer/r_heater)`.

Assume r_heater = 6.35 mm, L = 63.5 mm envelope, r_outer = 50 mm held at 25°C, T_hot = 500°C. These are selected simplifications; actual axial spreading, sleeve/backer, ends, supports, radiation, moisture transport and changing outer temperature are omitted. The code also varies length and outer radius.

| Assumed effective k, W/(m·K) | Radial-only W | Continuous equivalent RMS V, using 48 Ω |
|---|---:|---:|
| 0.25 | 22.96 | 33.20 |
| 0.60 | 55.10 | 51.43 |
| 1.50 | 137.76 | 81.32 |
| 2.50 | 229.60 | 104.98 |

The high-k rows are **counterfactual homogeneous-wet sensitivities at 500°C**, not physically sustained wet-sand predictions or approved voltages. They demonstrate why a single exact hold voltage cannot be selected from 'semi-wet'. They are not bounds on actual power, which can be outside the table.

For an assumed dry bulk density 1600 kg/m³, solid cp 750 J/(kg·K), water cp 4180 J/(kg·K), `Cv = rho_dry*cp_solid + theta*rho_water*cp_water`. At theta = 0.05, Cv ≈ 1.409 MJ/(m³·K); with assumed k = 0.6, `sqrt((k/Cv)*1800)` ≈ 27.7 mm. This is a conduction length scale, not a sharp heated boundary. It motivates treating the surrounding centimetres and changing outer temperature as relevant rather than lumping the whole cinderblock at one temperature. Room-temperature cp/k constants are not high-temperature material validation.

Water alone, initially 25°C and escaping as saturated steam around 100°C/1 atm, needs `E = m*(4180*(100-25) + 2257000)` J. [Steam-table source](http://wpage.unina.it/petrilli/gasvapor/steam.htm?html). Assumed 10 g local water consumes 25.705 kJ, equivalent to 14.28 W averaged over 1800 s; 50 g consumes 128.525 kJ, equivalent to 71.40 W. The actual evaporated mass and timing are unknown; these are not additive guaranteed constant losses, and water sensible heat must not also be counted twice in a transient mixture-capacity calculation. This is why fixed boost timers and fixed duty fractions are weak choices for a drying fixture.

## Variac setting: a limit on ON power, not a temperature knob

[Heater 4877K305](https://www.mcmaster.com/4877K305/): 300 W at 120 VAC. Nominal `R = 120²/300 = 48 Ω`, `P_on = V_RMS²/48`, `P_average ≈ duty*P_on`. Actual hot resistance and real load power must be measured.

| Measured load RMS voltage | Nominal ON power | Nominal ON current |
|---|---:|---:|
| 30 V | 18.75 W | 0.625 A |
| 40 V | 33.33 W | 0.833 A |
| 55 V | 63.02 W | 1.146 A |
| 60 V | 75.00 W | 1.250 A |
| 100 V | 208.33 W | 2.083 A |
| 120 V | 300.00 W | 2.500 A |

**Current unreviewed assembly: leave the heater de-energized.** After electrical/mounting/probe clearance, my engineering choice for the **first short, supervised, cold packed-fixture identification step is 30 V RMS measured across the connected heater**, not 100/120 V. It limits nominal ON power to 1/16 of rated power. It is not a safe-to-touch voltage or a claim the apparatus reaches 500°C. If the earlier 'full voltage' was actually 120 V and response scaled only with input, 5.294°C/s would scale to 0.331°C/s at 30 V. This is only a power-ratio illustration, not a sand heating-rate prediction or overshoot bound.

For the later operating voltage, select the **lowest approved voltage that supplies measured near-target loss power plus control authority**. A useful design target is nominal hold duty 0.5–0.8, leaving power authority in both directions; that range is a design preference, not measured tuning. `V_on = sqrt(48*P_hold/duty_hold)` in the nominal-resistance approximation. A 60 V / 75 W ceiling is a candidate only if packed-fixture measurements show it can reach/hold the target with headroom. Some sensitivity cases require more than 75 W; others need much less. Do not automatically raise voltage just because wet sand causes a plateau. The old 55 V recipe has no special evidential status.

## Exact low-voltage wiring — bare relay case

[Arduino's Mega ADK documentation](https://docs.arduino.cc/retired/boards/arduino-mega-adk-rev3/) and the preserved [vendor source](../references/hardware/mega-adk-vendor-documentation.md) specify 5 V GPIO; **D7 is reserved for MAX3421E USB-host reset**. Use **D33** for heater enable. Existing TC1 CLK/DO/CS stays **22/24/26**; TC2 stays **28/30/32**. Do not repurpose D7, serial 0/1 or the host SPI pins.

[Songle SRD datasheet, pp. 1–2](https://www.jotrin.jp/userfiles/downloadfile/SRD_05VDC_SL_C/SRD_05VDC_SL_C_DATASHEET.pdf): the **L** coil is approximately 0.36 W, 70 Ω ±10%, nominal 71.4 mA at 5 V. This exceeds the ADK's documented 40 mA GPIO maximum; **never connect the coil directly to D33**. That 40 mA is a maximum, not an operating target.

Additional parts required if this is only the blue five-pin relay: **onsemi P2N2222A**, **330 Ω** base resistor, **10 kΩ** base-emitter pulldown and **1N4007** flyback diode. Do not assume other '2222' transistors have the same lead order. The specific [onsemi datasheet](https://www.onsemi.com/pdf/datasheet/p2n2222a-d.pdf), pp. 1 and 6–7, identifies pin 1 collector, 2 base, 3 emitter; follow its package-view drawing, not a generic flat-face rule.

| Connection | Destination |
|---|---|
| Mega D33 | 330 Ω resistor → transistor base B |
| Transistor emitter E | Mega GND |
| Transistor collector C | Relay coil low side |
| Relay other coil terminal | Regulated +5 V coil supply |
| 10 kΩ resistor | Transistor base B → emitter E/GND |
| 1N4007 striped end (cathode) | Coil +5 V terminal |
| 1N4007 unstriped end (anode) | Coil collector terminal |
| Coil-supply negative | Mega GND |

Use a regulated, isolated 5 V coil supply with adequate documented current, or the Mega's 5 V rail only after verifying the complete USB/board/amplifier budget and noise behavior. If an external coil supply is used, share **its negative** with Mega GND for this transistor topology; **do not tie its positive to the Mega 5 V rail**. Do not feed 5 V into VIN and do not parallel two 5 V supplies. Keep coil wiring short; place the diode at the coil. Hardware pulldown makes reset/unpowered GPIO tend toward relay OFF. Firmware must preload LOW before setting D33 OUTPUT and require deliberate arming after reset. HIGH energizes this **bare-relay NPN circuit**.

The calculation checks a conservative 4.2 V GPIO HIGH, 1.2 V VBE, coil resistance at -10% tolerance and forced beta 10. With 330 Ω and 10 kΩ pulldown it yields about 8.97 mA base drive versus 7.94 mA required for the 79.37 mA worst-resistance coil example. Supply variation/actual hardware still need checking.

### Identifying the five relay pins

The manufacturer's physical pin drawing was rendered and visually inspected, not inferred from a hobby blog. In the **pin-side/bottom view**, orient the three-pin column to the left and two-pin column to the right. The two outer left pins are the coil; the middle left pin is COM. In that orientation the upper right is NO and lower right is NC, matching the datasheet's drawn unenergized contact. The bare coil has no polarity until you add the external diode. **Verify against your actual part**: with everything unplugged, the coil pair measures about 70 Ω; COM–NC has continuity unpowered; COM–NO is open and closes when the coil is powered from an isolated 5 V bench source. Never use mains to identify pins. A module's screw-terminal order is not this physical relay-pin order.

### If this is a relay module, not a bare component

`SRD-05VDC-SL-C` on the blue cube does **not** identify the module PCB. A documented 5 V module may already have driver/diode and expose VCC/GND/IN plus COM/NO/NC; then use its own input circuit, not an extra transistor blindly. **D33 → IN is conditional on verified 5 V logic compatibility and polarity; VCC/JD-VCC/GND wiring depends on its exact module schematic.** Active-LOW modules require a different reset-safe bias. An optocoupler alone does not establish safe mains creepage or system isolation. Exact module wiring is unreachable from the relay model alone: a clear module front/back photo or PCB model is the missing prerequisite, not an Arduino documentation question.

## AC-side topology — lab-qualified assembly required

This is a functional net description, **not permission to assemble exposed mains wiring**. The actual variac model/terminal labels, fuse arrangements, cord polarity, enclosure and protection must be checked by the lab's responsible electrical person. A bare Songle is a PCB component; mains does not belong on a solderless breadboard, Dupont wires or exposed relay legs.

- Approved supply/disconnect and ground-fault protection → correctly fused variac input.
- Identified **variac output live → appropriately coordinated output overcurrent protection → independent high-limit safety disconnect → relay COM; relay NO → one heater lead**. Relay NC remains unused and insulated.
- Other heater lead → identified variac output return/neutral according to that model's documentation. Do not invent screw numbers or wire colors for an unidentified variac.
- Protective earth → variac chassis and heater sheath/accessibly conductive fixture as required. PE is continuous, never routed through the Songle contacts. Arduino GND is a logic reference, not a replacement for PE, and never connects to a mains conductor or relay contact.

Switch **downstream of the variac**, so the relay switches the resistive heater, not transformer magnetizing inrush. With NO, loss of coil power normally removes heater power, but contacts can weld closed. The independent high-limit device must have its own appropriate sensor/disconnect path and remain capable of opening the power path after a welded control relay, failed-short SSR or hung Mega. Its trip threshold must be selected against the actual probe/fixture/lead ratings and verified overshoot; no defensible numeric trip threshold is established here.

An ordinary variac is a **nonisolating autotransformer**; 30 V across its output is not proof of low conductor-to-earth voltage. Zero on the dial and an OFF relay are not safe isolation; unplug/lock out for wiring. See [Elliott Sound Products' operating-principle and safety explanation](https://www.sound-au.com/articles/variac.htm) and verify the actual unit manual. [Staco's manufacturer FAQ](https://www.stacoenergy.com/support/product-faq.html) illustrates why terminal assignments must be model/mounting specific. Keep relay/electronics and terminations away from heat, moisture and steam. The cartridge page specifies close-fit drilled/reamed metal-hole installation and separate temperature control, not immersion or a loose sand mounting. Its 1400°F sheath exposure rating does not override the lead's 840°F rating or certify a locally overheated internal element. The preserved Tempco moisture note emphasizes insulation-resistance checks and protective earth; these are qualified electrical checks, not an instruction to apply a megohmmeter to connected Arduino electronics.

## Control scheme and commissioning criteria

### Existing Songle: slow, bounded hysteresis

Use explicit states **OFF → ARMED → RAMP → HOLD → COMPLETE**, with a latched **FAULT** reachable from every powered state. Control and high-priority interlocks run on the Mega, not through browser/PC commands. Keep the existing two-channel DAQ mapping; this document is a design, not implemented firmware.

1. Verify hot/cold identity with a modest nonhazardous differential before control; configure the hot channel explicitly. Check reference/co-location accuracy, physical attachment, valid MAX31855 operation and junction isolation. A finite number alone is not proof of a correctly mounted sensor.
2. In the final packed geometry, measure low-power ON/OFF response, maximum upward coast after OFF and near-target on/off slopes. Timestamp actual voltage/current/power changes. The existing peak separation is not a substitute. Repeat after changing moisture, packing, sleeve or barrier.
3. Limit the setpoint ramp and ON power from the measured response. A reasonable **candidate** hysteresis is ON below **497°C**, OFF above **503°C**, keeping a nominal 7°C guard to the draft ±10°C boundary. This is an analyst-selected starting band, not validated tuning or absolute accuracy. Cut earlier if measured coast would consume that margin: `T_pred = T_hot + coast_allowance(current slope, temperature, packed condition)`; use measured worst-case coast, not an invented delay constant.
4. Candidate ordinary dwell is **5 s ON / 5 s OFF minimum**, but any fault/high-limit or forecast overshoot overrides ON dwell immediately. Enforce OFF dwell before re-energizing. Even with arbitrarily early OFF, a 5 s OFF dwell limits normal repeated cycles to less than 24 contact transitions/min. With both 5 s dwells, a 10 s full cycle means 180 cycles / 360 transitions over 30 minutes. The Songle sheet lists 30 electrical operations/min and finite contact life; this is **not** an argument for Arduino PWM. Switch further down in frequency if the measured plant allows it.
5. Feasibility check: the measured minimum useful ON pulse plus coast and OFF cooling must fit inside the allowed band with sensing uncertainty/margin. `deltaT_pulse ≈ P_on*t_on/C_eff` is an energy sensitivity only. For an **assumed**, not fitted, C_eff = 50 J/K and 5 s pulse: 30 V gives 1.875°C; 60 V gives 7.5°C; 120 V gives 30°C before losses/lag. Full-voltage pulses are a poor starting point. If the measured dwell/ripple/coast cannot meet the band, do not widen the experiment's acceptance criterion or chatter the relay: use an appropriate SSR and/or a reviewed spreader/sleeve geometry and re-identify.
6. Start the official 1800 s clock at the first actual 500°C crossing, only after stable approach has been demonstrated. Once started, mark the run invalid and cut power if the hot reading leaves 490–510°C or either sensor fails/detaches; do not silently pause/restart the clock to manufacture a valid 30 minutes. At 1800 s, power OFF, latch COMPLETE, and continue both-channel logging through the cold-side peak/cooldown.

Any MAX31855 fault/nonfinite sample, stale acquisition, reset, sensor detachment, independent over-temperature event or manual stop must de-energize the output and latch a fault until a human resolves it/re-arms. A freshness deadline should be based on the 500 ms acquisition period and validated timing margin; no long hold-last-good behavior is acceptable with the observed fault history. Check high limits on unsmoothed valid readings; filtering for regulation must not hide a safety excursion. Two experimental TCs on one Mega are not independent safety protection. A cold-side cutoff needs the actual receiving object and a reviewed limit; the PDF's bracketed [100°C] is not a selected cell safety limit. Initial identification uses an inert receiver, not a live lithium cell.

### Recommended tight-hold actuator: AC zero-cross SSR + PI

Select a genuine SSR with load-voltage range including the actual reduced variac output, sufficient current/thermal derating and heatsink, low-load compatibility and documented DC input interface. Do not assume a '240 VAC' device operates at every low variac voltage. An AC TRIAC/SCR SSR is not a DC switch; leakage means OFF is not isolation, and fail-short behavior requires the separate safety disconnect. The Songle may be retained for deliberate enable/disable if its installation is properly rated, but is not the sole safety device.

[OMRON's manufacturer safety guidance](https://www.ia.omron.com/product/cautions/18/safety_precautions.html) explicitly identifies short-circuit failure as the main SSR failure mode and calls for a separate contactor/breaker path; its heater-load section supports zero-cross switching to reduce switching noise. Those requirements, not an assumed infallible SSR, motivate the recommended architecture.

For a local identified FOPDT plant, `tau*dDeltaT/dt + DeltaT = K*DeltaP(t-theta)`, use `P_cmd = clip(P_hold + Kc*error + I, 0, P_on)`, conditional integration/anti-windup, `dI/dt = (Kc/Ti)*error`. One documented starting relation is `Kc=tau/(K*(lambda+theta)), Ti=tau`, with a deliberately slow lambda and validation against a separate hold. [PI/IMC reference](https://apmonitor.com/pdc/index.php/Main/ProportionalIntegralControl). Convert power to SSR time duty `D=P_cmd/P_on` with an appropriate line-synchronized burst scheme, not phase-angle control or fast PWM on the Songle. The available run does not identify K, tau, theta or P_hold; numeric gains would be fabricated. Validate the full 30-minute packed hold, particularly during drying, before material comparisons.

## Reproduce and verification

From the repository root, standard-library calculations:

```sh
python3 models/relay-sand/calculate.py
```

Regenerate the measured plot as well:

```sh
nix-shell -p 'python3.withPackages (p: [p.numpy p.matplotlib])' \
  --run 'python models/relay-sand/calculate.py --plot'
```

`--inputs PATH --run PATH --out DIRECTORY` allows independent checks without touching raw runs. Inputs label every scenario assumption and source. Outputs: electrical/mica/sand/capacity/evaporation/pulse/cycle/ramp-sensitivity CSVs and results JSON with input/script/raw-data SHA-256. The nominal 48 Ω, P=VI identities and conservative transistor base-drive inequality are asserted by the script. No thermal parameters or safety bounds are silently fitted. Missing actual input, power-off time, hold power and PI gains remain JSON null.

Executed the actual script against the 819-row raw run and visually inspected the generated plot with fault gaps intact. Rendered/inspected the Songle manufacturer pin diagram and coil/contact ratings. No sensor readings were reacquired, no firmware uploaded, no relay/variac energized, and no physical 500°C hold or electrical-installation validation was performed.
