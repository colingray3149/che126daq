// Two Adafruit AD8495 type K amplifiers on A1 and A2.
// AD8495 output: Vout = 1.25 V + 5 mV/°C  ->  T = (Vout - 1.25) / 0.005
// Prints CSV over serial at 115200: time_s,t1_C,t2_C

const float VREF = 5.0;          // Mega analog reference (default 5 V)
const int SAMPLES = 32;          // readings averaged per channel to cut noise
const unsigned long PERIOD_MS = 500;

float readTempC(int pin) {
  long sum = 0;
  for (int i = 0; i < SAMPLES; i++) sum += analogRead(pin);
  float volts = (sum / (float)SAMPLES) * VREF / 1023.0;
  return (volts - 1.25) / 0.005;
}

void setup() {
  Serial.begin(115200);
  Serial.println("time_s,t1_C,t2_C");
}

void loop() {
  static unsigned long next = 0;
  if (millis() < next) return;
  next += PERIOD_MS;

  Serial.print(millis() / 1000.0, 2);
  Serial.print(',');
  Serial.print(readTempC(A1), 1);
  Serial.print(',');
  Serial.println(readTempC(A2), 1);
}
