# Run 033

- Started UTC: 2026-11-09T20:47:47.607+00:00
- Updated UTC: 2026-11-09T21:02:19.079+00:00
- State / stop reason: Stopped by command
- Samples: 1744
- Serial at start: /dev/ttyACM0 @ 115200 baud
- Units: seconds, degrees Celsius; UTC is host wall time.
- host_elapsed_s: monotonic seconds since run start; board_time_s: original uptime.
- epoch increments on board time regression; flags preserve sensor faults and zero caveats.
- TC1 CLK/DO/CS: 22/24/26; TC2: 28/30/32 (saved firmware map, not a wiring inspection).
- Probe identity, attachment and calibration: unverified.

## Configuration

```json
{
  "runs_dir": "runs",
  "port": 8765,
  "plot_points": 7200,
  "serial": {
    "port": "",
    "baud": 115200,
    "vid": 9025,
    "pid": 68,
    "serial_number": "64935343733351C0B251"
  },
  "channels": {
    "TC1": "Raw physical channel 1; MAX31855 CLK/DO/CS 22/24/26; role comes from run mapping; probe identity/calibration unverified",
    "TC2": "Raw physical channel 2; MAX31855 CLK/DO/CS 28/30/32; role comes from run mapping; probe identity/calibration unverified"
  }
}
```

## Comments

**2026-11-09 closeout — EXP5 rear-cutoff trip; no completed 700°C/60s hold.**
Logical heater/cartridge = raw `tc2_C`; logical rear/barrier = raw `tc1_C`.
The CSV columns remain in raw physical-channel order. Board-applied settings
were final target700°C, heater cutoff730°C, rear cutoff120°C enabled/required,
hysteresis3°C, prediction lead5s, minimum OFF5s, hold band±5°C and60s elapsed
final hold. Saved100V is manual-preset metadata, not a measured or
software-controlled voltage.

EXP5 START request5 was acknowledged at20:47:47.668 UTC. After a later valid
HOLD_100 report, the saved events record normal NEXT request6 acknowledged at
**20:53:03.506 UTC**. BOOST_FINAL was reported at20:54:47.949 UTC. At
**20:57:57.344 UTC**, the controller reported **TRIPPED / BOOST_FINAL /
TC2_LIMIT / heater_on=false**. This was the logical rear (raw TC1) cutoff, not
an assistant-issued STOP; commanded OFF is telemetry, not independent proof of
power removal. Recording continued until stopped by command at21:02:19.078 UTC.

| Quantity | Result |
|---|---:|
| Saved samples | 1744 |
| First→last sample span | 871.041s (14m31.041s) |
| First / last sample UTC | 20:47:47.865 / 21:02:18.906 |
| Initial heater/rear | 26.5 / 25.5°C |
| Maximum heater, UTC20:58:08.035 | 679.75°C |
| Maximum rear, UTC21:00:12.471 | 153.0°C |
| Trip→last saved sample | 261.562s (4m21.562s) |
| Final saved heater/rear | 376.5 / 146.5°C |

No saved heater sample reached700°C, and the events contain neither HOLD_FINAL
nor COMPLETE. This run is therefore not recorded as a successful final-target
test. All saved temperatures are finite, flags are empty and all samples belong
to epoch5. Raw CSV, events and original configuration/metadata snapshots are
unchanged; only this closeout was appended.

