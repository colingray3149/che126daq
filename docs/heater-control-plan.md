# Heater warm-up and a minimal control-identification plan

**2026-11-02 update:** [Relay/sand control design](relay-sand-control.md) analyzes the now-available heated run 006, recovers the design PDF's draft 500°C ±10°C / 30-minute criterion, and covers the newly reported Songle relay. This older plan's “no valid heated data” status was historical; run 006 now contains finite heated readings plus substantial faults, but still lacks measured input and power-off history. No hardware control has been deployed.

## Current answer to “100 V → 500°C: how long?”

There is not yet a defensible single time for this apparatus. The heater rating determines nominal electrical power, not the heater/fixture heat capacity or losses. The executed calculation and clearly labeled sensitivity examples are in [heater-timing/results.md](../models/heater-timing/results.md). No hypothetical capacity or loss parameter is presented as measured heater data.

The requested temperature must also be defined: heater-element temperature, sheath temperature, hot mica-face temperature and the nearby wire-held probe reading are not interchangeable. For the initial empirical controller, use the **hot-location thermocouple reading** as the process variable, with its exact attachment documented. That does not guarantee the internal element or an unmeasured hot spot is equally cool.

## Before a heated identification run

- Obtain valid, checked hot and cold readings. The last hub commissioning data contained faults on both channels; that is not usable identification data. Complete the basic reference/channel checks first.
- Use the approved heater installation and electrical protection discussed in [experiment-log.md](experiment-log.md#practical-stop-points-before-heating), dry protected connections, and no real battery for these initial checks. The current cartridge leaned against a sheet is not the close-fitting metal-hole mounting described by its product page.
- If the probes are Adafruit #3245, their listed upper temperature is 500°C. Do not select that upper limit as a control setpoint with no margin for local hot spots, lag or overshoot. A 500°C program needs an identified electrically compatible probe and full assembly rated with appropriate margin. Do not remove protective earth to avoid MAX31855 faults.
- Identify the variac. An ordinary hand-operated variac has no software actuator. These runs can identify a **manual boost/hold recipe now**; automatic voltage control requires an actual suitably rated, safely integrated actuator/power controller later. No heater-control output has been added to the DAQ hub.

## Best three runs: two identification runs, one independent hold

Keep the specimen, support/contact, probe positions, clamps, and sand condition the same throughout this identification set. Record the actual condition, not “floating” if it leans against a block. If current tests are air-supported, these identify that configuration only. The final packed fixture needs a near-operating-point recheck/re-identification; gains and boost times do not automatically transfer.

| Run | What to do, once cleared for heating | Information to extract |
|---|---|---|
| **1 — Step and coast** | Record a no-power baseline. Apply one modest, approved constant power step, with the actual RMS voltage/current or real watts recorded. Hold long enough to see a clear curve and, if attainable within the approved range, a near-plateau. Switch power off and keep recording through the initial coast and cooldown. Do not insist on reaching 500°C or keep heating just to finish a model fit. | Direction/channel sanity; initial ramp; apparent input-to-temperature delay; approximate gain and time constant if a plateau is identifiable; how much the measured temperature continues to rise after power is cut. A short rising segment alone cannot identify steady-state gain reliably. |
| **2 — Identify near the intended operating band** | At a reviewed target below the verified equipment limits, record a small up-step and down-step in measured input around a candidate hold condition. Start from a stable enough condition that each step is interpretable. Find the input that roughly balances losses there; record every adjustment. Keep logging when you reduce/cut input. | Local hold power, local response speed and delay, heating/cooling asymmetry, and the lead needed to leave the boost phase before the requested temperature. Fit the local model here rather than extrapolating the low-temperature ramp to 500°C. |
| **3 — Validate, do not refit away the result** | From a comparable documented start, try the proposed boost → early reduction → hold recipe, manually with the variac if that is the available actuator. Once the approved target band is reached, assess the planned **30-minute hold**. Preserve the initial recipe and all interventions. No intentional unsafe disturbances are needed. | Peak overshoot, time to enter the chosen band, time in band, drift during the hold, and how much manual intervention was actually needed. If it fails or needs new settings, record that and call the revised recipe unvalidated until retested. |

**Only two runs available?** Combine Runs 1 and 2 into one recorded staircase with distinct modest and near-operating-band sections, a small return/down-step and cooldown. Use the second run for the independent hold check. Do not spend both runs collecting uncontrolled climbs and leave the resulting recipe untested.

Set the target band/abort conditions with the lab's responsible person before a run. No arbitrary acceptance tolerance, voltage ceiling or warm-up duration is claimed here. A heating-rate or steady-state estimate from a failed/unsafe probe arrangement is not useful identification.

## Minimum data: input history matters as much as temperature

Keep the hub's raw `data.csv`/`events.csv` and its current sampling. The saved firmware's nominal sample period is 500 ms. Record probe/channel/location mapping, actual initial temperatures, fixture/sand condition, target, and all input changes in that run's `notes.md` comments.

For each input change, use `note` to timestamp the **observed** RMS voltage and current (or measured real watts), including an explicit power-off event. Record the same readings at each hold condition, because a constant dial position does not prove constant input power. A small `power.csv` using the same host UTC clock is preferable if measurements can be logged; a time-stamped handwritten/event record is enough to start. Do not invent unmeasured wattage values in the experimental dataset.

Example note format, with actual readings filled in at the time:

```text
note Input changed: measured load voltage ... V RMS; current ... A; real power ... W if measured; hot probe location unchanged
note Heater power physically OFF; continue recording cooldown
```

The ellipses describe the fields to record, not prefilled measurements or executable control commands. A hub note does **not** change heater power. Manual note timing also includes operator delay; keep that in mind when fitting dead time.

The first identification question is whether temperature and input timestamps line up. A temperature curve without input history cannot distinguish a thermal response from operator changes. Reconnects/board resets and fault gaps must remain visible; do not fit across them as if continuous good data existed.

## The simplest resulting scheme

### With the equipment currently described

A manual **boost/hold feedforward recipe** is the quickest useful result:

- Use an approved boost input while safely below the target; it is not automatically the requested 100 V.
- Reduce input **before** the target, using the measured coast/lag from the identification runs, not a guessed timer.
- Hold near the empirically observed balance power, trim by observation, and record each trim. The result is an operator-assisted/open-loop recipe, not automatic closed-loop control or a guaranteed 30-minute temperature tolerance.

A fixed “100 V for X minutes, then Y V” recipe should come from these data and should name the fixture and starting condition. It is not a universal heater recipe.

### After a real controllable power actuator exists

Start with **hold-power feedforward + slow PI**, no derivative term:

`P_cmd = clip(P_hold + Kc × error + (Kc/Ti) × integral(error dt), 0, P_allowed)`

Use anti-windup when clipped, a limited target ramp, and defined fail-off behavior for missing/stale temperature data. Independent thermal protection must not depend on the same PC/probe/controller. These are controller requirements, not implemented hardware in this project.

Work in watts if power is measured. If only measured RMS voltage is available, a local model versus voltage squared is preferable to treating voltage as proportional to heat. That still assumes approximately resistive behavior and is not a substitute for actual power measurement. Converting a watt command to voltage via `V = sqrt(R × P)` uses an actual calibrated/appropriate resistance model and an actuator capable of accepting that command; it does not make a manual variac programmable.

A first local empirical model is:

`tau × d(ΔT)/dt + ΔT = K × ΔP(t − theta)`

where K is local °C/W gain, tau is response time and theta is apparent delay, all **fitted from measured input/output**. Obtain K from an interpretable steady difference; tau and theta from the curve, or fit them jointly and check them against the other step/down-step. If the trace shows multiple time scales or ongoing drift, retain the model's mismatch instead of pretending a single time constant is exact.

A standard IMC PI starting relation is:

`Kc = tau / (K × (lambda + theta)); Ti = tau`

Choose a slow lambda appropriate to the observed delay/lag and validate the actual hold. No numeric gains, boost time or hold voltage have been calculated yet because no valid heated identification data are available. See [BYU/APMonitor FOPDT](https://apmonitor.com/pdc/index.php/Main/FirstOrderSystems) and [IMC PI / anti-windup](https://apmonitor.com/pdc/index.php/Main/ProportionalIntegralControl).

## Why this is better than a single 100 V climb

A single climb can show a ramp, but without a plateau or another input step it poorly separates thermal storage from losses. The off/down-step reveals coast and cooling. Near-target steps identify the local hold requirement and lag where the controller will actually operate. The independent hold run tests whether that model/recipe predicts a useful result instead of merely describing the data used to create it.

At elevated temperatures, radiation and contact losses can be strongly temperature dependent. Air-to-packed-sand changes, moisture evolution, clamp reseating or a changed stack can alter the effective plant. Treat a model from today's bare mica check as **preliminary**, not the final controller for every barrier.

## References

- [McMaster 4877K305](https://www.mcmaster.com/4877K305/) and the archived heater PDF, pp. 1–2: rating, geometry, installation and separate control requirement.
- [Adafruit #3245](https://www.adafruit.com/product/3245): possible probe's temperature and electrical-contact limits; actual identity remains unconfirmed.
- [Energy-balance formulation](https://apmonitor.com/pdc/index.php/Main/PhysicsBasedModels): storage/input/loss relationship.
- [FOPDT system identification](https://apmonitor.com/pdc/index.php/Main/FirstOrderSystems): local gain, response time and delay.
- [PI tuning and anti-reset windup](https://apmonitor.com/pdc/index.php/Main/ProportionalIntegralControl): feedforward/bias plus PI and IMC starting relations.
