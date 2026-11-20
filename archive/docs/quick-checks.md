# Quick checks worth doing

**Status: suggestions, not completed experiments.** The aim is to learn what this two-channel fixture can support with modest effort. Start with measurement sanity and repeatability. A catalog-conductivity match is interesting, but should not be the sole pass/fail criterion.

Current arrangement and decisions: [experiment-log.md](experiment-log.md). Source limits: [current-check-sources.md](current-check-sources.md). Executed arithmetic/plots: [mica-check/results.md](../models/mica-check/results.md).

## First: get believable channels without the heater

| Priority | Suggested check | Keep fixed / record | What it tells us | What it cannot establish |
|---|---|---|---|---|
| First | Put both tips together in the same well-stirred water bath with the reference thermometer. Keep tips away from container walls and one another; keep connectors/boards dry. | Probe IDs, channel mapping, reference reading/identity, immersion and settling behavior. Repeat at ambient and a comfortably warm reference condition. | Observed channel mismatch, obvious sign/polarity errors, noise, settling, disagreement with the reference. | Full-range calibration; accuracy beyond the reference; performance of a surface-mounted tip on a heater. |
| First | Record a quiet, no-heater baseline with tips beside one another. | Ambient conditions; actual saved samples, timestamps and fault counts. | Baseline scatter, differential offset, logging continuity and whether apparent changes exceed observed short-term noise. | A complete systematic-error budget. |
| First | With everything de-energized, check actual probe identity and whether tips/wire make unintended electrical contact with heater sheath or each other. | Photos and probe SKU; have the responsible lab person verify the heater/protective-earth arrangement. | Whether the grounded-tip/MAX31855 issue is relevant to this setup. | Electrical safety certification or permission to remove protective earth. |
| Useful | After shutting off power, disconnect one TC, restore acquisition, and confirm only the intended channel reports an open-probe fault. Reconnect with power off. | Label probe A/B separately from DAQ channel 1/2. | Channel assignment and actual fault visibility. | Accuracy of finite readings. A zero-only stream is not a substitute for this check. |

A reference check gives an **observed difference**, not a declaration that the reference is exact. Save the reference reading in the run comments. Do not “correct” one channel from one sample and then count that same sample as independent validation.

## Then: short mica-only trials after the installation is checked

The current cartridge-against-sheet arrangement is not the heater's documented close-fitting metal-hole installation. Resolve heat removal, grounded sheath/isolated sensing, dry protected terminations, accessible shutoff and separate over-temperature protection with the lab's responsible person before energizing. The calculations deliberately do not prescribe a safe voltage or sheath temperature for this uncharacterized mounting.

| Priority | Suggested check | Change just this | Useful comparison | Interpretation limit |
|---|---|---|---|---|
| Next | A modest, approved power step with the current mica-only fixture, followed by power-off cooldown. | Measured electrical input history. | Save both T(t), their difference, measured RMS V/I or real watts, onset/lag, and cooldown. Confirm the directly heated location responds plausibly. | No absolute temperature/lag is predictable from catalog k alone. A surface TC can miss the hottest heater point. |
| Next | Repeat the same assembly without disturbing the probes/clamps. | Run identity only, starting from comparable initial conditions. | Overlay curves; compare temperature rises from baseline, same-time differences, and final-window trends. | Repeatability is not accuracy. Repeated systematic bias can look excellent. |
| Next | Fully cool, disassemble/reseat, and repeat. | The handling/contact cycle. | Compare scatter with the untouched repeats. Photograph probe positions. | A larger difference implicates assembly sensitivity, not necessarily a changed material. |
| Useful | Swap the two probes between DAQ channels while preserving the physical positions; then separately exchange physical positions in another cooled/reassembled trial. | Electronic channel first; physical location separately. | Does the discrepancy follow the probe/channel or stay with the location? | A rushed swap that also changes contact/pressure mixes several explanations. |
| Useful | Keep one probe fixed and move the other across marked cold-face positions between cooled trials. | Sensing location. | A simple position sketch with measured temperatures shows whether a slightly off-center probe matters. | Two probes do not give a simultaneous temperature field; repeatable input/contact is needed. |

## Air-supported versus sand-packed — explicitly part of the experiment

Use the same mica specimen, probe positions, clamping and recorded electrical input history. Define the “air” case precisely: the reported first assembly still touches/leans on the cinderblock, so it is not thermally free-floating. For packed trials, log sand mass, fill depth, packing method, initial temperature and moisture preparation. Keep lead ends and live electrical parts out of the sand.

A practical order is **air → reproducible dry-packed sand → air again**, cooling and rebuilding to comparable starting conditions. The return-to-air run helps distinguish fixture changes from drift or damage. This order is a suggestion, not an already performed sequence.

Compare:

- Hot-location and cold-location temperature rise from each run's baseline, at matched elapsed times and measured power histories.
- Hot-minus-cold difference, lag, peak and cooldown behavior.
- Whether a late segment is still climbing, rather than calling a trace “steady” just because the clock ended.
- Within-condition repeat scatter versus the change between air and packed conditions.

This tells us **how sensitive the apparatus response is to support and surroundings**. It does not tell us which case has “the right mica conductivity.” Packing can change heater coupling, losses, effective area, contact and thermal storage simultaneously. The ambiguity plot in the executed calculations shows why a catalog-looking apparent k can arise from compensating assumptions.

**Today's semi-wet sand:** record it as semi-wet, not dry. If moisture is later studied deliberately, compare measured dry/wet preparation at fixed dry-sand mass and documented added water only after a safe fixture is established. Do not combine a poorly characterized moisture experiment with the first sensor-validation trial. The supplied sand PDS gives no thermal-conductivity or moisture value for this fill.

## Once the first checks are interpretable

- **Aluminum backer on/off:** useful because it tests the actual workholding choice. Keep pressure/contact and the definition of the measured cold-side surface as comparable as possible. A probe on aluminum instead of mica measures a different object; record that rather than calling the resulting difference “no material effect.”
- **Candidate layer stacks:** compare mica/basalt/aluminum now if available; add aerogel cases when it arrives. Measure the clamped stack thickness, not only nominal catalog thickness. Repeat and return to a familiar reference stack occasionally to catch drift.
- **One versus two mica sheets:** optional qualitative sensitivity check. A second sheet also adds an interface and changes geometry/contact; a non-doubling temperature difference does not by itself refute Fourier conduction.
- **Longer exposure:** only after the short trials are stable and the electrical/thermal arrangement is reviewed. The user’s eventual roughly 30-minute comparison is a goal, not evidence that every fixture reaches equilibrium by then. Keep recording after heater power is removed.
- **Real battery:** not needed to establish DAQ or baseline fixture behavior. Use an inert surrogate if a receiving thermal mass is needed. A later real-cell test needs its own justified limits and reviewed procedure; “cosmetic” does not make a cell inert.

## Minimum useful run note

Keep this short enough that it gets filled in:

```text
Question / comparison:
Stack and specimen ID:
Air / block contact / sand condition:
Probe A/B → channel → exact location:
Clamps / clip / wire and any changes:
Starting temperatures / reference reading:
Measured electrical input and changes:
Photo filename:
Anything odd (fault, slip, steam, meter change):
```

These fields can go below the hub run's blank comments area. Never replace the raw run CSV with smoothed curves; raw data and fault gaps should remain available.

## What we can honestly claim from two probes

With good positioning and records: measured local temperature traces, observed inter-channel mismatch/noise, relative lag, repeatability, and differences between controlled fixture configurations. With a known reference: limited checks of temperature agreement under those reference conditions.

Not from the two traces alone: net heat crossing the mica, full spatial temperature field, complete material conductivity, true heater-element peak temperature, full sensor uncertainty, or a safe battery-test envelope. More runs can reveal the limits of this setup without making the project needlessly elaborate.
