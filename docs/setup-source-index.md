# Setup source index — 2026-10-30

## Evidence order, not an assumed experiment

1. Present user statements: Mega/amps available, **no thermocouples connected**, user will explain intended experiment later.
2. Current saved code and today's USB/serial observations establish software pins and detected hardware, not the physical fixture.
3. Order XLSX and product PDFs describe selected/listed items; an order line is not proof of delivery or assembly.
4. Design PDF and conversations preserve research, draft procedures, and past observations. Document position is not proof of revision order.
5. Thermal-model ZIP is a hypothetical ChatGPT scenario, not an approved test protocol or validated prediction.

## Useful source map

| Source | Useful section | Status / caveat |
|---|---|---|
| `references/design/ChE 126 Design.pdf` | 42 pages; searchable counterpart in `references/text/ChE 126 Design.txt` with PDF page markers | Newest relevant setup document found in Downloads; no relevant DOCX found there. Filename and modification time do not date individual revisions. |
| Design pp. 1–25 | Battery-fire application, requirements/literature, material comparisons | Background/research claims retained without independent validation. |
| Design pp. 26–27 | Explicit **10/12–10/16** label; shopping/material options, thicknesses, candidate stacks | Dated planning block, not current assembly evidence. |
| Design pp. 28–31 | Older procurement/material candidates | Includes UNO R4/MAX31850K and other alternatives; not today's hardware. |
| Design pp. 32–35 | “Hardware details”, fixture, sand, hot/cold placement, test matrix, procedure, safety | Undated draft. Includes ESP32/MAX31856 at 1 Hz and 600°C/30-minute language; does not match saved Mega/MAX31855 logger. |
| Design p. 35 | “Thermocouple Check”: reference 21.9°C; T1 21.8°C; T2 22.2°C | Recorded spot-check, not full calibration; no raw run/time trace supplied. |
| Design p. 36 | Preparation; rod/dummy burn-in; 500°C/490–510°C recipe | Undated proposal; T2/T3 naming differs from logger TC1/TC2. Voltage/time recipes are not approved operating instructions. |
| Design pp. 39–40 | Explicit **10/16** setup comparison, coil/real cell versus cartridge/steel surrogate | Date is later in the document than undated sections; cannot infer append order is chronological. |
| Design pp. 41–42 | “Final test with cartridge heater”, acceptance criteria, repeats | Still contains `[model]`, `[100]%`, `[100°C]`, other placeholders and incomplete safety text. “Final” heading does not settle those choices. |
| `references/orders/ChE 126 Materials Ordering.xlsx` | `Materials` sheet; active populated purchase block rows 2–10; totals rows 12–13; additional candidates rows 15, 27–30 | Original retained, plus separate formula/cached-value CSVs and workbook index in `references/orders/extracted/`. Formatting extends to row 1002/column AF; most cells empty. Cached values are not recalculated. |
| `references/datasheets/` | Mica 85165K26; basalt fabric; heater 4877K305; MAX31855; recovered heater instructions PDF | Product/source evidence, not approval of a particular hot fixture. |
| `provenance/claude/conversation.md` | 2026-10-26 wiring/debugging, thermocouple uncertainty, heater moisture discussion | Historical assistant claims include wrong intermediate diagnoses and hot-rewiring suggestions. Use current wiring guide instead. |
| `provenance/chatgpt/conversation.md` | Complete answer from supplied shared page, local links to generated files | Full public answer recovered from embedded page data after text reader omitted it. Structured original text preserved in conversation.json. |
| `models/thermal-stack/README_thermal_experiment.md` | Model assumptions, provenance, executable commands, proposed repeatability protocol | Generated scenario only. Original outputs are predictions/templates, NOT acquired measurements. |
| `references/course/` | Course theme and syllabus | Background, not this experiment's procedure. |
| `references/historical-notes/2025-10-11 Thermal data logger.md` | Older 10-channel/50-Hz concept | Possibly related DAQ idea from a different year; NOT a requirement for this two-channel project. |

## Procurement details worth keeping visible

The order form lists sand, Samsung 25R cells, Skogar HT 2-mm aerogel, cartridge heater **4877K305**, mica **85165K26**, basalt fabric, cinderblocks, all-purpose sand, and a two-prong bare-lead cord. Row 12 caches **$286.89**; row 13 separately says “Total confirmed by Mike …” **$309.57**. Do not reconcile or overwrite this difference without the purchasing context.

The heater PDF specifies **120 VAC, 300 W, 0.50-inch diameter, 2.5-inch nominal element length**, but separately **1 9/16-inch heated length** and unheated end lengths. The shared model uses an assumed **3-inch × 2-inch contact footprint**, and older PDF drafts discuss a 6-mm heater/sleeve. None of those geometries can be substituted for the others. The order's 12.5-mm diameter text also differs from the nominal 0.50 inch = 12.7 mm.

The workbook's carbon-fiber candidate row 28 says “180°F (648.8889 C)”; that conversion is inconsistent. Preserve it as a source error, not a service-temperature limit.

## Unresolved or unsafe-to-assume choices

- Real battery versus inert dummy, cell model/SOC and whether any real-cell heating is intended. PDF p. 35 calls for discharged/dummy cells; p. 41 has a charged-cell placeholder. No approval of live-cell abuse testing is implied.
- Fixture construction and temperature ratings: older pages mention cardboard/plastic/tape near a very hot apparatus. Preserving these notes does **not** endorse that arrangement. A safety-reviewed fixture and independent heater protection must precede high-temperature work.
- Heater installation, actual contact area, power measurement, controller/variac, protective earth, fuse/GFCI and independent cutoff. Two-prong cord procurement alone does not establish protective-earthing arrangements. Arduino signal ground is not protective earth or a mains connection.
- Current material stack, dimensions, aluminum alloy/thickness/workholding, contact pressure and interface resistance. Model values do not select these.
- Actual thermocouple model/service temperature, junction isolation, mounting positions, channel names and uncertainty budget. The spot-check alone does not establish accuracy across the operating range.
- Required sample rate, durable raw logging, metadata/run IDs and acceptance thresholds. Imported plotter is visualization only; no acquired temperature dataset was located among these inputs.

## Export completeness and exclusions

The recent ZIP contains the model script, README, five PNGs, predictions CSV, measurement template and model run log—not a full-account ChatGPT export. All eight sandbox-linked generated artifacts in the supplied share are present locally (seven extracted files plus the ZIP link). The uploaded mica/basalt PDFs match the share's filenames and sizes. See `provenance/chatgpt/attachment-index.json`.

Search covered Downloads (including school), Documents, the Arduino sketchbook, the named Claude session and referenced temporary artifacts, and scoped ChE 126/local note sources. No unrelated portfolio archives, resume DOCX, personal-chat ZIP, full browser profile, credentials, or lab-locker-code fixture notes were imported. Originals were copied, not moved.
