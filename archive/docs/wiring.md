# Wiring: EXP8 Selec TC513 + Mega ADK MAX31855 channels

## Scope and evidence

- USB identification on 2026-10-30: **Arduino Mega ADK**, `/dev/ttyACM0`, FQBN `arduino:avr:megaADK`, VID:PID `2341:0044`. Port names can change after replugging. Raw identification: `../provenance/hardware/board-list-2026-10-30.json`.
- Amplifier identity comes from the user's 2026-10-26 Claude conversation: **Adafruit MAX31855 K-type breakout**, not an analog AD8495 and not MAX31856. Physical amplifier labels/revision and present jumper placement have not been visually inspected this session.
- The table below matches the current saved logger's pin constants and `tc_fault`. It is not a claim that the present wires or loaded firmware bytes have been verified.

## Connections

| Breakout label | Amplifier 1 / TC1 | Amplifier 2 / TC2 | Former amplifier 3 / TC3 (EXP8 unused) |
|---|---|---|---|
| `VIN` / `Vin` | Arduino **5V** | Arduino **5V** | Arduino **5V** |
| `GND` | Arduino **GND** | Arduino **GND** | Arduino **GND** |
| `CLK` | Digital **22** | Digital **28** | Digital **34** |
| `DO` / `SO` / `SDO` | Digital **24** | Digital **30** | Digital **36** |
| `CS` | Digital **26** | Digital **32** | Digital **38** |

Five wires per installed amplifier. TC1/TC2 share regulated 5V and ground; use a
sound distribution rail where needed. **EXP8 leaves former TC3 unused/unplugged.**
The internal 8440T32 thermocouple connects only to the TC513: yellow to terminal
**6 TC+**, red to **7 TC−**. Its white heater-power leads never connect to any
thermocouple or Arduino terminal.

For **EXP2**, TC1 is the heater-side probe and TC2 is the opposite barrier face. Relay module S uses **D33**, + uses 5V and − uses GND under the documented 5V active-HIGH profile. The requested COM–NC power contacts mean HIGH cuts commanded heat and LOW permits it; losing Arduino/coil power can turn the heater ON. See [EXP2 operation](exp2.md) for wiring, polarity verification and independent cutoff requirements.

For **EXP3–6**, `feedback_channel = 2`, `rear_channel = 1` preserves the
operator-reported reversed placement. EXP7 retains distinct external/internal/rear
channels 2/3/1. **EXP8 uses external/feedback 2/2 intentionally and rear 1:** TC2
controls entry/ramp and the external 730°C cutoff; TC1 is rear protection; a Selec
TC513 independently regulates the internal K sensor after TC2 reaches 200°C.
No required source falls back, and there is no internal DAQ high limit or
automatic 650°C measurement. The logical plots identify raw sources; EXP8 hides
unused TC3 while retaining its raw CSV column.

**TC513 variant and load wiring:** the complete [EXP8 hardware guide](experiment8.md)
contains the rendered-manual terminal map, requested common-OFF power diagram,
fixed-controller-supply alternative, truth table, interposer requirement, and
actual auto-tune procedure. In short, documented A/AX supply is 1/2, TC is 6+/7−,
A relay is 4 NO/5 COM, AX relay is 3 NC/4 NO/5 COM, and SSR drive is 10+/12−.
Match the exact rear label instead: other/BX/24 V variants can differ, and 24 V
must never receive 100 V. The requested arrangement places D33 COM–NC permission
before both TC513 supply and the separate fused heater branch so final OFF removes
both. The manufacturer requires an interposing relay/contactor despite the 10 A
rating. COM–NC can fail permission ON on reset/power loss.

**Grounded-probe limitation:** the archived 8440T32 PDF confirms a grounded K
junction, 760°C sheath exposure and **249°C (480°F)** wire-lead exposure. The
TC513 manual lists K input but does not explicitly establish grounded-junction
compatibility. Do not connect that probe to a MAX31855, do not reinstall the
failed 47 kΩ negative-to-ground resistor, and do not claim an isolation/leakage
fix. Retain protective earth; the variac is not isolation.

The following deployment notes describe earlier EXP4 hardware, not the new
cartridge's rating. The NC relay on D33 still can fail ON during reset or loss
of Arduino/coil power. The three new signals continue down the same even-numbered
header column: follow labels **34, 36, 38**, not hole counting.

`D22` means the hole labeled **22**, not a literal label “D22”. With USB connectors to the left and the large double-row header on the right, **22, 24, 26, 28, 30, 32 are consecutive holes down the inner/even column**, nearest the main processor. The header's top power row is **5V**, not 22. Follow the silkscreen numbers; do not count blindly. See `../references/hardware/mega-adk-front.jpg` and the OEM schematic.

These are software-SPI digital connections. **Do not use A1/A2** for this setup. Do not confuse breakout `VIN` (which accepts regulated 5V on this Adafruit board) with Arduino `VIN` (external supply input). Do not connect either breakout to Arduino VIN, a heater supply, mains, or a 3Vo/regulator-output pin.

## Safe wiring / power order

**Do not rewire a powered board. “Power last” means USB/external power last for the entire circuit, not leaving the Arduino on while an amplifier has its VIN disconnected.** Powered CLK/CS lines can inject current into an unpowered device; the bare MAX31855 limits pin voltage to VCC + 0.3V.

1. Turn off and disconnect heater power. Unplug Arduino USB, barrel supply, and any independent amplifier supply. Verify there is no other power source. Let any hot parts cool before handling.
2. With everything unpowered, connect **GND on all amplifiers first**.
3. Connect each amplifier's **CLK, DO, CS** using the table. Check the labels at both ends.
4. Connect amplifier VIN wires to regulated Arduino 5V. Secure thermocouple leads in marked +/− terminals; TC3 may remain open until its probe is connected.
5. Inspect for offsets, swapped VIN/GND, exposed strands, loose headers and shorts.
6. Plug Arduino USB in last; Arduino and all breakouts then power up together.
7. For changes or disconnection, **unplug USB and every other supply first**, then move wires. If removing individual jumper wires afterward, ground can be removed last. Disconnect immediately if a board heats unexpectedly, smells, or the USB connection repeatedly drops.

This is a conservative connection procedure, not a guarantee against wiring faults. The 5V recommendation applies to the **Adafruit breakout with its 3.3V regulator and level shifting**. A bare MAX31855 or an unknown clone is not 5V-compatible by assumption: its chip operating VCC is 3.0–3.6V. Stop if the physical boards do not match this documented hardware.

## What an unplugged probe should mean

A responding MAX31855 with an open thermocouple normally sets its open-circuit fault; the Adafruit library returns `nan` and the plot displays `fault`. An all-zero serial temperature is **not a valid connection check**: zero-valued frames may also occur with an unresponsive/miswired interface, and the imported code does not reject all-zero frames.

On 2026-10-30, a roughly five-second read at 115200 baud produced the expected CSV header but repeated `0.00,0.00`, with no thermocouples connected according to the user. Raw capture: `../provenance/hardware/serial-observation-2026-10-30.txt`. This does not identify the cause or prove a failed amplifier. No upload, rewiring, or temperature validation was performed.

## Firmware variants: do not mix these pin maps

- `thermocouple_logger`: table above; 115200 baud; four CSV columns `time_s,t1_C,t2_C,t3_C` plus `#CTRL` v6 telemetry; nominal 500 ms sampling, EXP2–8 board-local control on D33. EXP8 retains but does not use TC3.
- `tc_fault`: same current pin map; human-readable fault bits and cold-junction temperatures, **not CSV** for `host/plot.py`.
- `tc_diag`: **historical shared-clock diagnostic**, CLK 22, CS 26/28, DO 24/30. It does **not** match the current TC2 28/30/32 wiring. Preserved unchanged for provenance; do not upload it assuming the current table applies.
- Earlier AD8495/A1/A2 and shared-clock/data snapshots are historical, not alternative instructions.

## Primary sources

- [Adafruit MAX31855 product 269](https://www.adafruit.com/product/269): regulator, level shifting, 3.3–5V supply/logic compatibility.
- [Adafruit Arduino wiring](https://learn.adafruit.com/thermocouple/arduino-code): VIN/GND and digital CLK/DO/CS definitions; grounded thermocouples are not supported. Verify electrical isolation of the thermocouple junction from any grounded heater/fixture; do not defeat protective earthing to solve a sensor fault.
- [Arduino Mega ADK documentation source](https://raw.githubusercontent.com/arduino/docs-content/main/content/retired/01.boards/arduino-mega-adk-rev3/content.md): USB power, 5V/GND/VIN definitions, 5V digital I/O. Local copy in `references/hardware`.
- [Arduino OEM schematic](https://www.arduino.cc/en/uploads/Main/arduino-mega-adk-schematic.pdf): header mapping. Local PDF in `references/hardware`.
- [MAX31855 datasheet](https://cdn-shop.adafruit.com/datasheets/MAX31855.pdf), electrical characteristics and absolute maximum ratings: local `../references/datasheets/MAX31855.pdf`.
- [Selec OP292-V04 instructions](../references/datasheets/Selec-TC513-Manual.pdf), [OP292-V05 instructions](../references/datasheets/Selec-TC513-TC203-TC303-Manual.pdf), and [manufacturer TC513AX datasheet](../references/datasheets/Selec-TC513AX-Datasheet.pdf): conditional terminal maps, supply variants, load connections, keys, menus and auto-tune. The terminal numbers were checked against rendered PDF images.
- [McMaster 8440T32 exact product print](../references/datasheets/McMaster-8440T32-Internal-Thermocouple-Heater.pdf): grounded K sensor, yellow/red polarity, 500 W/120 V, 760°C sheath and 249°C wire leads.
- [Complete EXP8 hardware and operating guide](experiment8.md).
