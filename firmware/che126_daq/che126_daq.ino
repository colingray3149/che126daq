// che126-daq firmware: three MAX31855 thermocouple amplifiers and one heater relay.
//
// The board only measures and switches. Experiment logic lives in daq.py on the
// computer, which must keep renewing heat permission ("HEAT 1 <lease_ms>"). If the
// computer stops talking, the lease runs out and the relay goes to OFF.
//
// Board-side limits (LIM) trip the heater OFF on their own and stay tripped until
// CLEAR, even if the computer keeps asking for heat.
//
// Pins (Arduino Mega ADK):
//   amplifier 1 CLK/DO/CS = 22/24/26
//   amplifier 2 CLK/DO/CS = 28/30/32
//   amplifier 3 CLK/DO/CS = 34/36/38
//   relay signal          = 33
//
// Relay polarity is saved in EEPROM ("RELAY NC" or "RELAY NO"):
//   NC: heater wired through COM-NC. Pin HIGH = OFF, LOW = ON. Heat flows whenever
//       the board is unpowered or resetting.
//   NO: heater wired through COM-NO. Pin LOW = OFF, HIGH = ON.
//
// Serial 115200 baud, one line per message:
//   S,<ms>,<t1>,<t2>,<t3>,<f1>,<f2>,<f3>,<heat>,<trip>   sample (t in C or nan, f = fault bits)
//   #ID che126-daq <version> relay=<NC|NO>               at boot and on ID
//   #CFG ...                                             on CFG
//   #OK <command>  /  #ERR <reason>                      command replies
//   #TRIP <reason>                                       a limit or sensor trip latched
//   #LEASE                                               heat permission expired

#include <EEPROM.h>
#include <avr/wdt.h>

#define FIRMWARE_VERSION "1"

const uint8_t CLK[3] = {22, 28, 34};
const uint8_t DO_[3] = {24, 30, 36};
const uint8_t CS[3] = {26, 32, 38};
const uint8_t PIN_RELAY = 33;

const uint8_t EEPROM_MAGIC_ADDR = 0, EEPROM_POLARITY_ADDR = 1;
const uint8_t EEPROM_MAGIC = 0xC6;
const uint8_t POLARITY_NC = 0, POLARITY_NO = 1;

const uint32_t LEASE_DEFAULT_MS = 2000, LEASE_MAX_MS = 10000;
const uint8_t LIMIT_CONFIRM_SAMPLES = 2;  // a single garbage reading cannot trip

uint8_t polarity = POLARITY_NC;
uint32_t sample_ms = 250;
float limit_c[3] = {0, 0, 0};          // 0 = no limit
uint32_t fault_trip_ms = 0;            // 0 = sensor faults never trip
bool heat_requested = false;
uint32_t lease_until_ms = 0;
bool tripped = false;
uint8_t over_count[3] = {0, 0, 0};
uint32_t fault_since_ms[3] = {0, 0, 0};
bool relay_on = false;

char line[64];
uint8_t line_len = 0;
bool line_overflow = false;
uint32_t next_sample_ms = 0;

uint8_t offLevel() { return polarity == POLARITY_NC ? HIGH : LOW; }
uint8_t onLevel() { return polarity == POLARITY_NC ? LOW : HIGH; }

void setRelay(bool on) {
  relay_on = on;
  digitalWrite(PIN_RELAY, on ? onLevel() : offLevel());
}

bool leaseValid(uint32_t now) { return (int32_t)(lease_until_ms - now) > 0; }

void applyRelay(uint32_t now) {
  bool want = heat_requested && !tripped && leaseValid(now);
  if (heat_requested && !leaseValid(now)) {
    heat_requested = false;
    Serial.println(F("#LEASE"));
  }
  if (want != relay_on) setRelay(want);
}

void trip(const char *reason, uint8_t ch) {
  if (tripped) return;
  tripped = true;
  heat_requested = false;
  setRelay(false);
  Serial.print(F("#TRIP "));
  Serial.print(reason);
  Serial.print(' ');
  Serial.println(ch + 1);
}

// MAX31855: 32 bits, D31 first, next bit after each falling clock edge.
uint32_t readRaw(uint8_t ch) {
  uint32_t v = 0;
  digitalWrite(CS[ch], LOW);
  delayMicroseconds(20);
  for (int8_t i = 31; i >= 0; i--) {
    digitalWrite(CLK[ch], LOW);
    delayMicroseconds(10);
    v <<= 1;
    if (digitalRead(DO_[ch])) v |= 1;
    digitalWrite(CLK[ch], HIGH);
    delayMicroseconds(10);
  }
  digitalWrite(CLK[ch], LOW);
  digitalWrite(CS[ch], HIGH);
  return v;
}

// Returns fault bits (1 open, 2 short to GND, 4 short to VCC, 8 no response).
uint8_t readChannel(uint8_t ch, float *celsius) {
  uint32_t v = readRaw(ch);
  if (v == 0xFFFFFFFFUL || v == 0) {
    // All ones: DO floating high (amplifier missing). All zeros reads as 0.00 C
    // with no fault bit, which a disconnected DO line also produces.
    *celsius = NAN;
    return 8;
  }
  if (v & 0x7) {
    *celsius = NAN;
    return v & 0x7;
  }
  int16_t t = (int16_t)(v >> 16) >> 2;  // signed 14-bit, 0.25 C
  *celsius = t * 0.25f;
  return 0;
}

void printTemp(float c) {
  if (isnan(c)) Serial.print(F("nan"));
  else Serial.print(c, 2);
}

void sample(uint32_t now) {
  float t[3];
  uint8_t f[3];
  for (uint8_t ch = 0; ch < 3; ch++) f[ch] = readChannel(ch, &t[ch]);

  for (uint8_t ch = 0; ch < 3; ch++) {
    if (limit_c[ch] <= 0) {
      over_count[ch] = 0;
      fault_since_ms[ch] = 0;
      continue;
    }
    if (f[ch]) {
      over_count[ch] = 0;
      if (fault_since_ms[ch] == 0) fault_since_ms[ch] = now | 1;
      if (fault_trip_ms > 0 && now - fault_since_ms[ch] >= fault_trip_ms) trip("FAULT", ch);
    } else {
      fault_since_ms[ch] = 0;
      if (t[ch] >= limit_c[ch]) {
        if (over_count[ch] < 255) over_count[ch]++;
        if (over_count[ch] >= LIMIT_CONFIRM_SAMPLES) trip("LIMIT", ch);
      } else {
        over_count[ch] = 0;
      }
    }
  }
  applyRelay(now);

  Serial.print(F("S,"));
  Serial.print(now);
  for (uint8_t ch = 0; ch < 3; ch++) {
    Serial.print(',');
    printTemp(t[ch]);
  }
  for (uint8_t ch = 0; ch < 3; ch++) {
    Serial.print(',');
    Serial.print(f[ch]);
  }
  Serial.print(',');
  Serial.print(relay_on ? 1 : 0);
  Serial.print(',');
  Serial.println(tripped ? 1 : 0);
}

void printId() {
  Serial.print(F("#ID che126-daq " FIRMWARE_VERSION " relay="));
  Serial.println(polarity == POLARITY_NC ? F("NC") : F("NO"));
}

void printCfg() {
  Serial.print(F("#CFG relay="));
  Serial.print(polarity == POLARITY_NC ? F("NC") : F("NO"));
  Serial.print(F(" rate_ms="));
  Serial.print(sample_ms);
  Serial.print(F(" fault_ms="));
  Serial.print(fault_trip_ms);
  for (uint8_t ch = 0; ch < 3; ch++) {
    Serial.print(F(" lim"));
    Serial.print(ch + 1);
    Serial.print('=');
    Serial.print(limit_c[ch], 1);
  }
  Serial.print(F(" tripped="));
  Serial.println(tripped ? 1 : 0);
}

void ok(const char *cmd) {
  Serial.print(F("#OK "));
  Serial.println(cmd);
}

void err(const __FlashStringHelper *why) {
  Serial.print(F("#ERR "));
  Serial.println(why);
}

void handle(char *cmd, uint32_t now) {
  char *word = strtok(cmd, " ");
  if (!word) return;
  char *a = strtok(NULL, " ");
  char *b = strtok(NULL, " ");

  if (!strcmp(word, "HEAT")) {
    if (!a) return err(F("HEAT needs 0 or 1"));
    if (a[0] == '0') {
      heat_requested = false;
      applyRelay(now);
      return ok("HEAT 0");
    }
    if (tripped) return err(F("tripped; send CLEAR first"));
    uint32_t lease = b ? (uint32_t)atol(b) : LEASE_DEFAULT_MS;
    if (lease < 100 || lease > LEASE_MAX_MS) return err(F("lease must be 100-10000 ms"));
    heat_requested = true;
    lease_until_ms = now + lease;
    applyRelay(now);
    return;  // renewed every few hundred ms; no reply keeps the line quiet
  }
  if (!strcmp(word, "LIM")) {
    if (!a || !b) return err(F("LIM <1-3> <max C, 0 = off>"));
    int ch = atoi(a);
    if (ch < 1 || ch > 3) return err(F("channel must be 1-3"));
    limit_c[ch - 1] = atof(b);
    over_count[ch - 1] = 0;
    fault_since_ms[ch - 1] = 0;
    return ok("LIM");
  }
  if (!strcmp(word, "FAULT")) {
    if (!a) return err(F("FAULT <ms, 0 = off>"));
    fault_trip_ms = (uint32_t)atol(a);
    return ok("FAULT");
  }
  if (!strcmp(word, "RATE")) {
    long ms = a ? atol(a) : 0;
    if (ms < 100 || ms > 5000) return err(F("RATE 100-5000 ms"));
    sample_ms = ms;
    return ok("RATE");
  }
  if (!strcmp(word, "CLEAR")) {
    tripped = false;
    for (uint8_t ch = 0; ch < 3; ch++) {
      over_count[ch] = 0;
      fault_since_ms[ch] = 0;
    }
    return ok("CLEAR");
  }
  if (!strcmp(word, "RELAY")) {
    if (!a || (strcmp(a, "NC") && strcmp(a, "NO"))) return err(F("RELAY NC or RELAY NO"));
    heat_requested = false;
    polarity = strcmp(a, "NC") ? POLARITY_NO : POLARITY_NC;
    EEPROM.update(EEPROM_MAGIC_ADDR, EEPROM_MAGIC);
    EEPROM.update(EEPROM_POLARITY_ADDR, polarity);
    setRelay(false);
    printId();
    return;
  }
  if (!strcmp(word, "ID")) return printId();
  if (!strcmp(word, "CFG")) return printCfg();
  err(F("unknown command"));
}

void pollSerial(uint32_t now) {
  uint8_t budget = 64;
  while (budget-- && Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[line_len] = 0;
      if (line_overflow) err(F("line too long"));
      else if (line_len) handle(line, now);
      line_len = 0;
      line_overflow = false;
      continue;
    }
    if (line_len < sizeof(line) - 1) line[line_len++] = c;
    else line_overflow = true;
  }
}

void setup() {
  if (EEPROM.read(EEPROM_MAGIC_ADDR) == EEPROM_MAGIC && EEPROM.read(EEPROM_POLARITY_ADDR) == POLARITY_NO)
    polarity = POLARITY_NO;
  // Drive the OFF level before the pin becomes an output, so setup never pulses ON.
  digitalWrite(PIN_RELAY, offLevel());
  pinMode(PIN_RELAY, OUTPUT);
  relay_on = false;

  for (uint8_t ch = 0; ch < 3; ch++) {
    pinMode(CS[ch], OUTPUT);
    digitalWrite(CS[ch], HIGH);
    pinMode(CLK[ch], OUTPUT);
    digitalWrite(CLK[ch], LOW);
    pinMode(DO_[ch], INPUT);
  }
  Serial.begin(115200);
  delay(300);  // MAX31855 first conversion
  printId();
  wdt_enable(WDTO_2S);
  next_sample_ms = millis();
}

void loop() {
  wdt_reset();
  uint32_t now = millis();
  pollSerial(now);
  applyRelay(now);
  if ((int32_t)(now - next_sample_ms) >= 0) {
    next_sample_ms = now + sample_ms;
    sample(now);
  }
}
