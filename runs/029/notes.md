# Run 029

- Started UTC: 2026-11-09T20:02:15.030+00:00
- Updated UTC: 2026-11-09T20:03:04.147+00:00
- State / stop reason: Finalizing previous run before Experiment 5
- Samples: 96
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
experiment snapshot and no EXP5 START in its own event log.

The recording was finalized before Experiment 5 at **20:03:04.147 UTC**; run030
then received the EXP5 START. Saved events include serial reconnect/startup and
an IDLE report, but no heating-program transition for run029.

| Quantity | Result |
|---|---:|
| Saved samples | 96 |
| First→last sample span | 48.787s |
| First / last sample UTC | 20:02:15.130 / 20:03:03.917 |
| Initial heater/rear | 28.0 / 28.0°C |
| Maximum heater/rear | 28.0 / 28.25°C |
| Final saved heater/rear | 27.75 / 28.25°C |

All saved temperatures are finite and flags are empty. Epochs3 and4 reflect the
recorded startup/reset; they do not establish probe calibration or physical
power state. Raw CSV, events and metadata are unchanged; only this closeout was
appended.

