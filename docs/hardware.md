# Hardware

Disconnect USB and turn the variac off before moving any wire.

## Arduino Mega ADK and thermocouple amplifiers

Three Adafruit MAX31855 boards. Each: VIN → Arduino **5V**, GND → GND, and its own three
signal pins:

| Amplifier | CLK | DO | CS | Default role in the software |
|---|---|---|---|---|
| 1 | 22 | 24 | 26 | TC2 · barrier rear |
| 2 | 28 | 30 | 32 | TC1 · heater side (next to the cartridge) |
| 3 | 34 | 36 | 38 | TC3 · unused (hidden) |

The pin numbers are printed beside the big double header. The software never assumes which
probe is where: **Settings → Thermocouples** says which amplifier each TC is wired to, and
names it. If TC1 reads the wrong side, change it there (no rewiring needed).

The MAX31855 needs an ungrounded thermocouple. It cannot read the 8440T32 cartridge's
built-in (grounded) thermocouple: run 064 faulted as soon as the heater was powered.

## Relay (heater permission)

Relay module: **S → D33, + → 5V, − → GND.** The heater supply runs through COM and NC.

* COM–NC: heat flows when the relay coil is off. The firmware holds the coil on (heater off)
  whenever it is not heating. **Unplugged, rebooting or unflashed board = heater on.**
* COM–NO would be fail-safe (no heat unless the board asks). If you rewire to NO, set
  Settings → Board → Relay wiring to *COM–NO* (stored on the board).

The board only heats while the computer keeps renewing permission (every 0.5 s); if
`daq.py` stops, the board turns the heater off within 2 s. Program cutoffs are enforced by
the board itself and latch until *Clear cutoff*.

## Heater cartridges

| | 4877K305 (old, failed in run 040) | 8440T32 (current) |
|---|---|---|
| Rating | 300 W at 120 V | 500 W at 120 V, 4.17 A |
| At 100 V | 208 W | 347 W |
| Internal TC | no | grounded K: yellow +, red − (white leads = power) |
| Sheath limit | 760 °C | 760 °C; leads 249 °C |

Power scales with voltage squared; the page shows the full-power watts for the variac voltage
you type. When the external heater-side TC reads 700 °C the inside of the cartridge is far
hotter (see `analysis/README.md`, finding 5).

## Selec TC513 (optional, holds the cartridge's internal TC)

Terminals for the relay-output (A/AX) versions; check the label on yours:
supply **1 L / 2 N** (90–270 V AC; 24 V versions exist, check the label), thermocouple **6 + / 7 −**, relay **5 COM / 4 NO**.
In the run 068 wiring the D33 relay feeds both the TC513 supply and the heater, so the DAQ
can still switch everything off, and every relay pulse also restarts the TC513.

* The working setpoint is set from the normal display: hold **■** and press **▲/▼**.
  *SP.H* / *SP.L* in the menu are only the allowed range.
* In run 068 the TC513 switched the heater off once and never back on (the heater-side TC
  just cooled). Check its control mode and output before relying on it; the TC513 program
  preset waits on Full power until you press NEXT, so you can watch it work.

## Firmware

`firmware/che126_daq/che126_daq.ino` (compiled: `che126_daq.hex`). Upload from
**Settings → Board → Upload firmware**, or with the Arduino IDE (board *Arduino Mega or Mega
2560*). The previous EXP2–EXP8 firmware is in `archive/old-daq/`; this app does not work with
it.
