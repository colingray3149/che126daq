# Run 064 — EXP7: internal TC on MAX31855 faulted at heat-on

2026-11-16 10:29 PST · 100 V · 0:13 long · setup

**Setup:** New cartridge with internal grounded K TC on amplifier 3. Control stack: 1 aluminum sheet. McMaster 8440T32 cartridge, 500 W at 120 V, internal grounded K TC.

EXP7 controlled on the cartridge's internal TC. The internal TC (grounded junction) read NaN 0.7 s after heat-on and the sensor-fault trip ended the run after 1 s. The MAX31855 needs an isolated (ungrounded) junction; this cartridge's TC is grounded to its sheath, and the readings got worse whenever the heater circuit was powered. A 47 kΩ resistor from TC− to ground did not help. Led to the TC513 approach (run 068).

| | |
|---|---|
| TC1 Heater side peak | 26.5 °C at 0:13 |
| TC2 Barrier rear peak | 24.8 °C at 0:09 |
| TC3 Cartridge internal peak | 31.0 °C at 0:13 |
| TC2 rise | 0.0 °C |
| Relay on | 0:01 |

Files: [data.csv](data.csv) · [events.csv](events.csv) · [experiment-applied.json](experiment-applied.json) · [experiment.toml](experiment.toml) · [notes.md](notes.md) · [run-metadata.json](run-metadata.json)
