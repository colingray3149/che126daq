# Sources for the current fixture checks

Retrieved/read 2026-10-30. Source values are not operating recommendations. New originals and page-marked text are in `references/current-check/`; URLs, retrieval times, byte counts and hashes are in its `sources.json`. Previously downloaded originals remain in `references/datasheets/` and `references/text/`.

## S1 — Actual ordered heater

**McMaster 4877K305**, [product](https://www.mcmaster.com/4877K305/). Local original: `references/datasheets/Insertion Heater with Braided Wire Lead Covering, for 1_2_ Hole, 120V AC, 2-1_2_ Long Heating Element, 300W _ McMaster-Carr.pdf`, pp. 1–2.

- Rated **300 W at 120 VAC**, listed **2.5 A**; no built-in temperature control.
- Nominal element envelope **2.5 inches long, 0.50 inches diameter**; separately lists **1 9/16 inches heated length**, base-end unheated length **1/2 inch**, tip-end unheated length **7/16 inch**.
- Maximum exposure temperature **1400°F**; wire-lead maximum exposure **840°F**. These are not desired setpoints, not a rating of every fixture component, and not proof the element can shed rated power while leaned against mica.
- Manufacturer page describes installation into drilled/reamed holes for metal-to-metal heat transfer and says a separate temperature switch/controller is required.
- The script derives nominal electrical resistance from the rating and treats constant resistance as an explicitly labeled approximation. Measure RMS voltage/current across the actual load; do not infer wattage from a variac dial position.

## S2 — Mica benchmark

**McMaster 85165K26**, [product](https://www.mcmaster.com/85165K26/). Local original: `references/datasheets/Extra-High-Temperature Electrically Insulating Mica, 23_ x 39_ Sheet, 0.032_ Thick _ McMaster-Carr.pdf`, p. 1.

- Thickness **0.032 inch**, tolerance **±0.0032 inch**.
- Listed thermal conductivity **0.3 W/(m·°C)**; adjacent conductivity-at-temperature entry **2.08 BTU·in/(hr·ft²·°F) at 500°F**. The calculations use the SI value without implying that it is a measured room-temperature value for this specimen.
- Mica composition **90%**, silicone-resin binder; it is a manufactured sheet, not a pure-mica reference crystal.
- Listed maximum continuous exposure **1275°F**, intermittent **1800°F**. Product exposure limits do not establish complete fixture safety or an appropriate thermocouple range.
- Listed density **0.2 lb/in³** is retained as source data but **not used** to predict transients here. Heat capacity and a validated thermal boundary model for this fixture are absent.

## S3 — Basalt for later comparisons

**McMaster 1727T14**, [product](https://www.mcmaster.com/1727T14/). Local original: `references/datasheets/High-Strength Basalt Pipe Insulation, 2_ Wide _ McMaster-Carr.pdf`, p. 1.

- Width **2 inches**; thickness **3/64 inch**.
- Conductivity entry **2.44 BTU·in/(hr·ft²·°F) at 900°F**; maximum exposure **1200°F**.
- These conductivity reference conditions differ from the mica and ambient aerogel data. Treat a constant-k stack calculation as a scenario, not a verified hot-stack property.

## S4 — Ordered aerogel, not yet available

**Enersens SKOGAR HT**, ordered through [BuyAerogel](https://www.buyaerogel.com/product/skogar-ht/). [Manufacturer PDS](https://www.buyaerogel.com/wp-content/uploads/2025/03/PDS_Skogar_EN_25032.pdf), local `references/current-check/aerogel-pds.pdf`, p. 1; [SDS](https://www.buyaerogel.com/wp-content/uploads/2025/03/ENERSENS_SKOGAR-HT-2.0_2.5_3.0_3.5_6.0_SUI_EU_EN_v5.pdf), local `aerogel-sds.pdf`.

- Order sheet selects a **2-mm** sheet; manufacturer nominal thickness is measured at **0.5 kPa**, HT thickness tolerance **±0.3 mm**.
- Manufacturer HT conductivity range **0.012–0.018 W/(m·K) at 20°C**, not one universally fixed value. Heat capacity listed approximately **950 J/(kg·K) at 20°C**.
- **Up to 1300°C is short-time flame exposure**, not a general continuous service-temperature rating. The order-sheet shorthand “1300 C” loses that qualification.
- Clamping/compression can matter; do not assume the as-installed thickness equals the nominal thickness.

## S5 — Sand identity and missing thermal properties

Order sheet row 9 links **QUIKRETE All-Purpose Sand No. 1152**: [manufacturer page](https://www.quikrete.com/productlines/sandallpurpose.asp), [PDS](https://www.quikrete.com/PDFs/DATA_SHEET-QUIKRETE%20Sand%20%26%20Gravel%20Products.pdf), [SDS B1](https://www.quikrete.com/PDFs/SDS-B1-Packaged-Aggregate.pdf). Local `references/current-check/sand-pds.pdf` and `sand-sds.pdf`.

- Manufacturer calls it a washed, graded aggregate meeting ASTM C33, **not concrete mix**. Bag identity still needs visual confirmation.
- The PDS does **not** supply thermal conductivity, heat capacity, packing density, or moisture content for today's fill. No numerical sand thermal forecast is justified from this PDS alone.
- SDS identifies silica/dust inhalation and eye hazards; avoid generating/breathing dust while handling or drying. Drying/conditioning requires a suitable lab procedure, not the mains heater improvised as a sand dryer.
- User reports today's sand is semi-wet. Moisture and packing can change conduction, thermal storage and evaporation; no amount of water or thermal property has been measured yet.

## S6 — The battery is not a dummy

Order sheet row 3 links **Samsung INR18650-25R**: [seller](https://www.18650batterystore.com/products/samsung-25r-18650); [Samsung SDI SDS, 2018-01-01 rev. 01](https://cdn.shopify.com/s/files/1/0481/9678/0183/files/Samsung-25R-18650-SDS.pdf?v=1792487743), local `references/current-check/battery-sds.pdf`.

- SDS identifies a lithium-ion cell, **3.60 V**, **2.50 Ah**, **9.20 Wh** as printed. These data are not used to model this uncharacterized cell as a thermal mass.
- SDS §§2, 5, 7, 10 warn about thermal abuse/hot surfaces, venting and hazardous contents. Its warning about explosion/venting above **125°C** is **not a safe operating threshold below that temperature**.
- Initial heater/DAQ/fixture checks should use no real cell or an inert surrogate. A reviewed cell-heating experiment would be a separate decision, not a default consequence of putting a battery behind a barrier.

## S7 — Probe identity is important

Possible match based on older session: **Adafruit #3245 stainless-tip K thermocouple**, [product specification](https://www.adafruit.com/product/3245); readable capture `references/current-check/probe.txt`. Actual SKU has not been visually confirmed.

- Page says suitable up to **500°C** and explicitly states the thermocouple tip is **electrically connected to the steel probe**.
- Do not assume this assembly has an isolated junction. The page does not provide a complete calibrated accuracy budget for the particular probes on the bench.
- [Adafruit MAX31855 Arduino guide](https://learn.adafruit.com/thermocouple/arduino-code) states grounded thermocouples are not supported. Investigate faults caused by probe contact with a grounded heater; do not defeat protective earth.

## S8 — Converter resolution is not measurement accuracy

[MAX31855 manufacturer datasheet](https://cdn-shop.adafruit.com/datasheets/MAX31855.pdf), local `references/datasheets/MAX31855.pdf`, pp. 3–4, Thermal Characteristics and Note 4.

- Thermocouple output resolution **0.25°C**.
- MAX31855K gain/offset limit **±2°C** for thermocouple temperatures **−200 to +700°C**, converter ambient **−20 to +85°C**.
- Separate cold-junction error limit **±2°C** over that ambient range. **Note 4 excludes cold-junction error and thermocouple nonlinearity from the gain/offset specification.**
- The script sums these two electronics limits conservatively per channel and across a difference. That is not a statistical confidence interval, not a full probe/contact uncertainty budget, and not evidence of the actual offset of these two channels. Shared errors may correlate; no unsupported RSS assumption is made.

## S9 — Heater moisture and electrical installation

[Tempco DE14, Preventing Moisture-Induced Failures in Electric Heaters](https://www.tempco.com/wp-content/uploads/2026/03/DE14.PreventingMoistureFailure.pdf), original recovered in `references/datasheets/webfetch-1793036443765-bojg5m.pdf`; text `references/text/tempco-heater-instructions.txt`.

The article discusses hygroscopic MgO insulation, moisture-related loss of insulation resistance, qualified electrical testing/conditioning and protective grounding of the sheath. It is general heater guidance, **not proof that this McMaster heater is certified for wet-sand use**. Manufacturer-specific installation requirements take precedence. Do not improvise megger/hi-pot work on a connected Arduino or treat generic bake-out recipes as an approved procedure.

## S10 — Dimensions and equations used by the scripts

- **User-reported sample size:** 2 × 6 inches; source [experiment-log.md](experiment-log.md), this session.
- Exact SI conversion: **1 inch = 0.0254 m**, by definition; [NIST SI Units — Length, redefinition of the inch](https://www.nist.gov/pml/owm/si-units-length#metric_redefinition).
- Plane-wall Fourier relation: `Q = k A (T_hot − T_cold) / L`, `R = L/(k A)`. Requires a meaningful cross-sectional area, steady 1D conduction, and appropriate surface temperatures; it is not automatically valid for a line-heated plate. Reference: [MIT Unified Engineering, steady heat transfer](https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node118.html).
- Pure-resistance electrical model: `P = V_rms I_rms = V_rms²/R`. Nominal R comes from S1's rated voltage/power, not a measured cold resistance. Actual electrical power and waveform/load behavior should be measured.

Every source input and every analyst-selected scenario is separately labeled in `models/mica-check/inputs.json`. Computed results are generated by `calculate.py`; figures and tables are conditional calculations, not acquired measurements or safe-setting approvals.
