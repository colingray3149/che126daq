# Run 015 — Supporting recording

[All runs](../README.md) · [Three actual tests](../README.md#the-three-actual-tests) · [Raw CSV](data.csv) · [Event log](events.csv) · [Run notes](notes.md) · [Interactive report](report.html)

**2,062 saved sample rows.** Full elapsed-time range; no smoothing, downsampling or voltage scaling. Each graph has its own temperature axis.

## TC1 — heater

Saved-source interpretation: **TC1 · HEATER (raw TC1)**. 2,020 finite readings out of 2,062 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 015 full-history TC1 — heater graph](heater.png)

## TC2 — rear

Saved-source interpretation: **TC2 · REAR (raw TC2)**. 1,782 finite readings out of 2,062 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 015 full-history TC2 — rear graph](rear.png)

## Source and interactive viewing

The PNGs are1400×700 renders of the full-data Plotly traces in `report.html` and display directly on GitHub. Download/open the HTML locally for zoom, hover and export; GitHub does not execute its JavaScript. Regenerate HTML with `python host/report.py runs/015`; static PNGs are snapshots, not live views.

CSV SHA-256: `f4b16691d2fc1af25ef446375c677914dce314161183c76c4fa82f41c7e933fe`.

Role labels follow saved/legacy mapping rules; consult the run notes for probe-placement corrections and validity limitations. Original CSV, event log, notes and settings are unchanged by rendering.
