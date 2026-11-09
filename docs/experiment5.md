# EXP5 — completed run028

**Completed recording:** [run028](../runs/028/notes.md). The operator reported
that it **“went well.”** The intended exp027 recording was finalized when EXP5
START allocated the actual experiment recording, run028; run027 remains a
supporting acquisition, not a completed EXP5 controlled test.

Operator request: preserve EXP4's 100°C hold until explicit `next`, then its
90-second reference ramp to 200°C. After the measured-200°C transition, apply
maximum commanded heat toward 700°C. Start a 60-second elapsed hold only when
the heater/cartridge thermocouple first measures at least700°C; regulate during
that minute, then command heat OFF. Keep recording cooldown.

The required barrier/rear hard cutoff changes from85°C to **120°C**. EXP4 is
not modified. All other settings remain the same: 730°C heater cutoff,
3°C hysteresis,5s prediction lead,5s minimum OFF dwell,5°C hold-entry band,
100V manual variac metadata, raw TC2 heater / raw TC1 rear. The variac is not
software controlled. `experiment5.toml` is the selected settings source.

## Commands

- `start exp5`: allocate the next numbered run, snapshot settings and explicitly arm EXP5.
- `next`: advance EXP5's in-band100°C hold into the90-second ramp, without a new recording.
- `stop exp5`: command heat OFF, keep cooldown logging.
- `stop`: command heat OFF and finalize the recording.
- `clear`: clear this browser's graphs/console only; saved data remains unchanged.

Launch with `--wait-for-start` so opening the hub does not allocate an extra
recording. For this session, the intended `runs/027` was finalized on EXP5 START
and the actual recording became `runs/028`. The experiment program is EXP5;
exp027 was the intended recording identifier, not another program command.
No automatic START.

## Deadline and limits

The final hold starts on **measured**, not predicted,700°C arrival. Its deadline
is60 elapsed seconds, not60 accumulated in-band seconds. Excursions do not
restart it; interlocks can end heating sooner. Normal OFF dwell is retained,
so “as soon as possible” means full commanded output within existing interlocks,
not increased voltage or bypassed protections. Safety decisions precede output
and acknowledgements. COMPLETE leaves commanded heat OFF until explicit START.

This change records the requested software behavior; it does not certify the
assembly for700°C or guarantee actual power removal. Saved component-rating
warnings and the NC relay's reset/power-loss fail-ON limitation still apply.
Deployment/verification evidence is recorded in `activity-log.md`.

## Latest session — runs029–033 (2026-11-09)

- [Run029](../runs/029/notes.md): 96-sample supporting acquisition, finalized
  before EXP5 START; no applied EXP5 configuration in its own record.
- [Run030](../runs/030/notes.md): 2215-sample EXP5 acquisition; logical rear/raw
  TC1 `TC2_LIMIT` at20:06:42.606 UTC. Heater peaked483.0°C; no700°C arrival or
  final hold.
- [Run031](../runs/031/notes.md): 1747-sample supporting/cooldown acquisition,
  restarted by command; no EXP5 START in its own event log.
- [Run032](../runs/032/notes.md): 10-sample transition acquisition, finalized
  before EXP5 START; no applied EXP5 configuration in its own record.
- [Run033](../runs/033/notes.md): 1744-sample EXP5 acquisition; logical rear/raw
  TC1 `TC2_LIMIT` at20:57:57.344 UTC. Heater peaked679.75°C; no700°C arrival or
  final hold.

Runs030 and033 are trip-terminated records, not successful final-target tests.
Run028 above remains the separate operator-reported successful actual test4.
The force-next/spoof request chronology and the later normal NEXT recorded in
run033 are documented in the [experiment log](experiment-log.md#run033-force-next-and-spoof-requests).
