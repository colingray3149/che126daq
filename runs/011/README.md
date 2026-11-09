# Run 011 — Supporting recording

[All runs](../README.md) · [Three actual tests](../README.md#the-three-actual-tests) · [Raw CSV](data.csv) · [Event log](events.csv) · [Run notes](notes.md) · [Interactive report](report.html)

**4,302 saved sample rows.** Full elapsed-time range; no smoothing, downsampling or voltage scaling. Each graph has its own temperature axis.

## TC1 — heater

Saved-source interpretation: **TC1 · HEATER (raw TC1)**. 4,302 finite readings out of 4,302 saved rows.

![Run 011 full-history TC1 — heater graph](heater.png)

## TC2 — rear

Saved-source interpretation: **TC2 · REAR (raw TC2)**. 0 finite readings out of 4,302 saved rows.

**No finite temperature readings were recorded for this channel.** The image intentionally has no trace; missing readings are not zero.

![Run 011 full-history TC2 — rear graph](rear.png)

## Source and interactive viewing

The PNGs are1400×700 renders of the full-data Plotly traces in `report.html` and display directly on GitHub. Download/open the HTML locally for zoom, hover and export; GitHub does not execute its JavaScript. Regenerate HTML with `python host/report.py runs/011`; static PNGs are snapshots, not live views.

CSV SHA-256: `b0f43080a7c8627a7d4ef5e1bc7517566a64dba86e3baa358421c3d302a2af44`.

Role labels follow saved/legacy mapping rules; consult the run notes for probe-placement corrections and validity limitations. Original CSV, event log, notes and settings are unchanged by rendering.
