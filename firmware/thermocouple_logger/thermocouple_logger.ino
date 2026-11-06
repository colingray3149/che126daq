// CHE126 experiments 2/3/4: two MAX31855s plus an active-HIGH relay on D33.
// TC1 CLK/DO/CS = D22/D24/D26; TC2 = D28/D30/D32. CSV remains raw physical
// channels time_s,t1_C,t2_C at 115200 baud, with one #CTRL JSON line per sample.
//
// The user-selected COM-NC contact passes heater power when the coil is
// de-energized. D33 HIGH energizes the module and opens the contact (OFF);
// D33 LOW de-energizes it and closes the contact (ON). NC FAILS ON when
// Arduino power is lost or its pin floats during reset. The software latch
// and watchdog are not power-independent or hardware fail-safe protection.

#include <Adafruit_MAX31855.h>
#include <stdint.h>
#if defined(__AVR__)
#include <avr/wdt.h>
#endif
#include "exp2_controller.h"

const uint8_t PIN_CLK1 = 22, PIN_DO1 = 24, PIN_CS1 = 26;
const uint8_t PIN_CLK2 = 28, PIN_DO2 = 30, PIN_CS2 = 32;
const uint8_t PIN_RELAY = 33;
const uint8_t RELAY_OFF = HIGH;
const uint8_t RELAY_ON = LOW;
const uint32_t PERIOD_MS = 500;
const uint8_t COMMAND_CAPACITY = 192;
const uint8_t SERIAL_BUDGET_BYTES = 48;

Adafruit_MAX31855 tc1(PIN_CLK1, PIN_CS1, PIN_DO1);
Adafruit_MAX31855 tc2(PIN_CLK2, PIN_CS2, PIN_DO2);
che126_exp2::Controller controller;

char command_line[COMMAND_CAPACITY];
uint8_t command_length = 0;
bool discarding_command = false;
bool applied_heater_on = false;
uint32_t next_sample_ms = 0;

void applyHeater() {
  const bool on = controller.heaterOn();
  if (on == applied_heater_on) return;
  applied_heater_on = on;
  digitalWrite(PIN_RELAY, on ? RELAY_ON : RELAY_OFF);
}

void printDurationSeconds(uint32_t milliseconds) {
  Serial.print((unsigned long)(milliseconds / 1000UL));
  Serial.print('.');
  const uint32_t fraction = milliseconds % 1000UL;
  if (fraction < 100) Serial.print('0');
  if (fraction < 10) Serial.print('0');
  Serial.print((unsigned long)fraction);
}

void emitTelemetry() {
  const che126_exp2::Settings &settings = controller.settings();
  Serial.print(F("#CTRL {\"protocol\":\"exp2-v5\",\"program\":\""));
  Serial.print(controller.programName(controller.program()));
  Serial.print(F("\",\"phase\":\""));
  Serial.print(controller.phaseName(controller.phase()));
  Serial.print(F("\",\"state\":\""));
  Serial.print(controller.stateName(controller.state()));
  Serial.print(F("\",\"reason\":\""));
  Serial.print(controller.reason());
  Serial.print(F("\",\"heater_on\":"));
  Serial.print(controller.heaterOn() ? F("true") : F("false"));
  Serial.print(F(",\"setpoint_C\":"));
  Serial.print(controller.setpointC(), 3);
  Serial.print(F(",\"slope_C_per_s\":"));
  Serial.print(controller.slopeCPerSecond(), 6);
  Serial.print(F(",\"tc2_required\":"));
  Serial.print(controller.tc2Required() ? F("true") : F("false"));
  Serial.print(F(",\"relay_contact\":\"NC\","));
  Serial.print(F("\"active_high\":true,\"hold_s\":"));
  Serial.print((unsigned long)controller.holdSeconds());
  Serial.print(F(",\"request_id\":"));
  Serial.print((unsigned long)controller.requestId());
  Serial.print(F(",\"command_ok\":"));
  Serial.print(controller.commandOk() ? F("true") : F("false"));
  Serial.print(F(",\"settings\":{\"target_C\":"));
  Serial.print(settings.target_c, 3);
  Serial.print(F(",\"hysteresis_C\":"));
  Serial.print(settings.hysteresis_c, 3);
  Serial.print(F(",\"tc1_cutoff_C\":"));
  Serial.print(settings.tc1_cutoff_c, 3);
  Serial.print(F(",\"tc2_cutoff_C\":"));
  Serial.print(settings.tc2_cutoff_c, 3);
  Serial.print(F(",\"tc2_cutoff_enabled\":"));
  Serial.print(settings.tc2_cutoff_enabled ? F("true") : F("false"));
  Serial.print(F(",\"prediction_lead_s\":"));
  printDurationSeconds(settings.prediction_lead_ms);
  Serial.print(F(",\"min_off_s\":"));
  printDurationSeconds(settings.min_off_ms);
  Serial.print(F(",\"hold_band_C\":"));
  Serial.print(settings.hold_band_c, 3);
  Serial.print(F(",\"hold_s\":"));
  printDurationSeconds(settings.hold_duration_ms);
  Serial.print(F(",\"swap_inputs\":"));
  Serial.print(settings.swap_inputs ? F("true") : F("false"));
  Serial.println(F("}}"));
}

void processCommandLine() {
  if (command_length > 0 && command_line[command_length - 1] == '\r') {
    command_line[--command_length] = '\0';
  }
  const bool emit_ack = controller.handleCommand(command_line, millis());
  applyHeater();  // STOP/trips always reach the pin before acknowledgement.
  if (emit_ack) emitTelemetry();
  command_length = 0;
  command_line[0] = '\0';
}

void pollSerial() {
  // Bound work per loop so input flooding cannot starve interlocks/watchdog.
  uint8_t budget = SERIAL_BUDGET_BYTES;
  while (budget-- > 0 && Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\n') {
      if (discarding_command) {
        // Overlong or nonprintable input is rejected, never a truncated START.
        command_line[0] = '\0';
        command_length = 0;
        discarding_command = false;
        const bool emit_ack = controller.handleCommand(command_line, millis());
        applyHeater();
        if (emit_ack) emitTelemetry();
      } else {
        processCommandLine();
      }
      continue;
    }
    if (discarding_command) continue;
    // Only printable ASCII plus an optional trailing CR is accepted. Reject
    // the whole line for NUL/other controls so a truncated START cannot arm.
    if (c != '\r' && (c < ' ' || c > '~')) {
      discarding_command = true;
      command_length = 0;
      command_line[0] = '\0';
      continue;
    }
    if (command_length >= COMMAND_CAPACITY - 1) {
      discarding_command = true;
      command_length = 0;
      command_line[0] = '\0';
      continue;
    }
    command_line[command_length++] = c;
    command_line[command_length] = '\0';
  }
}

void setup() {
  // Preload the OFF latch before D33 becomes an output. This prevents a LOW
  // setup glitch, but cannot make COM-NC fail off during reset/power loss.
  digitalWrite(PIN_RELAY, RELAY_OFF);
  pinMode(PIN_RELAY, OUTPUT);
  applied_heater_on = false;
#if defined(__AVR__)
  wdt_disable();
#endif

  Serial.begin(115200);
  tc1.begin();
  tc2.begin();
  delay(500);  // MAX31855 power-up only; no delay is used while active.

  next_sample_ms = millis();
  controller.reset(next_sample_ms);
  applyHeater();
  Serial.println("time_s,t1_C,t2_C");
  emitTelemetry();  // bootstrap: request_id 0, IDLE, output OFF
#if defined(__AVR__)
  wdt_enable(WDTO_2S);
#endif
}

void loop() {
#if defined(__AVR__)
  wdt_reset();
#endif
  pollSerial();

  uint32_t now = millis();
  controller.update(now);
  applyHeater();  // interlock OFF precedes CSV, telemetry, or other output

  if ((int32_t)(now - next_sample_ms) < 0) return;
  next_sample_ms = now + PERIOD_MS;  // no catch-up burst after a delayed loop

  const float t1_c = (float)tc1.readCelsius();
  const float t2_c = (float)tc2.readCelsius();
  now = millis();
  controller.onSample(now, t1_c, t2_c);
  applyHeater();  // especially TC2/HOT/SENSOR trips: OFF before serial work

  Serial.print(now / 1000.0, 2);
  Serial.print(',');
  Serial.print(t1_c, 2);
  Serial.print(',');
  Serial.println(t2_c, 2);
  emitTelemetry();
}
