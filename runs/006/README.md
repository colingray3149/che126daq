# Run 006 — Supporting recording

[All runs](../README.md) · [Three actual tests](../README.md#the-three-actual-tests) · [Raw CSV](data.csv) · [Event log](events.csv) · [Run notes](notes.md) · [Interactive report](report.html)

**819 saved sample rows.** Full elapsed-time range; no smoothing, downsampling or voltage scaling. Each graph has its own temperature axis.

**Historical metadata warning:** original notes still say `recording`/0 samples; this archived CSV actually has819 rows. That header does not establish a live acquisition.

## TC1 — heater

Saved-source interpretation: **TC1 · HEATER (raw TC1)**. 759 finite readings out of 819 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 006 full-history TC1 — heater graph](heater.png)

## TC2 — rear

Saved-source interpretation: **TC2 · REAR (raw TC2)**. 760 finite readings out of 819 saved rows.

Missing/nonfinite readings remain gaps; they are not interpolated or replaced with zero.

![Run 006 full-history TC2 — rear graph](rear.png)

## Source and interactive viewing

The PNGs are1400×700 renders of the full-data Plotly traces in `report.html` and display directly on GitHub. Download/open the HTML locally for zoom, hover and export; GitHub does not execute its JavaScript. Regenerate HTML with `python host/report.py runs/006`; static PNGs are snapshots, not live views.

CSV SHA-256: `5c314843f42165eaca16269fc6bbcec54d6ac88b31e2103b1b7e134198bbaf82`.

Role labels follow saved/legacy mapping rules; consult the run notes for probe-placement corrections and validity limitations. Original CSV, event log, notes and settings are unchanged by rendering.
