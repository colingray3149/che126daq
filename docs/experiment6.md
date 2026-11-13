# EXP6 — EXP5 with an ungated `next`

EXP6 is EXP5 unchanged except for one rule: `next` is accepted any time
during the 100°C stage (HEAT_100 or HOLD_100), at any heater temperature. The
hub no longer requires the heater to be within 100°C ± `hold_band_C` or a
fresh sample before sending it, and the firmware no longer rejects it with
`NEXT_NOT_READY` outside the band.

Everything else is EXP5: 90-second reference ramp to 200°C, maximum commanded
heat toward 700°C, 60-second elapsed hold from the first measured ≥700°C, then
heat OFF with cooldown logging. The 730°C heater cutoff, 120°C rear cutoff,
sensor/staleness/heartbeat/STOP protections and OFF dwell are unchanged.
`experiment6.toml` holds the same settings as `experiment5.toml`.

## Commands

- `start exp6`: allocate the next run and arm EXP6 with `experiment6.toml`.
- `next`: leave the 100°C stage now and start the ramp.
- `stop exp6` / `stop`: as for EXP5.

EXP6 needs the updated firmware uploaded (heater power unplugged first, as
for every upload): `arduino-cli upload --fqbn arduino:avr:megaADK --port /dev/ttyACM0 firmware/thermocouple_logger`.
