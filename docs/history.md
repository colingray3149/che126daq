# History of the rig (Oct 30 – Nov 16, 2026)

Facts only, from the run data, event logs and what Colin said at the time. TC1 means the
heater-side thermocouple and TC2 the barrier-rear one in every run (the earlier software
called them raw TC2 and raw TC1).

## Goal and plan (Oct 30)

* Compare barrier stacks between a cartridge heater and a battery-side face: the heater pressed
  against layer 1, a thermocouple wired to each face, specimens cut 2 in × 6 in and clamped.
  Planned stacks: mica / basalt fabric / aluminum, mica / basalt / aerogel / aluminum,
  mica / aerogel / aluminum, repeated for consistency. The aerogel never arrived.
* Eventually pack everything in semi-wet sand (QUIKRETE) in a cinder block and hold a
  temperature for about 30 minutes. The early tests leaned the cartridge against the block.
* The battery (Samsung 25R 18650) was described as "kinda cosmetic"; no run records one in the stack.

## Oct 30 — commissioning (runs 001–006)

* Arduino Mega ADK with two Adafruit MAX31855 amplifiers (pins 22/24/26 and 28/30/32), logging only.
* Runs 001–005: amplifiers connected, thermocouples mostly unreadable (NaN).
* Run 006: first heat. 1 mica sheet, cartridge leaned on the block, voltage set by hand on the
  variac. One channel peaked 261 °C, the other 220 °C ten seconds later: one mica layer slowed
  the heat very little.

## Nov 2 — relay control, EXP2 (runs 007–015)

* Songle SRD-05VDC-SL-C relay module on D33, heater wired through **COM–NC** (Colin's choice): the
  board energises the coil to cut heat, so a dead or resetting board means heat on.
* EXP2 firmware: hold the heater side at 300 °C with predictive on/off control, cut and latch if
  TC2 passes 140 °C, started by typing `start exp2`. Variac at 30 V.
* Colin asked to remove the start preconditions the assistant had added ("i can read a graph and
  know when to start an experiment") and for an editable config file.
* Run 009: TC2 jumped past 140 °C in 4.5 s and tripped. The probes were the other way round from
  the software's assumption (TC2 was on the heater).
* Run 011: control check with one thermocouple; the plan was to test with a heat gun.
* Colin: "we didn't get to do a run, we were having too many thermocouple issues."

## Nov 6 — first tests (runs 016–026)

* Run 017, **test 1**: 1 mica / 2 basalt fabric / 1 aluminum. Probes still reversed, so the 85 °C
  rear cutoff watched the heater side and ended heating at 3:10. Colin: "first successful run".
  The software then gained a swapped-input mapping (EXP3).
* Run 023, **test 2** (EXP3): same stack, hold 300 °C at about 70 V (65 V preset). Held
  299.0 ± 2.4 °C for 20 minutes; the rear reached 84 °C and was still rising. Colin: "successful".
* EXP4: 100 V; full power to 100 °C, hold, `next`, 90 s ramp to 200 °C, full power to 700 °C (Colin
  first asked for 800 °C and changed to 700 °C after the 760 °C cartridge rating came up), hold until
  the rear hits 85 °C.
* Run 026, **test 3**: 707 °C; the 85 °C rear cutoff tripped at 9:18 and the rear kept rising to
  110.5 °C. During the run Colin could not send `next` (the software required 95–105 °C while the
  heater side sat at 116 °C) and asked to remove the 85 °C limit live; neither was done.

## Nov 9 — EXP5 (runs 027–033)

* EXP5 = EXP4 but stop 60 s after first reading 700 °C; rear cutoff raised to 120 °C.
* Before run 028 the heater was powered when the variac was switched on, before any start
  command (run 027 shows the heater side climbing from 50 to 73 °C while idle): the COM–NC relay
  passes heat whenever the board is not holding it off.
* Run 028, **test 4**: the cleanest full profile. 700 °C at 4:28, 60 s hold, heat off, rear peak
  83.5 °C seven minutes later. Colin: "it went well".
* Runs 030 and 033: the same program tripped the 120 °C rear cutoff (rear rose 2–3× faster). In
  033 `next` was refused for minutes (heater side 156 °C, outside the 95–105 °C window); Colin:
  "this experiment hinges on it, I don't know why you added guardrails".
* The stack for 026–033 was not recorded.

## Nov 13 — EXP6, fine sand, the cartridge dies (runs 034–059)

* Fine, less rocky sand from run 034. EXP6 = EXP5 with `next` allowed at any temperature.
* Run 036, **test 5**: 1 mica / 2 fiberglass heat-barrier strip (McMaster 4234N12) / 1 aluminum.
  700 °C at 4:08, hold done, rear peak 80.3 °C.
* Run 040, **test 6**: 1 mica / 3 ceramic fiber pipe insulation (87575K35) / 1 aluminum. 700 °C at
  5:47, hold done, rear peak 113.3 °C. A re-heat in the hold did nothing: the 300 W cartridge had
  failed (open circuit; about 108 V measured across it with no heating).
* Runs 044–059: aluminum-only control attempts with the dead cartridge; nothing heated.

## Nov 16 — new cartridge, internal TC, TC513 (runs 060–068)

* New cartridge (McMaster 8440T32, 500 W at 120 V, grounded internal K thermocouple). Third
  amplifier added on pins 34/36/38 for the internal TC (EXP7: control on the internal TC).
* Runs 060–065: the internal TC read choppy, worse when the heater circuit was powered. Run 064
  (EXP7) tripped on a sensor fault 0.7 s after heat on. A 47 kΩ resistor from TC− to ground did
  not help. The MAX31855 cannot read a grounded junction reliably here.
* EXP8: a Selec TC513 reads the internal TC and switches the heater with setpoint 650 °C; the D33
  relay feeds both the TC513 and the heater; the DAQ controls on the external TC up to 200 °C,
  then leaves the relay on; Colin presses `next` when the TC513 shows 650 °C to start a 90 s hold.
  The TC513 had been used by someone else; auto-tune could not be reached and was skipped. *SP.H*
  (setpoint limit) was set to 650 before the actual setpoint was found (■ + ▲).
* Run 068: full power to 100 °C coasted to 187 °C. The first `next` started the ramp, but its
  setpoint began at 100 °C while TC1 read ~170 °C, so nothing heated for 55 s (it looked like
  `next` failed). After 200 °C the external TC peaked 419 °C, then cooled for 12 minutes with the
  relay on. Colin: the TC513 was configured wrong and did not hold. The 90 s hold never started.

## Nov 20 — this software

The EXP2–EXP8 firmware and host were replaced by `daq.py` and the che126-daq firmware (old code in
`archive/old-daq/`). What changed because of the history above:

* NEXT, Stop and manual control always act; no temperature windows or start preconditions.
* Ramps start from the current reading (run 068).
* Cutoffs are per program and editable; the board enforces them.
* The board turns heat off if the computer stops talking (lease), and the page warns that COM–NC
  means heat whenever the board is unpowered.
* Predicted runs show coast-overshoot before heating (run 068: 100 → 187 °C).
* Every run asks for the setup, because five of the key runs have no recorded stack.
