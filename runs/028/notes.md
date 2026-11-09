# Run 028

- Started UTC: 2026-11-09T18:27:43.481+00:00
- Updated UTC: 2026-11-09T18:46:21.061+00:00
- State / stop reason: Stopped by command
- Samples: 2236
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

**Actual test 4; successful EXP5:** the operator reported that the completed
experiment **“went well.”** This records that assessment separately from probe
calibration, component certification or electrical-power verification. The
intended exp027 recording was finalized when EXP5 START allocated the actual
recording, **run028**.

### Configuration and observed sequence

- Logical heater/cartridge = raw `tc2_C`; logical rear/barrier = raw `tc1_C`.
  The CSV columns remain in raw physical-channel order.
- Board-applied settings: final target700°C, heater cutoff730°C, rear cutoff
  120°C enabled/required, hysteresis3°C, prediction lead5s, minimum OFF5s,
  hold band±5°C and60s elapsed final hold. Saved100V is manual-preset metadata,
  not a measured or software-controlled voltage.
- START request1 was acknowledged at18:27:43.595 UTC; NEXT request2 at
  18:28:47.603 UTC. BOOST_FINAL began at18:30:19.395 UTC.
- The first saved heater sample≥700°C was **700.25°C at18:32:12.535 UTC**.
  HOLD_FINAL began1ms later at18:32:12.536 UTC with the reported hold counter0.
- COMPLETE/HOLD_COMPLETE was reported at18:33:12.807 UTC with commanded heat
  OFF and hold counter60. HOLD_FINAL→COMPLETE was **60.271s**. Commanded OFF is
  controller telemetry, not independent proof of relay contacts or power removal.
- No `TC1_LIMIT`, `TC2_LIMIT`, `TRIPPED` or sensor-fault trip appears in the
  saved events. Recording continued through cooldown until stopped by command
  at18:46:21.060 UTC,788.253s after COMPLETE.

### Saved measurements

| Quantity | Result |
|---|---:|
| Saved samples | 2236 |
| First→last sample span | 1116.729s (18m36.729s) |
| First sample, UTC | 18:27:43.898 |
| Last sample, UTC | 18:46:20.627 |
| Initial heater/rear | 41.0 / 26.75°C |
| Maximum heater, UTC18:32:16.033 | 707.75°C |
| Maximum rear, UTC18:39:35.319 | 83.5°C |
| COMPLETE→last saved sample cooldown | 787.820s (13m7.820s) |
| Final saved heater/rear | 161.5 / 75.25°C |

All saved temperature readings are finite, all flags are empty and all samples
belong to epoch2. These checks do not establish probe identity/calibration or
physical power state. The raw CSV, events and original configuration/metadata
snapshots are unchanged; only this closeout was appended.

