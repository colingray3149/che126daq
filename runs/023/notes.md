# Run 023

- Started UTC: 2026-11-06T18:26:33.426+00:00
- Updated UTC: 2026-11-06T20:40:58.801+00:00
- State / stop reason: Stopped by command
- Samples: 3313
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


- 2026-11-06T18:55:35.421+00:00 — Run 023 / EXP3 operator closeout: operator described this run as great and SUCCESSFUL, operated at approximately 70 V. This is an operator-reported approximate operating voltage, not a logged electrical measurement; the original saved 65 V preset is retained as the requested configuration, not the actual-voltage claim. The voltage time history was not supplied. Saved setup comments carry the previously reported stack: 1 mica layer, 2 basalt-fabric layers, 1 aluminum layer; no new layer order, thickness or sand-condition observation was supplied. Corrected roles: logical TC1/heater = raw TC2; logical TC2/rear = raw TC1. Saved data: 3313 samples from 2026-11-06T18:26:33.875Z through 18:54:08.997Z, 1655.12 s between first/last samples; zero nonfinite readings on either channel. Heater peak 303.00 C, rear peak 83.75 C; last readings heater 277.00 C and rear 83.75 C. Applied target 300 C, heater cutoff 320 C, rear cutoff enabled at 85 C. STOP request 6 acknowledged at 18:53:37.360Z with STOPPED/heater_on=false; hold_s=1218 (20 min 18 s), not completion of the configured 1800 s hold. USB/serial disconnected at 18:54:09.273Z; no samples after 18:54:08.997Z at inspection. Host recording remains open. Current physical heater power after disconnect is unknown to software; the earlier OFF acknowledgement is not electrical-isolation proof. Logging this assessment does not change controller settings, raw data, original run metadata or run numbering.

- 2026-11-06T20:40:58.796+00:00 — Operator requested a fresh updated session. Finalizing run 023 after its earlier acknowledged STOP; serial is currently disconnected, so current physical heater state cannot be verified. Preserving all recorded data.
