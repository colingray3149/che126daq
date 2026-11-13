# Run 036

- Started UTC: 2026-11-13T18:01:52.883+00:00
- Updated UTC: 2026-11-13T18:17:33.333+00:00
- State / stop reason: Stopped by command
- Samples: 1882
- Serial at start: /dev/ttyACM0 @ 115200 baud
- Barrier: 1 layer mica (McMaster 85165K26, 0.032 in) / 2 layers fiberglass heat barrier strip (McMaster 4234N12, 0.045 in) / 1 thin aluminum sheet
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

- 2026-11-13 correction (operator): the barrier in this run was 2 layers of the fiberglass heat barrier strip, not the ceramic fiber pipe insulation. The barrier line above, run-metadata.json and experiment.toml were corrected after the run; data.csv and events.csv are unchanged.
- Result: EXP6 completed. NEXT sent from HEAT_100 at 18:02:44 UTC; heater first measured >=700 C at 18:06:02 (249.2 s), peaked 714.0 C, 60 s hold completed at 18:07:02 (HOLD_COMPLETE, heat OFF). Rear peaked 80.25 C at 18:12:34 during cooldown (642.0 s); the 120 C rear cutoff was never reached. 1882 samples, no sensor faults.

- Sand: fine, less rocky sand used from run034 onward (2026-11-13); earlier runs used a semi-gravelly sand.
