# Run 040

- Started UTC: 2026-11-13T18:46:34.011+00:00
- Updated UTC: 2026-11-13T19:05:46.521+00:00
- State / stop reason: Stopped by command
- Samples: 2306
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

- Result: EXP6 completed (actual test 6). Barrier 1 mica / 3 layers ceramic fiber pipe insulation / 1 aluminum. NEXT from HEAT_100 at 18:47:28 UTC; BOOST_FINAL 18:48:53; heater first measured >=700 C at 18:52:21 (347.7 s), peaked 709.5 C; 60 s hold complete at 18:53:21 (HOLD_COMPLETE, heat OFF). Rear peaked 113.25 C at 18:56:02 (568.5 s), during cooldown; the 120 C rear cutoff was not reached. Cooldown recorded to STOP at 19:05:46. 2306 samples, no sensor faults.
