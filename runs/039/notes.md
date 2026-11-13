# Run 039

- Started UTC: 2026-11-13T18:46:14.478+00:00
- Updated UTC: 2026-11-13T18:46:34.008+00:00
- State / stop reason: Finalizing previous run before Experiment 6
- Samples: 36
- Serial at start: /dev/ttyACM0 @ 115200 baud
- Barrier: 1 layer mica (McMaster 85165K26, 0.032 in) / 3 layers ceramic fiber pipe insulation (McMaster 87575K35, alumina, 1/32 in) / 1 thin aluminum sheet
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

- Idle recording before the run040 EXP6 START (serial reopen/reset; board IDLE, no heating).

- Sand: fine, less rocky sand used from run034 onward (2026-11-13); earlier runs used a semi-gravelly sand.
