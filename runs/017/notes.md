# Run 017

- Started UTC: 2026-11-06T17:33:17.243+00:00
- Updated UTC: 2026-11-06T17:54:08.898+00:00
- State / stop reason: Stopped by command
- Samples: 2504
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


- 2026-11-06T17:39:38.731+00:00 — Operator correction: probes were reversed during this run. Raw tc1_C is opposite-barrier temperature; raw tc2_C is heater temperature. Preserve raw CSV columns. The TC2_LIMIT event therefore acted on the heater probe, not the intended barrier probe. Operator requests 65 V RMS preset for EXP3; earlier automatic 30 V note is an assumption, not a measured voltage. Actual voltage history of this run is not established.

- 2026-11-06T17:53:55.929+00:00 — Operator assessment at closeout: first successful test. Reported assembly: one layer mica, two layers basalt fabric, one layer aluminum. Layer counts are operator-reported; hot-to-cold order, thicknesses, sand condition and actual voltage history were not supplied in this closeout. Probes were reversed: raw TC1=rear, raw TC2=heater; TC2_LIMIT was the 85 C cutoff acting on the heater probe. This successful-test assessment does not establish a completed 300 C/30 minute hold. Next planned experiment: EXP3 with corrected software input mapping and 65 V manual preset, intended run 018.
