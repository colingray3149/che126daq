// Print MAX31855 fault bits and cold-junction temp for both boards.
#include <Adafruit_MAX31855.h>
Adafruit_MAX31855 tc[] = {Adafruit_MAX31855(22, 26, 24), Adafruit_MAX31855(28, 32, 30)};

void setup() {
  Serial.begin(115200);
  for (auto &t : tc) t.begin();
  delay(500);
}

void loop() {
  for (int i = 0; i < 2; i++) {
    float c = tc[i].readCelsius();
    uint8_t e = tc[i].readError();
    Serial.print("TC"); Serial.print(i + 1);
    Serial.print(" tc="); Serial.print(c);
    Serial.print(" board="); Serial.print(tc[i].readInternal());
    Serial.print(" fault=");
    if (!e) Serial.print("none");
    if (e & MAX31855_FAULT_OPEN) Serial.print("OPEN ");
    if (e & MAX31855_FAULT_SHORT_GND) Serial.print("SHORT_GND ");
    if (e & MAX31855_FAULT_SHORT_VCC) Serial.print("SHORT_VCC ");
    Serial.println();
  }
  delay(1000);
}
