# Run 010

- Started UTC: 2026-11-02T19:17:38.470+00:00
- Updated UTC: 2026-11-02T19:18:05.845+00:00
- State / stop reason: Finalizing previous run before Experiment 2
- Samples: 52
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
    "TC1": "Heater-side TC; MAX31855 CLK/DO/CS 22/24/26; probe identity/calibration unverified",
    "TC2": "Opposite barrier face; EXP2 cutoff at >=140 C; MAX31855 CLK/DO/CS 28/30/32; probe identity/calibration unverified"
  }
}
```

## Comments

