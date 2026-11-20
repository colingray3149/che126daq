// Wiring check: select each CS in turn and read 32 bits from each DO pin.
const int CLK = 22, CS[] = {26, 28}, DO[] = {24, 30};

uint32_t read32(int cs, int dout) {
  uint32_t v = 0;
  digitalWrite(cs, LOW);
  delayMicroseconds(10);
  for (int i = 0; i < 32; i++) {
    digitalWrite(CLK, LOW); delayMicroseconds(10);
    v = (v << 1) | digitalRead(dout);
    digitalWrite(CLK, HIGH); delayMicroseconds(10);
  }
  digitalWrite(cs, HIGH);
  return v;
}

void setup() {
  Serial.begin(115200);
  pinMode(CLK, OUTPUT); digitalWrite(CLK, LOW);
  for (int c : CS) { pinMode(c, OUTPUT); digitalWrite(c, HIGH); }
  for (int d : DO) pinMode(d, INPUT_PULLUP);
  delay(500);
}

void loop() {
  for (int c : CS) for (int d : DO) {
    uint32_t v = read32(c, d);
    Serial.print("CS"); Serial.print(c); Serial.print(" DO"); Serial.print(d);
    Serial.print(" 0x"); Serial.print(v, HEX);
    if (v != 0 && v != 0xFFFFFFFF) {
      Serial.print(" tc="); Serial.print(((int32_t)v >> 18) * 0.25);
      Serial.print(" internal="); Serial.print(((int16_t)(v & 0xFFF0) >> 4) * 0.0625);
      Serial.print(" fault="); Serial.print(v & 7);
    }
    Serial.println();
  }
  Serial.println();
  delay(1000);
}
