# Run 068 — EXP8: TC513 on internal TC, 650 °C; did not hold

2026-11-16 12:41 PST · 100 V · 16:28 long · test

**Setup:** Barrier not recorded. McMaster 8440T32 cartridge, 500 W at 120 V, internal grounded K TC at 100 V (about 347 W). The Selec TC513 reads the internal TC with setpoint 650 °C; the DAQ relay feeds both the TC513 and the heater.

Full power to 100 °C, cut at 0:36; the heater side kept climbing to 187 °C on stored heat. The first NEXT started the ramp, but the old ramp began its setpoint at 100 °C while the reading was ~170 °C, so nothing heated for 55 s; a second NEXT was swallowed. After 200 °C the relay stayed on (TC513 in charge). The external TC peaked 419 °C at 5:45 and then cooled exactly as with the heater off: the thermal model fits the rest of the run within 11 °C if heater power stopped for good at 5:02. So the TC513 switched the heater off once (its internal TC near 650 °C) and never switched it back on; the operator reports the TC513 was configured wrong. The 90 s hold was never started.

| | |
|---|---|
| TC1 Heater side (external) peak | 419.0 °C at 5:45 |
| TC2 Barrier rear peak | 110.0 °C at 10:52 |
| TC1 reached 100 °C after heat on | 0:36 |
| TC1 reached 200 °C after heat on | 4:15 |
| TC1 reached 400 °C after heat on | 5:19 |
| TC2 rise | 86.2 °C |
| Fitted rear gain | 0.38 (±1.8 °C) |
| Relay on | 13:11 |

Files: [data.csv](data.csv) · [events.csv](events.csv) · [experiment-applied.json](experiment-applied.json) · [experiment.toml](experiment.toml) · [notes.md](notes.md) · [run-metadata.json](run-metadata.json)
