# Run 001

- Started UTC: 2026-10-30T17:22:42.715+00:00
- Updated UTC: 2026-10-30T17:24:09.160+00:00
- State / stop reason: Stopped by command
- Samples: 171
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
    "TC1": "MAX31855, degrees Celsius; CLK/DO/CS 22/24/26; probe unverified",
    "TC2": "MAX31855, degrees Celsius; CLK/DO/CS 28/30/32; probe unverified"
  }
}
```

## Comments


- 2026-10-30T17:24:07.404+00:00 — Hub commissioning only: both channels nan; probe attachment unverified; no heater controls used.
