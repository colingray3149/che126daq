# Run 036 — EXP6 / actual test 5

[All runs](../README.md) · [Raw CSV](data.csv) · [Event log](events.csv) · [Run notes](notes.md) · [Run metadata](run-metadata.json) · [Selected settings](experiment.toml) · [Applied settings](experiment-applied.json) · [Interactive report](report.html)

**Barrier: 1 layer mica / 2 layers fiberglass heat barrier strip (McMaster 4234N12) / 1 thin aluminum sheet.**

EXP6 completed: NEXT from HEAT_100 at 18:02:44 UTC, heater first measured ≥700°C at 18:06:02 (249.2 s), peak 714.0°C, 60-second hold complete at 18:07:02 and heat OFF. Rear peaked at 80.25°C at 642.0 s, during cooldown; the 120°C rear cutoff was not reached. No sensor faults.

**1,882 saved sample rows.** Full elapsed-time range; no smoothing, downsampling or voltage scaling. Each graph has its own temperature axis.

## TC1 — heater

Saved-source interpretation: **TC1 · HEATER (raw TC2)**. 1,882 finite readings out of 1,882 saved rows.

![Run 036 full-history TC1 — heater graph](heater.png)

## TC2 — rear

Saved-source interpretation: **TC2 · REAR (raw TC1)**. 1,882 finite readings out of 1,882 saved rows.

![Run 036 full-history TC2 — rear graph](rear.png)
