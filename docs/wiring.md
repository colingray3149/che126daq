# Wiring: Mega ADK + two Adafruit MAX31855 breakouts

## Scope and evidence

- USB identification on 2026-10-30: **Arduino Mega ADK**, `/dev/ttyACM0`, FQBN `arduino:avr:megaADK`, VID:PID `2341:0044`. Port names can change after replugging. Raw identification: `../provenance/hardware/board-list-2026-10-30.json`.
- Amplifier identity comes from the user's 2026-10-26 Claude conversation: **Adafruit MAX31855 K-type breakout**, not an analog AD8495 and not MAX31856. Physical amplifier labels/revision and present jumper placement have not been visually inspected this session.
- The table below matches the current saved logger's pin constants and `tc_fault`. It is not a claim that the present wires or loaded firmware bytes have been verified.

## Connections

| Breakout label | Amplifier 1 / TC1 | Amplifier 2 / TC2 |
|---|---|---|
| `VIN` / `Vin` | Arduino **5V** | Arduino **5V** |
| `GND` | Arduino **GND** | Arduino **GND** |
| `CLK` | Digital **22** | Digital **28** |
| `DO` / `SO` / `SDO` | Digital **24** | Digital **30** |
| `CS` | Digital **26** | Digital **32** |

Five wires per amplifier. Each signal has its own Arduino pin; both amplifiers still share the Arduino's electrical 5V and ground rails. Use separate available 5V/GND header sockets or a sound distribution rail, not two loose wires jammed into one socket.

For **EXP2**, TC1 is the heater-side probe and TC2 is the opposite barrier face. Relay module S uses **D33**, + uses 5V and − uses GND under the documented 5V active-HIGH profile. The requested COM–NC power contacts mean HIGH cuts commanded heat and LOW permits it; losing Arduino/coil power can turn the heater ON. See [EXP2 operation](exp2.md) for wiring, polarity verification and independent cutoff requirements.

For **EXP3**, the operator-reported reversed physical placement is handled by
`swap_inputs = true`: amplifier 2/raw TC2 is heater feedback, amplifier 1/raw TC1
is the rear cutoff input. Pin wiring and raw CSV order stay unchanged.
The logical plot labels show each raw source explicitly. Firmware/host v4 was
deployed after run 017 finished. `start exp3` applies the corrected control
mapping; changing the display alone never changes controller inputs.

Prepared EXP4 uses the same default swapped wiring with both probes required;
its 100 V/700°C program is code-only and is not cleared for this assembly.
See [EXP4 limits](exp2.md#exp4-staged-100-v-program--prepared-not-deployed) before
any hardware cutover. No reset/upload was performed during its implementation.

`D22` means the hole labeled **22**, not a literal label “D22”. With USB connectors to the left and the large double-row header on the right, **22, 24, 26, 28, 30, 32 are consecutive holes down the inner/even column**, nearest the main processor. The header's top power row is **5V**, not 22. Follow the silkscreen numbers; do not count blindly. See `../references/hardware/mega-adk-front.jpg` and the OEM schematic.

These are software-SPI digital connections. **Do not use A1/A2** for this setup. Do not confuse breakout `VIN` (which accepts regulated 5V on this Adafruit board) with Arduino `VIN` (external supply input). Do not connect either breakout to Arduino VIN, a heater supply, mains, or a 3Vo/regulator-output pin.

## Safe wiring / power order

**Do not rewire a powered board. “Power last” means USB/external power last for the entire circuit, not leaving the Arduino on while an amplifier has its VIN disconnected.** Powered CLK/CS lines can inject current into an unpowered device; the bare MAX31855 limits pin voltage to VCC + 0.3V.

1. Turn off and disconnect heater power. Unplug Arduino USB, barrel supply, and any independent amplifier supply. Verify there is no other power source. Let any hot parts cool before handling.
2. With everything unpowered, connect **GND on both amplifiers first**.
3. Connect each amplifier's **CLK, DO, CS** using the table. Check the labels at both ends. Do not use the older shared-pin or odd-numbered-pin plans from the historical conversation.
4. Connect **both amplifier VIN wires to Arduino 5V**. These connections are still unpowered. If connecting thermocouples later, secure each lead in the breakout's marked `+`/`−` terminals while power is off; use the probe documentation for polarity, not wire color alone. They may remain disconnected now.
5. Inspect for a one-hole offset, swapped VIN/GND, exposed strands, loose headers, and shorts. A continuity/short check is useful when available.
6. **Plug Arduino USB in last**. For the documented USB-powered arrangement, the Arduino and both breakouts then receive power together. Do not introduce separate amplifier supplies as part of this reconnect.
7. For changes or disconnection, **unplug USB and every other supply first**, then move wires. If removing individual jumper wires afterward, ground can be removed last. Disconnect immediately if a board heats unexpectedly, smells, or the USB connection repeatedly drops.

This is a conservative connection procedure, not a guarantee against wiring faults. The 5V recommendation applies to the **Adafruit breakout with its 3.3V regulator and level shifting**. A bare MAX31855 or an unknown clone is not 5V-compatible by assumption: its chip operating VCC is 3.0–3.6V. Stop if the physical boards do not match this documented hardware.

## What an unplugged probe should mean

A responding MAX31855 with an open thermocouple normally sets its open-circuit fault; the Adafruit library returns `nan` and the plot displays `fault`. An all-zero serial temperature is **not a valid connection check**: zero-valued frames may also occur with an unresponsive/miswired interface, and the imported code does not reject all-zero frames.

On 2026-10-30, a roughly five-second read at 115200 baud produced the expected CSV header but repeated `0.00,0.00`, with no thermocouples connected according to the user. Raw capture: `../provenance/hardware/serial-observation-2026-10-30.txt`. This does not identify the cause or prove a failed amplifier. No upload, rewiring, or temperature validation was performed.

## Firmware variants: do not mix these pin maps

- `thermocouple_logger`: table above; 115200 baud; three CSV columns plus `#CTRL` EXP2 telemetry; nominal 500 ms sampling and explicit serial-command control on D33.
- `tc_fault`: same current pin map; human-readable fault bits and cold-junction temperatures, **not CSV** for `host/plot.py`.
- `tc_diag`: **historical shared-clock diagnostic**, CLK 22, CS 26/28, DO 24/30. It does **not** match the current TC2 28/30/32 wiring. Preserved unchanged for provenance; do not upload it assuming the current table applies.
- Earlier AD8495/A1/A2 and shared-clock/data snapshots are historical, not alternative instructions.

## Primary sources

- [Adafruit MAX31855 product 269](https://www.adafruit.com/product/269): regulator, level shifting, 3.3–5V supply/logic compatibility.
- [Adafruit Arduino wiring](https://learn.adafruit.com/thermocouple/arduino-code): VIN/GND and digital CLK/DO/CS definitions; grounded thermocouples are not supported. Verify electrical isolation of the thermocouple junction from any grounded heater/fixture; do not defeat protective earthing to solve a sensor fault.
- [Arduino Mega ADK documentation source](https://raw.githubusercontent.com/arduino/docs-content/main/content/retired/01.boards/arduino-mega-adk-rev3/content.md): USB power, 5V/GND/VIN definitions, 5V digital I/O. Local copy in `references/hardware`.
- [Arduino OEM schematic](https://www.arduino.cc/en/uploads/Main/arduino-mega-adk-schematic.pdf): header mapping. Local PDF in `references/hardware`.
- [MAX31855 datasheet](https://cdn-shop.adafruit.com/datasheets/MAX31855.pdf), electrical characteristics and absolute maximum ratings: local `../references/datasheets/MAX31855.pdf`.
