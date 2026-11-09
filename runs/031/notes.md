# Run 031

- Started UTC: 2026-11-09T20:33:09.511+00:00
- Updated UTC: 2026-11-09T20:47:42.594+00:00
- State / stop reason: Restarted by command
- Samples: 1747
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

**2026-11-09 closeout — supporting acquisition, not an EXP5 heating test.**
Logical heater/cartridge = raw `tc2_C`; logical rear/barrier = raw `tc1_C`.
The CSV columns remain in raw physical-channel order. Retained `exp5`,
`swap_inputs=true` and 100V metadata describe the session mapping/manual preset,
not applied heating settings or a measured voltage. This run has no applied
experiment snapshot and no EXP5 START in its own event log; its events contain
only recording creation and **Restarted by command** at20:47:42.593 UTC.

| Quantity | Result |
|---|---:|
| Saved samples | 1747 |
| First→last sample span | 872.558s (14m32.558s) |
| First / last sample UTC | 20:33:09.806 / 20:47:42.364 |
| Initial heater/rear | 41.5 / 39.75°C |
| Maximum heater, UTC20:34:03.779 | 42.25°C |
| Maximum rear, UTC20:34:23.771 | 40.5°C |
| Final saved heater/rear | 26.5 / 25.5°C |

The measurements show cooldown/ambient-range acquisition, not execution or
completion of the EXP5 heating sequence. All saved temperatures are finite,
flags are empty and all samples belong to epoch5. Raw CSV, events and metadata
are unchanged; only this closeout was appended.

