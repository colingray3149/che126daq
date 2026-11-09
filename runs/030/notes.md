# Run 030

- Started UTC: 2026-11-09T20:03:04.149+00:00
- Updated UTC: 2026-11-09T20:21:31.018+00:00
- State / stop reason: Stopped by command
- Samples: 2215
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

EXP5 START request3 was acknowledged at20:03:04.220 UTC; NEXT request4 at
20:03:32.317 UTC; BOOST_FINAL was reported at20:05:11.654 UTC. At
**20:06:42.606 UTC**, the controller reported **TRIPPED / BOOST_FINAL /
TC2_LIMIT / heater_on=false**. This was the logical rear (raw TC1) cutoff, not
an assistant-issued STOP; commanded OFF is telemetry, not independent proof of
power removal. Recording continued until stopped by command at20:21:31.018 UTC.

| Quantity | Result |
|---|---:|
| Saved samples | 2215 |
| First→last sample span | 1106.446s (18m26.446s) |
| First / last sample UTC | 20:03:04.417 / 20:21:30.863 |
| Initial heater/rear | 28.0 / 28.25°C |
| Maximum heater, UTC20:06:48.300 | 483.0°C |
| Maximum rear, UTC20:07:39.775 | 139.5°C |
| Trip→last saved sample | 888.257s (14m48.257s) |
| Final saved heater/rear | 90.75 / 75.0°C |

No saved heater sample reached700°C, and the events contain neither HOLD_FINAL
nor COMPLETE. This run is therefore not recorded as a successful final-target
test. All saved temperatures are finite, flags are empty and all samples belong
to epoch4. Raw CSV, events and original configuration/metadata snapshots are
unchanged; only this closeout was appended.

