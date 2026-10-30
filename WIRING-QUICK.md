# Quick wiring — Arduino Mega ADK + two Adafruit MAX31855 breakouts

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
```

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
                 ... continues down to 52 / 53 ...
```

Follow the printed numbers on YOUR board. “D22” in code means the hole labeled “22”; there need not be a printed “D”. Do not use A1 or A2. Both amplifiers use the same electrical 5V and ground rails, but their three signal wires are separate.

## Connection order

1. Disconnect Arduino USB, barrel/external power, and any amplifier supply. Heater power stays off.
2. Connect GND on BOTH amplifiers first.
3. Connect CLK, DO, and CS on BOTH amplifiers using the diagram.
4. Connect VIN on BOTH amplifiers to Arduino 5V, still with USB unplugged.
5. Inspect both ends of every wire for swapped labels, one-hole offsets, shorts, or loose connections.
6. Plug Arduino USB in LAST. Arduino and both amplifiers then power up together.
7. Before changing anything: unplug USB and every other power source FIRST.

Thermocouples can stay disconnected. Do NOT leave the Arduino powered while wiring an unpowered amplifier. Do NOT connect these wires to mains or heater power.

This pin map matches the latest saved thermocouple_logger sketch: TC1 CLK/DO/CS = 22/24/26; TC2 = 28/30/32. The old tc_diag sketch uses a different map and must not be uploaded assuming this wiring.

More detail and sources: [docs/wiring.md](docs/wiring.md).
