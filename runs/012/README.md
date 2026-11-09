# Run 012 — Supporting recording

[All runs](../README.md) · [Three actual tests](../README.md#the-three-actual-tests) · [Raw CSV](data.csv) · [Event log](events.csv) · [Run notes](notes.md) · [Interactive report](report.html)

**2,400 saved sample rows.** Full elapsed-time range; no smoothing, downsampling or voltage scaling. Each graph has its own temperature axis.

## TC1 — heater

Saved-source interpretation: **TC1 · HEATER (raw TC1)**. 1,791 finite readings out of 2,400 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 012 full-history TC1 — heater graph](heater.png)

## TC2 — rear

Saved-source interpretation: **TC2 · REAR (raw TC2)**. 143 finite readings out of 2,400 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 012 full-history TC2 — rear graph](rear.png)

## Source and interactive viewing

The PNGs are1400×700 renders of the full-data Plotly traces in `report.html` and display directly on GitHub. Download/open the HTML locally for zoom, hover and export; GitHub does not execute its JavaScript. Regenerate HTML with `python host/report.py runs/012`; static PNGs are snapshots, not live views.

CSV SHA-256: `8dd35e6d788f18bbb6d0456cab0bbb8921c76059f7d1c96cc8fd4fd3871e7dd9`.

Role labels follow saved/legacy mapping rules; consult the run notes for probe-placement corrections and validity limitations. Original CSV, event log, notes and settings are unchanged by rendering.
