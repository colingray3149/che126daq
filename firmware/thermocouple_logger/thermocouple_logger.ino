// Two Adafruit MAX31855 type K breakouts, each on its own pins.
// Wiring: Vin -> 5V, GND -> GND; TC1 CLK/DO/CS -> D22/D24/D26, TC2 CLK/DO/CS -> D28/D30/D32
// Prints CSV over serial at 115200: time_s,t1_C,t2_C  (nan = thermocouple fault, e.g. open circuit)

#include <Adafruit_MAX31855.h>

const int PIN_CLK1 = 22, PIN_DO1 = 24, PIN_CS1 = 26;
const int PIN_CLK2 = 28, PIN_DO2 = 30, PIN_CS2 = 32;
const unsigned long PERIOD_MS = 500;

Adafruit_MAX31855 tc1(PIN_CLK1, PIN_CS1, PIN_DO1);
Adafruit_MAX31855 tc2(PIN_CLK2, PIN_CS2, PIN_DO2);

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
