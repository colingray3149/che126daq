#ifndef CHE126_EXP2_CONTROLLER_H
#define CHE126_EXP2_CONTROLLER_H

#include <float.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// CHE126 experiments 2/3/4/5, protocol "exp2-v5"; START is explicit manual re-arming.
// All times are uint32_t milliseconds from the same wrapping clock. This
// class only decides the requested heater level; the sketch owns the relay.
// NC wiring is NOT power-independent fail-safe: this active-HIGH module must
// be energized to open the heater contact.
namespace che126_exp2 {

enum State : uint8_t {
  IDLE,
  RUNNING,
  HOLD,
  TRIPPED,
  COMPLETE,
  STOPPED
};

enum Program : uint8_t { PROGRAM_SINGLE, PROGRAM_EXP4, PROGRAM_EXP5 };

enum Phase : uint8_t {
  SINGLE,
  HEAT_100,
  HOLD_100,
  RAMP_200,
  BOOST_FINAL,
  HOLD_FINAL
};

struct Settings {
  float target_c;
  float hysteresis_c;
  float tc1_cutoff_c;
  float tc2_cutoff_c;
  bool tc2_cutoff_enabled;
  uint32_t prediction_lead_ms;
  uint32_t min_off_ms;
  float hold_band_c;
  uint32_t hold_duration_ms;
  bool swap_inputs;
};

class Controller {
public:
  // These defaults are used only at hardware boot/reset. Every accepted START
  // supplies and atomically applies a complete replacement Settings value.
  static Settings defaultSettings() {
    Settings settings;
    settings.target_c = 300.0f;
    settings.hysteresis_c = 3.0f;
    settings.tc1_cutoff_c = 320.0f;
    settings.tc2_cutoff_c = 140.0f;
    settings.tc2_cutoff_enabled = true;
    settings.prediction_lead_ms = 5000UL;
    settings.min_off_ms = 5000UL;
    settings.hold_band_c = 5.0f;
    settings.hold_duration_ms = 1800000UL;
    settings.swap_inputs = false;
    return settings;
  }

  static Settings defaultExp4Settings() {
    Settings settings;
    settings.target_c = 700.0f;
    settings.hysteresis_c = 3.0f;
    settings.tc1_cutoff_c = 730.0f;
    settings.tc2_cutoff_c = 85.0f;
    settings.tc2_cutoff_enabled = true;
    settings.prediction_lead_ms = 5000UL;
    settings.min_off_ms = 5000UL;
    settings.hold_band_c = 5.0f;
    settings.hold_duration_ms = 0;
    settings.swap_inputs = true;
    return settings;
  }

  static Settings defaultExp5Settings() {
    Settings settings = defaultExp4Settings();
    settings.tc2_cutoff_c = 120.0f;
    settings.hold_duration_ms = 60000UL;
    return settings;
  }

  enum : uint32_t {
    SAMPLE_STALE_MS = 1500UL,
    HOST_TIMEOUT_MS = 2500UL,
    SLOPE_WINDOW_MS = 5000UL,
    RAMP_DURATION_MS = 90000UL,
    MAX_DURATION_MS = 2147483647UL
  };

  Controller() { reset(0); }

  // Hardware boot initialization; ordinary experiments do not require reset.
  void reset(uint32_t now_ms) {
    settings_ = defaultSettings();
    program_ = PROGRAM_SINGLE;
    phase_ = SINGLE;
    setpoint_c_ = settings_.target_c;
    state_ = IDLE;
    reason_ = "BOOT";
    heater_on_ = false;
    output_changed_ms_ = now_ms;
    request_id_ = 0;
    command_ok_ = false;
    heartbeat_seen_ = false;
    last_heartbeat_ms_ = now_ms;
    sample_valid_ = false;
    last_sample_ms_ = now_ms;
    last_raw_sample_ms_ = now_ms;
    tc1_c_ = 0.0f;
    tc2_c_ = 0.0f;
    slope_c_per_s_ = 0.0f;
    history_count_ = 0;
    history_next_ = 0;
    in_band_ = false;
    hold_started_ms_ = now_ms;
    hold_s_ = 0;
    ramp_started_ms_ = now_ms;
  }

  // Supply each acquisition exactly once. Invalid samples are never entered
  // into the slope history. This method also evaluates all interlocks/control.
  void onSample(uint32_t now_ms, float raw_tc1_c, float raw_tc2_c) {
    last_raw_sample_ms_ = now_ms;
    tc1_c_ = settings_.swap_inputs ? raw_tc2_c : raw_tc1_c;
    tc2_c_ = settings_.swap_inputs ? raw_tc1_c : raw_tc2_c;

    // Logical TC1 supplies heater feedback. Logical TC2 is optional for
    // single-probe testing; its trip applies only for a finite enabled high.
    const bool finite1 = finite(tc1_c_);
    const bool finite2 = finite(tc2_c_);
    const bool checked = finite1 && tc1_c_ > 0.0f;

    if (checked) {
      sample_valid_ = true;
      last_sample_ms_ = now_ms;
      recordSlopeSample(now_ms, tc1_c_);
    } else {
      sample_valid_ = false;
      slope_c_per_s_ = 0.0f;
      history_count_ = 0;
      history_next_ = 0;
    }

    if (active()) {
      // Logical TC2 has explicit priority, including when heater feedback is bad.
      if (settings_.tc2_cutoff_enabled && finite2 &&
        tc2_c_ >= settings_.tc2_cutoff_c) {
        trip("TC2_LIMIT", now_ms);
      } else if (stagedProgram() && !finite2) {
        trip("TC2_FAULT", now_ms);
      } else if (finite1 && tc1_c_ >= settings_.tc1_cutoff_c) {
        trip("HOT_LIMIT", now_ms);
      } else if (!checked) {
        trip("SENSOR_FAULT", now_ms);
      }
    } else if (state_ == IDLE) {
      if (settings_.tc2_cutoff_enabled && finite2 &&
        tc2_c_ >= settings_.tc2_cutoff_c) {
        reason_ = "TC2_LIMIT";
      } else if (finite1 && tc1_c_ >= settings_.tc1_cutoff_c) {
        reason_ = "HOT_LIMIT";
      } else if (!checked) {
        reason_ = "SENSOR_FAULT";
      } else {
        reason_ = "IDLE";
      }
    }

    update(now_ms);
  }

  // Call frequently between samples for host-timeout and stale-sample trips.
  void update(uint32_t now_ms) {
    if (!active()) return;
    // Runtime limits also apply immediately after an unconditional START,
    // before the next acquisition; they are not pre-start requirements.
    if (settings_.tc2_cutoff_enabled && finite(tc2_c_) &&
        tc2_c_ >= settings_.tc2_cutoff_c) {
      trip("TC2_LIMIT", now_ms);
      return;
    }
    if (stagedProgram() && !finite(tc2_c_)) {
      trip("TC2_FAULT", now_ms);
      return;
    }
    if (finite(tc1_c_) && tc1_c_ >= settings_.tc1_cutoff_c) {
      trip("HOT_LIMIT", now_ms);
      return;
    }

    if (!sample_valid_ || elapsed(now_ms, last_sample_ms_) >= SAMPLE_STALE_MS) {
      trip("SENSOR_STALE", now_ms);
      return;
    }
    if (!heartbeat_seen_ ||
        elapsed(now_ms, last_heartbeat_ms_) >= HOST_TIMEOUT_MS) {
      trip("HOST_TIMEOUT", now_ms);
      return;
    }

    if (stagedProgram()) {
      updateStaged(now_ms);
      return;
    }

    setpoint_c_ = settings_.target_c;
    updateHold(now_ms);
    if (!active()) return;
    reason_ = (state_ == HOLD) ? "HOLD" : "RUNNING";
    regulate(settings_.target_c, settings_.target_c, true, now_ms);
  }

  // Parse one complete, NUL-terminated, newline-stripped command. Returns true
  // when the caller should emit immediate acknowledgement telemetry. PING only
  // refreshes the heartbeat and therefore returns false. No command retries or
  // delayed/pending START exist. Malformed input can never enable the output.
  bool handleCommand(const char *line, uint32_t now_ms) {
    update(now_ms);
    if (line == 0) {
      reject("BAD_COMMAND");
      return true;
    }

    if (strcmp(line, "EXP2 PING") == 0) {
      heartbeat_seen_ = true;
      last_heartbeat_ms_ = now_ms;
      return false;
    }

    static const char START_PREFIX[] = "EXP2 START ";
    static const char EXP4_START_PREFIX[] = "EXP4 START ";
    static const char EXP5_START_PREFIX[] = "EXP5 START ";
    static const char EXP4_NEXT_PREFIX[] = "EXP4 NEXT ";
    static const char EXP5_NEXT_PREFIX[] = "EXP5 NEXT ";
    static const char STOP_PREFIX[] = "EXP2 STOP ";
    uint32_t id = 0;

    if (strncmp(line, START_PREFIX, sizeof(START_PREFIX) - 1) == 0) {
      Settings candidate;
      const bool valid = parseStart(line + sizeof(START_PREFIX) - 1, id, candidate);
      request_id_ = id;
      command_ok_ = false;
      if (!valid) {
        reject("BAD_COMMAND");
        return true;
      }
      start(id, candidate, PROGRAM_SINGLE, now_ms);
      return true;
    }

    if (strncmp(line, EXP4_START_PREFIX, sizeof(EXP4_START_PREFIX) - 1) == 0) {
      Settings candidate;
      const bool valid =
          parseStart(line + sizeof(EXP4_START_PREFIX) - 1, id, candidate) &&
          validExp4Settings(candidate);
      request_id_ = id;
      command_ok_ = false;
      if (!valid) {
        reject("BAD_COMMAND");
        return true;
      }
      start(id, candidate, PROGRAM_EXP4, now_ms);
      return true;
    }

    if (strncmp(line, EXP5_START_PREFIX, sizeof(EXP5_START_PREFIX) - 1) == 0) {
      Settings candidate;
      const bool valid =
          parseStart(line + sizeof(EXP5_START_PREFIX) - 1, id, candidate) &&
          validExp5Settings(candidate);
      request_id_ = id;
      command_ok_ = false;
      if (!valid) {
        reject("BAD_COMMAND");
        return true;
      }
      start(id, candidate, PROGRAM_EXP5, now_ms);
      return true;
    }

    if (strncmp(line, EXP4_NEXT_PREFIX, sizeof(EXP4_NEXT_PREFIX) - 1) == 0) {
      const bool valid_id = parsePositiveId(line + sizeof(EXP4_NEXT_PREFIX) - 1, id);
      request_id_ = id;
      command_ok_ = false;
      if (!valid_id) {
        reject("BAD_COMMAND");
        return true;
      }
      next(id, PROGRAM_EXP4, now_ms);
      return true;
    }

    if (strncmp(line, EXP5_NEXT_PREFIX, sizeof(EXP5_NEXT_PREFIX) - 1) == 0) {
      const bool valid_id = parsePositiveId(line + sizeof(EXP5_NEXT_PREFIX) - 1, id);
      request_id_ = id;
      command_ok_ = false;
      if (!valid_id) {
        reject("BAD_COMMAND");
        return true;
      }
      next(id, PROGRAM_EXP5, now_ms);
      return true;
    }

    if (strncmp(line, STOP_PREFIX, sizeof(STOP_PREFIX) - 1) == 0) {
      const bool valid_id = parsePositiveId(line + sizeof(STOP_PREFIX) - 1, id);
      request_id_ = id;
      command_ok_ = false;
      if (!valid_id) {
        reject("BAD_COMMAND");
        return true;
      }
      stop(id, now_ms);
      return true;
    }

    request_id_ = 0;
    command_ok_ = false;
    reject("BAD_COMMAND");
    return true;
  }

  bool heaterOn() const { return heater_on_; }
  State state() const { return state_; }
  Program program() const { return program_; }
  Phase phase() const { return phase_; }
  const char *reason() const { return reason_; }
  uint32_t holdSeconds() const { return hold_s_; }
  uint32_t requestId() const { return request_id_; }
  bool commandOk() const { return command_ok_; }
  bool tc2Required() const { return stagedProgram(); }
  const Settings &settings() const { return settings_; }
  float setpointC() const { return setpoint_c_; }
  float slopeCPerSecond() const { return slope_c_per_s_; }

  static const char *stateName(State state) {
    switch (state) {
      case IDLE: return "IDLE";
      case RUNNING: return "RUNNING";
      case HOLD: return "HOLD";
      case TRIPPED: return "TRIPPED";
      case COMPLETE: return "COMPLETE";
      case STOPPED: return "STOPPED";
    }
    return "TRIPPED";
  }

  static const char *programName(Program program) {
    if (program == PROGRAM_EXP4) return "exp4";
    if (program == PROGRAM_EXP5) return "exp5";
    return "single";
  }

  static const char *phaseName(Phase phase) {
    switch (phase) {
      case SINGLE: return "SINGLE";
      case HEAT_100: return "HEAT_100";
      case HOLD_100: return "HOLD_100";
      case RAMP_200: return "RAMP_200";
      case BOOST_FINAL: return "BOOST_FINAL";
      case HOLD_FINAL: return "HOLD_FINAL";
    }
    return "SINGLE";
  }

private:
  struct SlopeSample {
    uint32_t time_ms;
    float tc1_c;
  };

  // At the firmware's 500 ms period, 16 entries cover the trailing 5 seconds
  // with margin. Older entries are excluded using actual unsigned elapsed time.
  enum { HISTORY_SIZE = 16 };

  static uint32_t elapsed(uint32_t now_ms, uint32_t earlier_ms) {
    return now_ms - earlier_ms;
  }

  static bool finite(float value) {
    return value == value && value <= FLT_MAX && value >= -FLT_MAX;
  }

  static bool finishToken(const char *&text, const char *end, bool last) {
    if (last) {
      if (*end != '\0') return false;
      text = end;
      return true;
    }
    if (*end != ' ' || end[1] == '\0') return false;
    text = end + 1;
    return true;
  }

  static bool parseUnsigned(const char *&text, uint32_t maximum,
                            uint32_t &value, bool last) {
    value = 0;
    const char *end = text;
    if (*end < '0' || *end > '9') return false;
    bool overflow = false;
    while (*end >= '0' && *end <= '9') {
      const uint8_t digit = (uint8_t)(*end - '0');
      if (value > (4294967295UL - digit) / 10UL) {
        overflow = true;
      } else if (!overflow) {
        value = value * 10UL + digit;
      }
      ++end;
    }
    if (overflow || value > maximum) return false;
    return finishToken(text, end, last);
  }

  static bool parseFloat(const char *&text, float &value, bool last) {
    const char *end = text;
    if (*end == '+' || *end == '-') ++end;

    bool has_digit = false;
    bool significant = false;
    uint8_t significant_digits = 0;
    while (*end >= '0' && *end <= '9') {
      has_digit = true;
      if (*end != '0') significant = true;
      if (significant) {
        if (significant_digits >= 6) return false;
        ++significant_digits;
      }
      ++end;
    }
    if (*end == '.') {
      ++end;
      while (*end >= '0' && *end <= '9') {
        has_digit = true;
        if (*end != '0') significant = true;
        if (significant) {
          if (significant_digits >= 6) return false;
          ++significant_digits;
        }
        ++end;
      }
    }
    if (!has_digit) return false;

    if (*end == 'e' || *end == 'E') {
      ++end;
      if (*end == '+' || *end == '-') ++end;
      if (*end < '0' || *end > '9') return false;
      while (*end >= '0' && *end <= '9') ++end;
    }

    char *conversion_end = 0;
    const double converted = strtod(text, &conversion_end);
    if (conversion_end != end) return false;
    value = (float)converted;
    return finishToken(text, end, last);
  }

  static bool parseBool(const char *&text, bool &value, bool last) {
    if (*text != '0' && *text != '1') return false;
    value = *text == '1';
    return finishToken(text, text + 1, last);
  }

  static bool validSettings(const Settings &settings) {
    const float limit = 1000000.0f;
    return finite(settings.target_c) && settings.target_c >= -limit &&
           settings.target_c <= limit && finite(settings.hysteresis_c) &&
           settings.hysteresis_c >= 0.0f && settings.hysteresis_c <= limit &&
           finite(settings.tc1_cutoff_c) && settings.tc1_cutoff_c >= -limit &&
           settings.tc1_cutoff_c <= limit && finite(settings.tc2_cutoff_c) &&
           settings.tc2_cutoff_c >= -limit && settings.tc2_cutoff_c <= limit &&
           settings.prediction_lead_ms <= MAX_DURATION_MS &&
           settings.min_off_ms <= MAX_DURATION_MS &&
           finite(settings.hold_band_c) && settings.hold_band_c >= 0.0f &&
           settings.hold_band_c <= limit &&
           settings.hold_duration_ms <= MAX_DURATION_MS;
  }

  static bool validExp4Settings(const Settings &settings) {
    return settings.target_c > 200.0f && settings.target_c <= 700.0f &&
           settings.target_c < settings.tc1_cutoff_c &&
           settings.tc1_cutoff_c <= 730.0f &&
           settings.tc2_cutoff_enabled && settings.tc2_cutoff_c == 85.0f &&
           settings.hold_duration_ms == 0 &&
           settings.hysteresis_c <= 5.0f && settings.hold_band_c <= 5.0f;
  }

  static bool validExp5Settings(const Settings &settings) {
    return settings.target_c == 700.0f &&
           settings.tc1_cutoff_c == 730.0f &&
           settings.tc2_cutoff_enabled && settings.tc2_cutoff_c == 120.0f &&
           settings.hold_duration_ms == 60000UL &&
           settings.hysteresis_c <= 5.0f && settings.hold_band_c <= 5.0f;
  }

  // Parse all eleven START fields into independent outputs. id remains available
  // for rejection acknowledgement after a valid id but a bad settings field.
  static bool parseStart(const char *text, uint32_t &id, Settings &settings) {
    id = 0;
    return parseUnsigned(text, 4294967295UL, id, false) && id > 0 &&
           parseFloat(text, settings.target_c, false) &&
           parseFloat(text, settings.hysteresis_c, false) &&
           parseFloat(text, settings.tc1_cutoff_c, false) &&
           parseFloat(text, settings.tc2_cutoff_c, false) &&
           parseBool(text, settings.tc2_cutoff_enabled, false) &&
           parseUnsigned(text, MAX_DURATION_MS, settings.prediction_lead_ms,
                         false) &&
           parseUnsigned(text, MAX_DURATION_MS, settings.min_off_ms, false) &&
           parseFloat(text, settings.hold_band_c, false) &&
           parseUnsigned(text, MAX_DURATION_MS, settings.hold_duration_ms,
                         false) &&
           parseBool(text, settings.swap_inputs, true) &&
           validSettings(settings);
  }

  static bool parsePositiveId(const char *text, uint32_t &id) {
    id = 0;
    if (*text < '0' || *text > '9') return false;
    bool overflow = false;
    while (*text >= '0' && *text <= '9') {
      const uint8_t digit = (uint8_t)(*text - '0');
      if (id > (4294967295UL - digit) / 10UL) {
        overflow = true;
      } else if (!overflow) {
        id = id * 10UL + digit;
      }
      ++text;
    }
    return !overflow && id > 0 && *text == '\0';
  }

  bool stagedProgram() const {
    return program_ == PROGRAM_EXP4 || program_ == PROGRAM_EXP5;
  }

  bool active() const { return state_ == RUNNING || state_ == HOLD; }

  void reject(const char *reason) {
    command_ok_ = false;
    // Preserve the latched cause in terminal states.
    if (state_ == IDLE || active()) reason_ = reason;
  }

  void start(uint32_t id, const Settings &settings, Program program,
             uint32_t now_ms) {
    if (settings_.swap_inputs != settings.swap_inputs) {
      // The cached values are logical under the old mapping. Swapping them
      // recovers the same raw acquisition under the new mapping; never carry
      // the opposite probe's freshness or slope into heater feedback.
      const float cached_tc1 = tc1_c_;
      tc1_c_ = tc2_c_;
      tc2_c_ = cached_tc1;
      sample_valid_ = finite(tc1_c_) && tc1_c_ > 0.0f;
      slope_c_per_s_ = 0.0f;
      history_count_ = 0;
      history_next_ = 0;
      if (sample_valid_) {
        last_sample_ms_ = last_raw_sample_ms_;
        recordSlopeSample(last_sample_ms_, tc1_c_);
      }
    }
    settings_ = settings;
    program_ = program;
    phase_ = stagedProgram() ? HEAT_100 : SINGLE;
    setpoint_c_ = stagedProgram() ? 100.0f : settings_.target_c;
    ramp_started_ms_ = now_ms;
    setHeater(false, now_ms);
    in_band_ = false;
    hold_started_ms_ = now_ms;
    hold_s_ = 0;
    state_ = RUNNING;
    reason_ = "START";
    command_ok_ = true;
    request_id_ = id;
  }

  void next(uint32_t id, Program expected_program, uint32_t now_ms) {
    const bool in_band = tc1_c_ >= 100.0f - settings_.hold_band_c &&
                         tc1_c_ <= 100.0f + settings_.hold_band_c;
    if (program_ != expected_program || !active() || phase_ != HOLD_100 || !in_band) {
      reject("NEXT_NOT_READY");
      return;
    }

    // NEXT changes only the phase trajectory. In particular, duplicate or
    // premature commands never re-arm a run or disturb the current output.
    phase_ = RAMP_200;
    state_ = RUNNING;
    setpoint_c_ = 100.0f;
    ramp_started_ms_ = now_ms;
    in_band_ = false;
    hold_started_ms_ = now_ms;
    hold_s_ = 0;
    request_id_ = id;
    command_ok_ = true;
    reason_ = "NEXT";
  }

  void stop(uint32_t id, uint32_t now_ms) {
    // Output is requested OFF before any acknowledgement/serial work and in
    // every state, including IDLE and an already-latched terminal state.
    setHeater(false, now_ms);
    request_id_ = id;
    command_ok_ = true;
    if (state_ != TRIPPED && state_ != COMPLETE) {
      state_ = STOPPED;
      reason_ = "STOP";
    }
  }

  void trip(const char *reason, uint32_t now_ms) {
    setHeater(false, now_ms);
    state_ = TRIPPED;
    reason_ = reason;
  }

  void setHeater(bool on, uint32_t now_ms) {
    if (heater_on_ == on) return;
    heater_on_ = on;
    output_changed_ms_ = now_ms;
  }

  static float rampReference(uint32_t elapsed_ms) {
    const uint32_t bounded = elapsed_ms < RAMP_DURATION_MS
                                 ? elapsed_ms
                                 : RAMP_DURATION_MS;
    return 100.0f + 100.0f * ((float)bounded / (float)RAMP_DURATION_MS);
  }

  void regulate(float target_c, float future_target_c,
                bool use_slope_prediction, uint32_t now_ms) {
    const float positive_slope =
        use_slope_prediction && slope_c_per_s_ > 0.0f ? slope_c_per_s_ : 0.0f;
    const float projected =
        tc1_c_ + positive_slope * ((float)settings_.prediction_lead_ms / 1000.0f);
    const bool projected_cutoff = projected >= future_target_c;

    if (heater_on_) {
      // This forecast includes TC1 >= target even with zero/negative slope. OFF
      // is always immediate; a predictive pulse may be shorter than the dwell.
      if (projected_cutoff) setHeater(false, now_ms);
    } else if (tc1_c_ <= target_c - settings_.hysteresis_c &&
               !projected_cutoff &&
               elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms) {
      // Never switch ON when the cutoff is already true. The OFF dwell bounds
      // re-enable frequency without delaying any safety/predictive OFF.
      setHeater(true, now_ms);
    }
  }

  void updateStaged(uint32_t now_ms) {
    if (phase_ == HEAT_100 || phase_ == HOLD_100) {
      const bool in_band = tc1_c_ >= 100.0f - settings_.hold_band_c &&
                           tc1_c_ <= 100.0f + settings_.hold_band_c;
      setpoint_c_ = 100.0f;
      if (!in_band) {
        phase_ = HEAT_100;
        state_ = RUNNING;
        in_band_ = false;
        hold_s_ = 0;
      } else {
        if (!in_band_ || phase_ != HOLD_100) {
          in_band_ = true;
          hold_started_ms_ = now_ms;
          hold_s_ = 0;
        } else {
          hold_s_ = elapsed(now_ms, hold_started_ms_) / 1000UL;
        }
        phase_ = HOLD_100;
        state_ = HOLD;
      }
      reason_ = state_ == HOLD ? "HOLD" : "RUNNING";
      regulate(100.0f, 100.0f, true, now_ms);
      return;
    }

    if (phase_ == RAMP_200) {
      const uint32_t ramp_age = elapsed(now_ms, ramp_started_ms_);
      setpoint_c_ = rampReference(ramp_age);
      if (tc1_c_ >= 200.0f) {
        phase_ = BOOST_FINAL;
        state_ = RUNNING;
        setpoint_c_ = settings_.target_c;
        hold_s_ = 0;
      } else {
        state_ = RUNNING;
        reason_ = "RUNNING";
        hold_s_ = 0;
        // Once the reference is 200 C, finish the approach below 200 C without
        // prediction or hysteresis trapping the measured value below the only
        // permitted phase transition. Minimum OFF still bounds re-energization.
        if (ramp_age >= RAMP_DURATION_MS) {
          if (!heater_on_ &&
              elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms) {
            setHeater(true, now_ms);
          }
          return;
        }
        const uint32_t future_age =
            settings_.prediction_lead_ms >= RAMP_DURATION_MS - ramp_age
                ? RAMP_DURATION_MS
                : ramp_age + settings_.prediction_lead_ms;
        regulate(setpoint_c_, rampReference(future_age), true, now_ms);
        return;
      }
    }

    if (phase_ == BOOST_FINAL) {
      state_ = RUNNING;
      reason_ = "RUNNING";
      setpoint_c_ = settings_.target_c;
      hold_s_ = 0;
      if (program_ == PROGRAM_EXP5) {
        if (tc1_c_ < settings_.target_c) {
          // EXP5 boost ignores slope prediction: only the measured heater
          // temperature may end maximum commanded heat and start the final hold.
          if (heater_on_ ||
              elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms) {
            setHeater(true, now_ms);
          }
          return;
        }
        phase_ = HOLD_FINAL;
        hold_started_ms_ = now_ms;
        hold_s_ = 0;
      } else {
        const float positive_slope =
            slope_c_per_s_ > 0.0f ? slope_c_per_s_ : 0.0f;
        const float projected =
            tc1_c_ + positive_slope * ((float)settings_.prediction_lead_ms / 1000.0f);
        if (projected < settings_.target_c) {
          // Full power is a phase policy, not a fixed duty cycle. Preserve an
          // existing ON request, but never bypass minimum OFF on re-energization.
          if (heater_on_ ||
              elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms) {
            setHeater(true, now_ms);
          }
          return;
        }
        phase_ = HOLD_FINAL;
        hold_s_ = 0;
      }
    }

    if (program_ == PROGRAM_EXP5) {
      // The final EXP5 hold is wall-clock time from the first measured target
      // crossing. Leaving the regulation band neither pauses nor resets it.
      phase_ = HOLD_FINAL;
      setpoint_c_ = settings_.target_c;
      const uint32_t hold_age = elapsed(now_ms, hold_started_ms_);
      hold_s_ = hold_age / 1000UL;
      if (hold_age >= settings_.hold_duration_ms) {
        setHeater(false, now_ms);
        state_ = COMPLETE;
        reason_ = "HOLD_COMPLETE";
        return;
      }
      state_ = HOLD;
      reason_ = "HOLD";
      regulate(settings_.target_c, settings_.target_c, true, now_ms);
      return;
    }

    // EXP4 HOLD_FINAL has no timer-based completion and remains the terminal phase
    // label after STOP or a fault for diagnosis. State and hold_s retain their
    // continuous in-band meaning even when predictive capture occurs below it.
    phase_ = HOLD_FINAL;
    setpoint_c_ = settings_.target_c;
    const bool in_band =
        tc1_c_ >= settings_.target_c - settings_.hold_band_c &&
        tc1_c_ <= settings_.target_c + settings_.hold_band_c;
    if (!in_band) {
      in_band_ = false;
      hold_s_ = 0;
      state_ = RUNNING;
      reason_ = "RUNNING";
    } else {
      if (!in_band_) {
        in_band_ = true;
        hold_started_ms_ = now_ms;
        hold_s_ = 0;
      } else {
        hold_s_ = elapsed(now_ms, hold_started_ms_) / 1000UL;
      }
      state_ = HOLD;
      reason_ = "HOLD";
    }
    regulate(settings_.target_c, settings_.target_c, true, now_ms);
  }

  void updateHold(uint32_t now_ms) {
    const bool in_band = tc1_c_ >= settings_.target_c - settings_.hold_band_c &&
                         tc1_c_ <= settings_.target_c + settings_.hold_band_c;
    if (!in_band) {
      in_band_ = false;
      hold_s_ = 0;
      state_ = RUNNING;
      return;
    }

    if (!in_band_) {
      in_band_ = true;
      hold_started_ms_ = now_ms;
      hold_s_ = 0;
    } else {
      hold_s_ = elapsed(now_ms, hold_started_ms_) / 1000UL;
    }
    state_ = HOLD;
    if (settings_.hold_duration_ms != 0 &&
        elapsed(now_ms, hold_started_ms_) >= settings_.hold_duration_ms) {
      setHeater(false, now_ms);
      state_ = COMPLETE;
      reason_ = "HOLD_COMPLETE";
    }
  }

  void recordSlopeSample(uint32_t now_ms, float tc1_c) {
    history_[history_next_].time_ms = now_ms;
    history_[history_next_].tc1_c = tc1_c;
    history_next_ = (uint8_t)((history_next_ + 1) % HISTORY_SIZE);
    if (history_count_ < HISTORY_SIZE) ++history_count_;

    uint32_t oldest_age = 0;
    float oldest_tc1 = tc1_c;
    for (uint8_t i = 0; i < history_count_; ++i) {
      const uint32_t age = elapsed(now_ms, history_[i].time_ms);
      if (age > 0 && age <= SLOPE_WINDOW_MS && age >= oldest_age) {
        oldest_age = age;
        oldest_tc1 = history_[i].tc1_c;
      }
    }
    const float slope = oldest_age > 0
                            ? (tc1_c - oldest_tc1) /
                                  ((float)oldest_age / 1000.0f)
                            : 0.0f;
    slope_c_per_s_ = finite(slope) ? slope : 0.0f;
  }

  Settings settings_;
  Program program_;
  Phase phase_;
  float setpoint_c_;
  State state_;
  const char *reason_;
  bool heater_on_;
  uint32_t output_changed_ms_;
  uint32_t request_id_;
  bool command_ok_;

  bool heartbeat_seen_;
  uint32_t last_heartbeat_ms_;
  bool sample_valid_;
  uint32_t last_sample_ms_;
  uint32_t last_raw_sample_ms_;
  float tc1_c_;
  float tc2_c_;
  float slope_c_per_s_;
  SlopeSample history_[HISTORY_SIZE];
  uint8_t history_count_;
  uint8_t history_next_;

  bool in_band_;
  uint32_t hold_started_ms_;
  uint32_t hold_s_;
  uint32_t ramp_started_ms_;
};

}  // namespace che126_exp2

#endif
