# Mica + basalt + aluminum: thermal resistance and heater/thermocouple model

## Primary quantitative result

For a full **6 in × 2 in** sheet, assuming 1D, through-thickness, perfectly bonded conduction:

- Mica: 0.032 in thick; k = 0.3 W/(m K), R = 0.349956 K/W.
- Basalt strip: 3/64 in thick; k = 2.44 BTU in/(hr ft² °F) = 0.351916 W/(m K), R = 0.437006 K/W.
- Aluminum 3003-H14: 0.225 mm thick; k = 159 W/(m K), R = 0.00018278 K/W.
- **Without aluminum:** R = 0.7869621 K/W; effective k = 0.3288294 W/(m K).
- **With aluminum:** R = 0.7871449 K/W; effective k = 0.3656745 W/(m K).
- Extra bulk resistance: **0.023226%**. Effective k rises because thickness increases, **not** because more heat crosses for a fixed hot-to-cold temperature difference.

Formula: `R_i = L_i/(k_i*A)`; `R_total = sum(R_i)`; `Qdot = (T_hot - T_cold)/R_total`. For the 3 in × 2 in patch, resistances double under an isolated-area 1D assumption.

## Example time simulation (hypothetical, not a validated forecast)

- 20 W electric cartridge heater; **assume** 30% = 6 W enters the sample.
- Ambient 25 °C; effective rear heat-transfer coefficient h = 15 W/(m² K).
- Full 2 in heated width and centered 3 in heated height, within a 6 × 2 in plate.
- Room-side convection plus radiation approximated with constant h; no explicit heater block, clamp, front heat losses, side-edge heat losses, TC bead mass, or contact resistance.
- One thermal capacitance node per material per stripe; a 60-stripe x-height finite-volume network. Aluminum stripes exchange heat laterally; mica and basalt in-plane flow neglected.
- Default result at the **center** of the 3-in heater patch: near steady state, **128.3 °C without aluminum** vs **89.2 °C with aluminum**. Without aluminum, roughly **5.86 min** to 100 °C, but with aluminum the center does **not** reach 100 °C at that power and assumed heat losses. These are model-dependent results, not predictions guaranteed in your apparatus.
- A strictly isolated 1D model that ignores heat spreading instead predicts 100 °C with aluminum in about 6.64 min, illustrating how misleading the 1D model can be for a local thermocouple.

## Source provenance

- Mica: McMaster-Carr 85165K26 product PDF supplied by user. Thermal conductivity 0.3 W/(m K), thickness 0.032 in, listed density 0.2 lb/in³.
- Basalt: McMaster-Carr 1727T14 product PDF supplied by user. Thickness 3/64 in, conductivity 2.44 BTU in/(hr ft² °F) stated at 900 °F, density 1.75 lb/ft³.
- Aluminum: 3003-H14 typical density 2730 kg/m³, conductivity 159 W/(m K), specific heat 893 J/(kg K), from MatWeb/Clinton Aluminum and associated commercial data.
- Mica/basalt *specific heats* assumed 840 J/(kg K) because product PDFs do not provide them. The stated mica density corresponds to 5.54 g/cm³, higher than many reference values for natural phlogopite (typically ~2.6–3.2 g/cm³); verify the specific sheet's mass if you want useful time-to-temperature forecasts. `--mica-density-scale 0.5` is an illustrative lower-density sensitivity run.
- All conductivities taken as constant, although user product k values have different temperature reference points.

## Run the script

1. Install dependencies: `python -m pip install numpy scipy matplotlib`
2. Run: `python thermal_stack_model.py`
3. Set parameters: `python thermal_stack_model.py --power 30 --coupling 0.30 --h 15 --target 100`
4. Test density sensitivity: `python thermal_stack_model.py --mica-density-scale 0.5`
5. Enter actual thermocouple readings in `measurements_template.csv` under `TC_C`, keeping `config` as `bare` or `aluminum` and `run` as 1/2/3.
6. Overlay measured points and estimate run-level RMSE at the specified power: `python thermal_stack_model.py --power 20 --measurements measurements_template.csv`

**Limit of spatial mesh:** This program assumes the 3-in heater is in contact across the entire 2-in width. A typical cylindrical cartridge may have a much narrower heater contact patch. To model a narrower contact accurately you need a 2D *in-plane* aluminum mesh (or full 3D FEA), so the script intentionally rejects `--heater-width-in` values other than 2.

## Output files

- `01_conduction_comparison.png`: resistance and effective conductivity
- `02_thermocouple_vs_time.png`: temperature vs time, including 1D vs lateral spreading
- `03_time_to_targets.png`: heater power vs time to reach 50, 100, and 150 °C
- `04_aluminum_spreading_illustration.png`: rear surface temperature along the 6-in plate
- `05_interface_contact_sensitivity.png`: possible contact resistance penalty
- `thermal_predictions.csv`: model traces at 5, 10, 20, 40, and 60 W
- `measurements_template.csv`: blank rows for 3 repeat tests in each configuration

## Suggested experimental protocol

1. Record dimensions, actual heater contact width, pressure/torque, ambient, and thermocouple attachment point. Insulate or characterize the heater fixture's other heat-loss paths.
2. At identical electrical powers, first perform at least 3 runs with mica+basalt and 3 runs with mica+basalt+aluminum. Return the entire fixture close to the same starting temperature before each run; alternate ordering where possible. If high temperatures are used, monitor for permanent compression/binder effects.
3. Log electric voltage *and* current, source temperature, rear thermocouple temperature, and another rear thermocouple outside the heater's 3-in footprint (if possible). Sample 1 Hz or better then average/report 10- or 30-second windows.
4. Repeat at at least two safe heater powers. Normalize by net thermal power INTO the stack if you can separately estimate heat leaks; electric power alone is not equal to through-sample heat flow.
5. At steady state, for a verified heat flow Q through the stack, `R_experiment = (T_front - T_back)/Q`. Without heat-flow measurement, the model can be fitted to transient readings, but this does not independently validate thermal conductivity or thermocouple calibration.
6. Quantify mean peak/steady temperatures, time to common temperature thresholds, between-run standard deviation, and paired no-Al/with-Al differences. Three repeats assess preliminary repeatability, not rigorous statistical equivalence.
7. If the goal is to test whether the **bulk layer** is unchanged, place thermocouples on both sides of the laminate at matching positions *inside the heater footprint* and keep boundary conditions as similar as possible. A rear thermocouple bonded directly to the aluminum may read a different local temperature simply because the aluminum redistributes heat over the plate.

**Safety:** the aluminum alloy has a much lower melting point than the mica/basalt maximum temperature ratings, and an aluminum sheet loses stiffness at temperatures well below its melt point. Keep expected metal, fixture, and bond temperatures within documented material/service limits. Electrical insulation and TC grounding should be verified separately.
