// Two Adafruit MAX31855 type K breakouts sharing CLK and DO, each with its own CS.
// Wiring: Vin -> 5V (or 3.3V), GND -> GND, CLK -> D5, DO -> D3, CS -> D4 (TC1) / D6 (TC2)
// Prints CSV over serial at 115200: time_s,t1_C,t2_C  (nan = thermocouple fault, e.g. open circuit)

#include <Adafruit_MAX31855.h>

const int PIN_CLK = 5, PIN_DO = 3, PIN_CS1 = 4, PIN_CS2 = 6;
const unsigned long PERIOD_MS = 500;

Adafruit_MAX31855 tc1(PIN_CLK, PIN_CS1, PIN_DO);
Adafruit_MAX31855 tc2(PIN_CLK, PIN_CS2, PIN_DO);

void setup() {
  Serial.begin(115200);
  tc1.begin();
  tc2.begin();
  delay(500);  // MAX31855 needs a moment after power-up
  Serial.println("time_s,t1_C,t2_C");
}

void loop() {
  static unsigned long next = 0;
  if (millis() < next) return;
  next += PERIOD_MS;

  Serial.print(millis() / 1000.0, 2);
  Serial.print(',');
  Serial.print(tc1.readCelsius(), 2);
  Serial.print(',');
  Serial.println(tc2.readCelsius(), 2);
}
