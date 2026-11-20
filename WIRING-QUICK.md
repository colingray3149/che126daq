# Quick wiring — EXP8 TC513 + Mega ADK MAX31855 channels

UNPLUG USB AND ALL OTHER POWER BEFORE CONNECTING OR MOVING WIRES.
Keep heater power OFF. This applies to Adafruit MAX31855 breakouts with regulator and level shifting, not unidentified modules.

## Each wire, end to end

```text
AMPLIFIER 1                         ARDUINO MEGA ADK
-----------                         ----------------
VIN   ----------------------------> 5V   (NOT Arduino VIN)
GND   ----------------------------> GND
CLK   ----------------------------> 22
DO / SO / SDO ---------------------> 24
CS    ----------------------------> 26

AMPLIFIER 2                         ARDUINO MEGA ADK
-----------                         ----------------
VIN   ----------------------------> 5V   (NOT Arduino VIN)
GND   ----------------------------> GND
CLK   ----------------------------> 28
DO / SO / SDO ---------------------> 30
CS    ----------------------------> 32

AMPLIFIER 3 — FORMER INTERNAL TC; UNUSED/UNPLUGGED IN EXP8
-----------------------------------------------------------  ----------------
VIN   ----------------------------> 5V   (NOT Arduino VIN)
GND   ----------------------------> GND
CLK   ----------------------------> 34
DO / SO / SDO ---------------------> 36
CS    ----------------------------> 38
```

For **experiment 2**, amplifier **1 / TC1** measures the cartridge heater; amplifier **2 / TC2** measures the opposite face of the barrier. Identify the amplifier by its signal pin connections, not the probe's appearance.

**EXP8:** raw **TC2** controls continuous heat to 100°C and the 90-second ramp to
200°C; raw **TC1** is rear protection. After 200°C, D33 permission stays ON and a
**Selec TC513**, not the DAQ, regulates the internal K thermocouple at its manual
650°C setpoint. Select `external_channel = 2`, `feedback_channel = 2` (intentional
EXP8 alias), and `rear_channel = 1`. TC2's 730°C cutoff is external-only. Former
TC3 is unused/unplugged and is not a fallback. EXP7 retains its distinct 2/3/1
mapping; EXP2 retains 1/2 and EXP3–6 retain 2/1.

The McMaster **8440T32** print confirms a **grounded K** sensor: **yellow → TC513
6 TC+**, **red → TC513 7 TC−**. Its two white leads are heater power, never TC
leads. Do not connect this internal probe to a MAX31855 and do not install the
failed 47 kΩ negative-to-ground resistor. The TC513 manual does not explicitly
prove grounded-input compatibility; no isolation or leakage fix is claimed.
Retain protective earth; the variac is not isolation.

**Match the exact TC513 rear model/supply/output label before using this conditional
A/AX map:** supply **1 L / 2 N**; TC **6+ / 7−**; A relay **4 NO / 5 COM**; AX
relay **3 NC / 4 NO / 5 COM**; selected SSR drive **10+ / 12−**. SSR and relay are
different outputs, not simultaneous contacts. BX/other/24 V variants can differ.
A 24 V unit must **never** receive 100 V. The manual's mains variant accepts
100 V within its published range, but the physical nameplate is decisive.

For the **requested common-OFF topology**, the D33 COM–NC permission contact is in
the switched live feed **before both** the TC513 supply branch and the separate
fused heater-load branch. TC513 1/2 receives controller power only; the heater
load goes through the TC513 NO output and the manual-required interposing
relay/contactor. Final OFF therefore removes both controller and heater power;
TC2 lower-stage pulses can reboot the controller. The alternative fixed-supply
arrangement leaves TC513 1/2 powered and puts D33 permission only in the heater
branch. Both require D33 permission **and** the TC513 output for heat. The manual
requires an interposer and separate fused load despite the 10 A contact rating;
the direct-contact existing-hardware fallback and its deviation are explicit in
the full guide. COM–NC can fail permission ON on reset/power loss.

See [EXP8 wiring, auto-tune with START/NEXT/BOOST_FINAL, key icons, and lessons](docs/experiment8.md).
Do not press the second NEXT during auto-tune: in the actual run it is reserved
for observed TC513 PV =650°C and starts the 90-second timer.

## Experiment 2 relay module

With **all power disconnected**: module **+ → Mega 5V**, **− → Mega GND**, **S → D33** (the odd-numbered pin beside TC2's D32). This assumes the verified 5V, active-HIGH module profile used by the EXP2 firmware; check its switching behavior with the variac unplugged before connecting heater power.

The requested **COM–NC** contact wiring passes heater power when the coil is unpowered. For that profile, the firmware commands **D33 HIGH to cut heat**, **LOW to request heat**. **NC is not fail-safe: losing Arduino/relay power or resetting the board can turn the heater ON.** A separate independent high-limit disconnect is required; COM–NO is the recommended fail-off contact choice and needs the matching firmware profile.

Voltage is set/measured manually at the heater: the earlier EXP2 preset was 30V RMS; EXP3 requests 65V RMS, recorded in `experiment3.toml`. The Arduino does not set or measure it, and no 65V tuning validation is claimed. No AC conductor or relay contact connects to Arduino GND. Protective earth is not the heater's neutral/return. Keep mains terminals enclosed and dry.

EXP8 defaults are a 100 V manual variac preset, external TC2 100°C entry and
90-second ramp to 200°C, manual TC513 650°C setpoint and 90-second final hold,
730°C **external** cutoff, and 120°C rear cutoff. `target_C = 650` is TC513
metadata, not an automatic DAQ measurement. `start exp8` applies the selected
configuration; connecting USB alone never starts heating. The first NEXT advances
entry/wait; the second NEXT in BOOST_FINAL at observed PV=650 starts the hold;
all other NEXT commands are acknowledged no-ops.

## Where the signal holes are

Orient the Arduino with its USB connectors to the LEFT and its big double-row header to the RIGHT. The inner column, closer to the main processor, is the EVEN-numbered column.

```text
       BIG DOUBLE-ROW HEADER — TOP SECTION
       Inner / toward CPU       Outer / board edge

                 5V   o     o   5V      <-- POWER ROW, not pin 22
   Amp 1 CLK --> 22   o     o   23
   Amp 1 DO  --> 24   o     o   25
   Amp 1 CS  --> 26   o     o   27
   Amp 2 CLK --> 28   o     o   29
   Amp 2 DO  --> 30   o     o   31
   Amp 2 CS  --> 32   o     o   33
   Amp 3 CLK --> 34   o     o   35
   Amp 3 DO  --> 36   o     o   37
   Amp 3 CS  --> 38   o     o   39
                 ... continues down to 52 / 53 ...
```

Follow the printed numbers on YOUR board. “D22” means the hole labeled “22”. Do not use A1/A2. All three amplifiers share electrical 5V and ground, but each has separate signal wires.

## Connection order

1. Disconnect Arduino USB, barrel/external power, and any amplifier supply. Heater power stays off.
2. Connect GND on all amplifiers first.
3. Connect CLK, DO, and CS using the diagram.
4. Connect all amplifier VIN wires to Arduino 5V, still unpowered.
5. Inspect both ends for swapped labels, offsets, shorts and loose connections.
6. Plug Arduino USB in LAST so Arduino and amplifiers power up together.
7. Before changing anything: unplug USB and every other power source FIRST.

Thermocouples can stay disconnected. Do NOT leave the Arduino powered while wiring an unpowered amplifier. Do NOT connect these wires to mains or heater power.

Current logger pin map: TC1 CLK/DO/CS = 22/24/26; TC2 = 28/30/32; TC3 = 34/36/38. The old tc_diag sketch uses a different map and must not be uploaded assuming this wiring.

More detail and sources: [docs/wiring.md](docs/wiring.md).
