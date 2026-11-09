# Run 019

- Started UTC: 2026-11-06T18:03:54.034+00:00
- Updated UTC: 2026-11-06T18:20:38.684+00:00
- State / stop reason: Restarted by command
- Samples: 2008
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


- 2026-11-06T18:10:18.078+00:00 — Operator reports graphs still combined and rising heater trace labeled TC2, and requests assurance that stop exp3 cuts heat. At inspection controller reports swap_inputs=true, rear cutoff 85C, STOPPED/heater_on=false with STOP request 2 acknowledged at 18:04:26.840Z; raw TC2 is the heater and raw TC1 the rear. Physical power removal is not verified by serial telemetry. Correcting browser presentation without restarting acquisition.
