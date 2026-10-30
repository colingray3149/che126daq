# Running the imported code

These commands use the repository root as the working directory. Current executable sources were copied unchanged. Historical code and source errors are explicitly retained for later refinement.

## Arduino

Observed installed dependencies: Arduino AVR Boards **1.8.8**, Adafruit MAX31855 library **1.4.2**, Adafruit BusIO **1.17.4**. Board FQBN: `arduino:avr:megaADK`.

```sh
arduino-cli board list
arduino-cli compile --fqbn arduino:avr:megaADK firmware/thermocouple_logger
```

Compilation does not upload. No upload was performed during this collection. Select the actual port after each replug; `ttyACM0` is today's observation, not a stable device name. Do not replace firmware or switch diagnostic sketches without matching their wiring and serial format first.

`tc_fault` uses the current logger pin map but outputs human-readable diagnostics. `tc_diag` uses an OLD pin map; see [wiring.md](wiring.md). Neither diagnostic output is a compatible input to the CSV plotter.

## Live plotting

On this NixOS workstation the original executable script has a nix-shell shebang for matplotlib, pyserial, and tkinter:

```sh
./host/plot.py /dev/ttyACM0
```

Or use an explicitly provisioned Python environment with those packages:

```sh
python host/plot.py /dev/ttyACM0
```

Close other serial readers first. The plot opens the serial port at 115200 baud and may reset the Arduino. It displays the last 20 seconds; **it does not save data to disk**. CSV header is `time_s,t1_C,t2_C`; time comes from board uptime, nominal interval 0.5 seconds. Fault `nan` is displayed as “fault”.

Known imported limitations, intentionally not fixed in this collection:

- Legend still says `(A1)` / `(A2)` from the early analog version. These are stale labels; actual MAX31855 signals use the digital pins in wiring.md.
- Default port picks the first sorted `/dev/ttyACM*`, not board identity. Specify a port explicitly; no-device and unplug/reconnect handling are not robust.
- All-zero MAX31855 frames are not rejected. Today's zeros do not validate wiring or temperature.
- Uptime/reset/wrap behavior, durable logging, units/metadata standardization and calibrated uncertainty remain for subsequent work with the user.

## Thermal model

Dependencies: Python, numpy, scipy, matplotlib. Original ZIP README supplies the model's assumptions and limitations. Run into a separate output directory so original generated artifacts are not overwritten:

```sh
python models/thermal-stack/thermal_stack_model.py --out /tmp/che126daq-model-run
```

Optional example parameter changes are scenarios, not heater-control instructions:

```sh
python models/thermal-stack/thermal_stack_model.py --power 30 --coupling 0.30 --h 15 --target 100 --out /tmp/che126daq-model-run
```

The supplied measurement CSV has blank `TC_C` entries; it is not experimental data. Heater power/coupling, footprint, boundary losses, heat capacities, densities, constant conductivities and contact resistance must be checked before comparing to real apparatus.

## Source provenance

`provenance/source-manifest.json` records byte-preserving imports and ZIP extraction. `provenance/claude/code-history/index.json` identifies reconstructed Write/Edit states. Bash-based changes remain in `code-tool-calls.json`; historical snapshots are not asserted to reconstruct every Bash-modified intermediate state. Current copied sources, not those snapshots, are the latest saved files.

Prior `megaadk-flash.bin`/`.hex` backups are labeled `prior-board-flash.*`: they are historical backups, not a verified binary of today's saved logger and not an instruction to flash them.
