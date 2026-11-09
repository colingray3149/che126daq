# Run 005 — Supporting recording

[All runs](../README.md) · [Three actual tests](../README.md#the-three-actual-tests) · [Raw CSV](data.csv) · [Event log](events.csv) · [Run notes](notes.md) · [Interactive report](report.html)

**3,028 saved sample rows.** Full elapsed-time range; no smoothing, downsampling or voltage scaling. Each graph has its own temperature axis.

## TC1 — heater

Saved-source interpretation: **TC1 · HEATER (raw TC1)**. 87 finite readings out of 3,028 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 005 full-history TC1 — heater graph](heater.png)

## TC2 — rear

Saved-source interpretation: **TC2 · REAR (raw TC2)**. 1,008 finite readings out of 3,028 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 005 full-history TC2 — rear graph](rear.png)

## Source and interactive viewing

The PNGs are1400×700 renders of the full-data Plotly traces in `report.html` and display directly on GitHub. Download/open the HTML locally for zoom, hover and export; GitHub does not execute its JavaScript. Regenerate HTML with `python host/report.py runs/005`; static PNGs are snapshots, not live views.

CSV SHA-256: `d07f850efa60a3641102c2acd6cfd4ea8c501ba7634fc1239427c85693ac10aa`.

Role labels follow saved/legacy mapping rules; consult the run notes for probe-placement corrections and validity limitations. Original CSV, event log, notes and settings are unchanged by rendering.
