#ifndef CHE126_EXP2_CONTROLLER_H
#define CHE126_EXP2_CONTROLLER_H

#include <float.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// CHE126 experiments 2/3/4/5/6/7/8, protocol "exp2-v6"; START explicitly re-arms.
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

enum Program : uint8_t {
  PROGRAM_SINGLE,
  PROGRAM_EXP4,
  PROGRAM_EXP5,
  PROGRAM_EXP6,
  PROGRAM_EXP7,
  PROGRAM_EXP8
};

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
  float feedback_cutoff_c;
  float rear_cutoff_c;
  bool rear_cutoff_enabled;
  uint32_t prediction_lead_ms;
  uint32_t min_off_ms;
  float hold_band_c;
  uint32_t hold_duration_ms;
  uint8_t feedback_channel;
  uint8_t rear_channel;
  uint8_t external_channel;
  float preheat_target_c;
  float ramp_target_c;
  uint32_t ramp_duration_ms;
};

class Controller {
public:
  // These defaults are used only at hardware boot/reset. Every accepted START
  // supplies and atomically applies a complete replacement Settings value.
  static Settings defaultSettings() {
    Settings settings;
    settings.target_c = 300.0f;
    settings.hysteresis_c = 3.0f;
    settings.feedback_cutoff_c = 320.0f;
    settings.rear_cutoff_c = 140.0f;
    settings.rear_cutoff_enabled = true;
    settings.prediction_lead_ms = 5000UL;
    settings.min_off_ms = 5000UL;
    settings.hold_band_c = 5.0f;
    settings.hold_duration_ms = 1800000UL;
    settings.feedback_channel = 2;
    settings.rear_channel = 1;
    settings.external_channel = 2;
    settings.preheat_target_c = 100.0f;
    settings.ramp_target_c = 200.0f;
    settings.ramp_duration_ms = 90000UL;
    return settings;
  }

  static Settings defaultExp4Settings() {
    Settings settings = defaultSettings();
    settings.target_c = 700.0f;
    settings.hysteresis_c = 3.0f;
    settings.feedback_cutoff_c = 730.0f;
    settings.rear_cutoff_c = 85.0f;
    settings.rear_cutoff_enabled = true;
    settings.prediction_lead_ms = 5000UL;
    settings.min_off_ms = 5000UL;
    settings.hold_band_c = 5.0f;
    settings.hold_duration_ms = 0;
    settings.feedback_channel = 3;
    settings.rear_channel = 1;
    return settings;
  }

  static Settings defaultExp5Settings() {
    Settings settings = defaultExp4Settings();
    settings.rear_cutoff_c = 120.0f;
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
    raw_sample_seen_ = false;
    raw_tc_c_[0] = 0.0f;
    raw_tc_c_[1] = 0.0f;
    raw_tc_c_[2] = 0.0f;
    feedback_c_ = 0.0f;
    rear_c_ = 0.0f;
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
  void onSample(uint32_t now_ms, float raw_tc1_c, float raw_tc2_c,
                float raw_tc3_c) {
    raw_tc_c_[0] = raw_tc1_c;
    raw_tc_c_[1] = raw_tc2_c;
    raw_tc_c_[2] = raw_tc3_c;
    raw_sample_seen_ = true;
    last_raw_sample_ms_ = now_ms;
    selectCachedChannels();

    // EXP7 uses external feedback before boost, internal feedback afterward.
    // Internal high-limit/fault protection remains active throughout EXP7.
    const float high_limit_c = raw_tc_c_[settings_.feedback_channel - 1];
    const bool finite_feedback = finite(high_limit_c);
    const bool finite_rear = finite(rear_c_);
    const bool checked = validFeedback();

    if (checked) {
      sample_valid_ = true;
      last_sample_ms_ = now_ms;
      recordSlopeSample(now_ms, feedback_c_);
    } else {
      sample_valid_ = false;
      slope_c_per_s_ = 0.0f;
      history_count_ = 0;
      history_next_ = 0;
    }

    if (active()) {
      // Rear protection has explicit priority, including bad feedback.
      if (settings_.rear_cutoff_enabled && finite_rear &&
          rear_c_ >= settings_.rear_cutoff_c) {
        trip("REAR_LIMIT", now_ms);
      } else if (stagedProgram() && !finite_rear) {
        trip("REAR_FAULT", now_ms);
      } else if (finite_feedback && high_limit_c >= settings_.feedback_cutoff_c) {
        trip("HOT_LIMIT", now_ms);
      } else if (!checked) {
        trip("SENSOR_FAULT", now_ms);
      }
    } else if (state_ == IDLE) {
      if (settings_.rear_cutoff_enabled && finite_rear &&
          rear_c_ >= settings_.rear_cutoff_c) {
        reason_ = "REAR_LIMIT";
      } else if (finite_feedback && high_limit_c >= settings_.feedback_cutoff_c) {
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
    if (settings_.rear_cutoff_enabled && finite(rear_c_) &&
        rear_c_ >= settings_.rear_cutoff_c) {
      trip("REAR_LIMIT", now_ms);
      return;
    }
    if (stagedProgram() && !finite(rear_c_)) {
      trip("REAR_FAULT", now_ms);
      return;
    }
    if (finite(raw_tc_c_[settings_.feedback_channel - 1]) &&
        raw_tc_c_[settings_.feedback_channel - 1] >= settings_.feedback_cutoff_c) {
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

    if (program_ == PROGRAM_EXP7 || program_ == PROGRAM_EXP8) {
      updateExp7(now_ms);
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
    static const char EXP6_START_PREFIX[] = "EXP6 START ";
    static const char EXP6_NEXT_PREFIX[] = "EXP6 NEXT ";
    static const char EXP7_START_PREFIX[] = "EXP7 START ";
    static const char EXP7_NEXT_PREFIX[] = "EXP7 NEXT ";
    static const char EXP8_START_PREFIX[] = "EXP8 START ";
    static const char EXP8_NEXT_PREFIX[] = "EXP8 NEXT ";
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

    if (strncmp(line, EXP6_START_PREFIX, sizeof(EXP6_START_PREFIX) - 1) == 0) {
      Settings candidate;
      const bool valid =
          parseStart(line + sizeof(EXP6_START_PREFIX) - 1, id, candidate) &&
          validExp5Settings(candidate);
      request_id_ = id;
      command_ok_ = false;
      if (!valid) {
        reject("BAD_COMMAND");
        return true;
      }
      start(id, candidate, PROGRAM_EXP6, now_ms);
      return true;
    }

    if (strncmp(line, EXP7_START_PREFIX, sizeof(EXP7_START_PREFIX) - 1) == 0) {
      Settings candidate;
      const bool valid =
          parseStart(line + sizeof(EXP7_START_PREFIX) - 1, id, candidate, true) &&
          validExp7Settings(candidate);
      request_id_ = id;
      command_ok_ = false;
      if (!valid) {
        reject("BAD_COMMAND");
        return true;
      }
      start(id, candidate, PROGRAM_EXP7, now_ms);
      return true;
    }

    if (strncmp(line, EXP8_START_PREFIX, sizeof(EXP8_START_PREFIX) - 1) == 0) {
      Settings candidate;
      const bool valid = parseStart(line + sizeof(EXP8_START_PREFIX) - 1, id, candidate, true) &&
                         validExp8Settings(candidate);
      request_id_ = id;
      command_ok_ = false;
      if (!valid) {
        reject("BAD_COMMAND");
        return true;
      }
      start(id, candidate, PROGRAM_EXP8, now_ms);
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

    if (strncmp(line, EXP6_NEXT_PREFIX, sizeof(EXP6_NEXT_PREFIX) - 1) == 0) {
      const bool valid_id = parsePositiveId(line + sizeof(EXP6_NEXT_PREFIX) - 1, id);
      request_id_ = id;
      command_ok_ = false;
      if (!valid_id) {
        reject("BAD_COMMAND");
        return true;
      }
      next(id, PROGRAM_EXP6, now_ms);
      return true;
    }

    if (strncmp(line, EXP7_NEXT_PREFIX, sizeof(EXP7_NEXT_PREFIX) - 1) == 0) {
      const bool valid_id = parsePositiveId(line + sizeof(EXP7_NEXT_PREFIX) - 1, id);
      request_id_ = id;
      command_ok_ = false;
      if (!valid_id) {
        reject("BAD_COMMAND");
        return true;
      }
      next(id, PROGRAM_EXP7, now_ms);
      return true;
    }

    if (strncmp(line, EXP8_NEXT_PREFIX, sizeof(EXP8_NEXT_PREFIX) - 1) == 0) {
      const bool valid_id = parsePositiveId(line + sizeof(EXP8_NEXT_PREFIX) - 1, id);
      request_id_ = id;
      command_ok_ = false;
      if (!valid_id) {
        reject("BAD_COMMAND");
        return true;
      }
      next(id, PROGRAM_EXP8, now_ms);
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
  bool rearRequired() const { return stagedProgram(); }
  const Settings &settings() const { return settings_; }
  float setpointC() const { return setpoint_c_; }
  float slopeCPerSecond() const { return slope_c_per_s_; }
  uint8_t phaseFeedbackChannel() const {
    return program_ == PROGRAM_EXP7 &&
                   (phase_ == HEAT_100 || phase_ == HOLD_100 || phase_ == RAMP_200)
               ? settings_.external_channel : settings_.feedback_channel;
  }

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
    if (program == PROGRAM_EXP6) return "exp6";
    if (program == PROGRAM_EXP7) return "exp7";
    if (program == PROGRAM_EXP8) return "exp8";
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
    float feedback_c;
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
           finite(settings.feedback_cutoff_c) && settings.feedback_cutoff_c >= -limit &&
           settings.feedback_cutoff_c <= limit && finite(settings.rear_cutoff_c) &&
           settings.rear_cutoff_c >= -limit && settings.rear_cutoff_c <= limit &&
           settings.prediction_lead_ms <= MAX_DURATION_MS &&
           settings.min_off_ms <= MAX_DURATION_MS &&
           finite(settings.hold_band_c) && settings.hold_band_c >= 0.0f &&
           settings.hold_band_c <= limit &&
           settings.hold_duration_ms <= MAX_DURATION_MS &&
           settings.feedback_channel >= 1 && settings.feedback_channel <= 3 &&
           settings.rear_channel >= 1 && settings.rear_channel <= 3 &&
           settings.feedback_channel != settings.rear_channel;
  }

  static bool validExp4Settings(const Settings &settings) {
    return settings.target_c > 200.0f && settings.target_c <= 700.0f &&
           settings.target_c < settings.feedback_cutoff_c &&
           settings.feedback_cutoff_c <= 730.0f &&
           settings.rear_cutoff_enabled && settings.rear_cutoff_c > 0.0f &&
           settings.rear_cutoff_c <= 85.0f && settings.hold_duration_ms == 0 &&
           settings.hysteresis_c <= 5.0f && settings.hold_band_c <= 5.0f;
  }

  static bool validExp5Settings(const Settings &settings) {
    return settings.target_c > 200.0f && settings.target_c <= 700.0f &&
           settings.target_c < settings.feedback_cutoff_c &&
           settings.feedback_cutoff_c <= 730.0f &&
           settings.rear_cutoff_enabled && settings.rear_cutoff_c > 0.0f &&
           settings.rear_cutoff_c <= 120.0f &&
           settings.hold_duration_ms > 0 &&
           settings.hold_duration_ms <= MAX_DURATION_MS &&
           settings.hysteresis_c <= 5.0f && settings.hold_band_c <= 5.0f;
  }

  static bool validExp7Settings(const Settings &settings) {
    return validExp5Settings(settings) &&
           settings.external_channel >= 1 && settings.external_channel <= 3 &&
           settings.external_channel != settings.feedback_channel &&
           settings.external_channel != settings.rear_channel &&
           finite(settings.preheat_target_c) && settings.preheat_target_c > 0 &&
           finite(settings.ramp_target_c) &&
           settings.preheat_target_c < settings.ramp_target_c &&
           settings.ramp_target_c < settings.target_c &&
           settings.ramp_duration_ms <= MAX_DURATION_MS;
  }

  static bool validExp8Settings(const Settings &settings) {
    return settings.target_c > 200.0f && settings.target_c <= 700.0f &&
           settings.feedback_cutoff_c <= 730.0f &&
           settings.rear_cutoff_enabled && settings.rear_cutoff_c > 0.0f &&
           settings.rear_cutoff_c <= 120.0f && settings.hold_duration_ms > 0 &&
           settings.hold_duration_ms <= MAX_DURATION_MS &&
           settings.hysteresis_c <= 5.0f && settings.hold_band_c <= 5.0f &&
           settings.feedback_channel == 2 && settings.external_channel == 2 &&
           settings.rear_channel == 1 && finite(settings.preheat_target_c) &&
           settings.preheat_target_c > 0 && finite(settings.ramp_target_c) &&
           settings.preheat_target_c < settings.ramp_target_c &&
           settings.ramp_target_c < settings.target_c &&
           settings.ramp_target_c < settings.feedback_cutoff_c &&
           settings.ramp_duration_ms <= MAX_DURATION_MS;
  }

  static bool parseChannel(const char *&text, uint8_t &channel, bool last) {
    uint32_t value = 0;
    if (!parseUnsigned(text, 3, value, last) || value == 0) return false;
    channel = (uint8_t)value;
    return true;
  }

  // Parse every START field into independent outputs. id remains available
  // for rejection acknowledgement after a valid id but a bad settings field.
  static bool parseStart(const char *text, uint32_t &id, Settings &settings,
                         bool exp7 = false) {
    settings = defaultSettings();
    id = 0;
    return parseUnsigned(text, 4294967295UL, id, false) && id > 0 &&
           parseFloat(text, settings.target_c, false) &&
           parseFloat(text, settings.hysteresis_c, false) &&
           parseFloat(text, settings.feedback_cutoff_c, false) &&
           parseFloat(text, settings.rear_cutoff_c, false) &&
           parseBool(text, settings.rear_cutoff_enabled, false) &&
           parseUnsigned(text, MAX_DURATION_MS, settings.prediction_lead_ms,
                         false) &&
           parseUnsigned(text, MAX_DURATION_MS, settings.min_off_ms, false) &&
           parseFloat(text, settings.hold_band_c, false) &&
           parseUnsigned(text, MAX_DURATION_MS, settings.hold_duration_ms,
                         false) &&
           parseChannel(text, settings.feedback_channel, false) &&
           parseChannel(text, settings.rear_channel, !exp7) &&
           (!exp7 || (parseChannel(text, settings.external_channel, false) &&
                      parseFloat(text, settings.preheat_target_c, false) &&
                      parseFloat(text, settings.ramp_target_c, false) &&
                      parseUnsigned(text, MAX_DURATION_MS,
                                    settings.ramp_duration_ms, true))) &&
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
    return program_ == PROGRAM_EXP4 || program_ == PROGRAM_EXP5 ||
           program_ == PROGRAM_EXP6 || program_ == PROGRAM_EXP7 ||
           program_ == PROGRAM_EXP8;
  }

  // EXP5/EXP6/EXP7 share wall-clock final holds; EXP6/EXP7 use ungated NEXT.
  bool timedFinal() const {
    return program_ == PROGRAM_EXP5 || program_ == PROGRAM_EXP6 ||
           program_ == PROGRAM_EXP7;
  }

  bool active() const { return state_ == RUNNING || state_ == HOLD; }

  void reject(const char *reason) {
    command_ok_ = false;
    // Preserve the latched cause in terminal states.
    if (state_ == IDLE || active()) reason_ = reason;
  }

  void selectCachedChannels() {
    feedback_c_ = raw_tc_c_[phaseFeedbackChannel() - 1];
    rear_c_ = raw_tc_c_[settings_.rear_channel - 1];
  }

  bool validFeedback() const {
    const float internal_c = raw_tc_c_[settings_.feedback_channel - 1];
    return finite(feedback_c_) && feedback_c_ > 0.0f &&
           (program_ != PROGRAM_EXP7 || (finite(internal_c) && internal_c > 0.0f));
  }

  void reseedPhaseFeedback() {
    selectCachedChannels();
    sample_valid_ = raw_sample_seen_ && validFeedback();
    slope_c_per_s_ = 0.0f;
    history_count_ = 0;
    history_next_ = 0;
    if (sample_valid_) {
      last_sample_ms_ = last_raw_sample_ms_;
      recordSlopeSample(last_sample_ms_, feedback_c_);
    }
  }

  void start(uint32_t id, const Settings &settings, Program program,
             uint32_t now_ms) {
    const uint8_t previous_source = phaseFeedbackChannel();
    settings_ = settings;
    program_ = program;
    phase_ = stagedProgram() ? HEAT_100 : SINGLE;
    const bool feedback_changed = previous_source != phaseFeedbackChannel();
    selectCachedChannels();

    // Reuse only the last physical acquisition. A new feedback source starts a
    // new slope history and inherits that acquisition's original timestamp;
    // START itself never makes cached data fresh or substitutes another probe.
    sample_valid_ = raw_sample_seen_ && validFeedback();
    if (feedback_changed) {
      slope_c_per_s_ = 0.0f;
      history_count_ = 0;
      history_next_ = 0;
    }
    if (sample_valid_) {
      last_sample_ms_ = last_raw_sample_ms_;
      if (feedback_changed) recordSlopeSample(last_sample_ms_, feedback_c_);
    }
    setpoint_c_ = (program_ == PROGRAM_EXP7 || program_ == PROGRAM_EXP8)
                      ? settings_.preheat_target_c
                      : stagedProgram() ? 100.0f : settings_.target_c;
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
    if (expected_program == PROGRAM_EXP7 || expected_program == PROGRAM_EXP8) {
      // Valid EXP7/EXP8 NEXT is always acknowledged. EXP8 has exactly two
      // transitions: entry/wait to ramp, then boost to the TC513 timed hold.
      request_id_ = id;
      command_ok_ = true;
      if (program_ == expected_program && active() &&
          (phase_ == HEAT_100 || phase_ == HOLD_100)) {
        phase_ = RAMP_200;
        state_ = RUNNING;
        setpoint_c_ = settings_.preheat_target_c;
        ramp_started_ms_ = now_ms;
        hold_s_ = 0;
        reason_ = "NEXT";
      } else if (expected_program == PROGRAM_EXP8 && program_ == PROGRAM_EXP8 &&
                 active() && phase_ == BOOST_FINAL) {
        phase_ = HOLD_FINAL;
        state_ = HOLD;
        setpoint_c_ = settings_.target_c;
        hold_started_ms_ = now_ms;
        hold_s_ = 0;
        reason_ = "TC513_TIMED_HOLD";
      }
      return;
    }
    const bool in_band = feedback_c_ >= 100.0f - settings_.hold_band_c &&
                         feedback_c_ <= 100.0f + settings_.hold_band_c;
    const bool ungated_next =
        program_ == PROGRAM_EXP6 || program_ == PROGRAM_EXP7;
    const bool ready = ungated_next
                           ? phase_ == HEAT_100 || phase_ == HOLD_100
                           : phase_ == HOLD_100 && in_band;
    if (program_ != expected_program || !active() || !ready) {
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
        feedback_c_ + positive_slope * ((float)settings_.prediction_lead_ms / 1000.0f);
    const bool projected_cutoff = projected >= future_target_c;

    if (heater_on_) {
      // This forecast includes TC1 >= target even with zero/negative slope. OFF
      // is always immediate; a predictive pulse may be shorter than the dwell.
      if (projected_cutoff) setHeater(false, now_ms);
    } else if (feedback_c_ <= target_c - settings_.hysteresis_c &&
               !projected_cutoff &&
               elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms) {
      // Never switch ON when the cutoff is already true. The OFF dwell bounds
      // re-enable frequency without delaying any safety/predictive OFF.
      setHeater(true, now_ms);
    }
  }

  float exp7RampReference(uint32_t age) const {
    if (settings_.ramp_duration_ms == 0 || age >= settings_.ramp_duration_ms)
      return settings_.ramp_target_c;
    return settings_.preheat_target_c +
           (settings_.ramp_target_c - settings_.preheat_target_c) *
               ((float)age / (float)settings_.ramp_duration_ms);
  }

  void updateExp7(uint32_t now_ms) {
    if (phase_ == HEAT_100) {
      setpoint_c_ = settings_.preheat_target_c;
      if (feedback_c_ >= settings_.preheat_target_c) {
        phase_ = HOLD_100;
        state_ = HOLD;
        reason_ = "WAIT_NEXT";
        setHeater(false, now_ms);
      } else if (elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms) {
        setHeater(true, now_ms);
      }
      return;
    }
    if (phase_ == HOLD_100) {
      // Reaching external 100 C latches OFF; cooling never reheats this stage.
      state_ = HOLD;
      reason_ = "WAIT_NEXT";
      setHeater(false, now_ms);
      return;
    }
    if (phase_ == RAMP_200) {
      const uint32_t age = elapsed(now_ms, ramp_started_ms_);
      setpoint_c_ = exp7RampReference(age);
      if (feedback_c_ >= settings_.ramp_target_c) {
        phase_ = BOOST_FINAL;
        setpoint_c_ = settings_.target_c;
        reseedPhaseFeedback();  // Internal source; never carry external slope.
      } else {
        state_ = RUNNING;
        reason_ = "RUNNING";
        if (age >= settings_.ramp_duration_ms) {
          if (elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms)
            setHeater(true, now_ms);
        } else {
          const uint32_t remaining = settings_.ramp_duration_ms - age;
          const uint32_t future = settings_.prediction_lead_ms >= remaining
                                      ? settings_.ramp_duration_ms
                                      : age + settings_.prediction_lead_ms;
          regulate(setpoint_c_, exp7RampReference(future), true, now_ms);
        }
        return;
      }
    }
    if (phase_ == BOOST_FINAL) {
      if (program_ == PROGRAM_EXP8) {
        // TC513 alone regulates the internal 650 C setpoint. D33 is only a
        // continuous series permission until the operator starts the hold.
        state_ = RUNNING;
        reason_ = "WAIT_TC513_CONFIRM";
        setpoint_c_ = settings_.target_c;
        hold_s_ = 0;
        if (elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms)
          setHeater(true, now_ms);
        return;
      }
      state_ = RUNNING;
      reason_ = "RUNNING";
      if (feedback_c_ < settings_.target_c) {
        if (elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms)
          setHeater(true, now_ms);
        return;
      }
      phase_ = HOLD_FINAL;
      hold_started_ms_ = now_ms;
      hold_s_ = 0;
    }
    if (program_ == PROGRAM_EXP8) {
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
      reason_ = "TC513_TIMED_HOLD";
      if (elapsed(now_ms, output_changed_ms_) >= settings_.min_off_ms)
        setHeater(true, now_ms);
      return;
    }
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
    regulate(settings_.target_c, settings_.target_c, false, now_ms);
  }

  void updateStaged(uint32_t now_ms) {
    if (phase_ == HEAT_100 || phase_ == HOLD_100) {
      const bool in_band = feedback_c_ >= 100.0f - settings_.hold_band_c &&
                           feedback_c_ <= 100.0f + settings_.hold_band_c;
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
      if (feedback_c_ >= 200.0f) {
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
      if (timedFinal()) {
        if (feedback_c_ < settings_.target_c) {
          // Timed programs ignore slope prediction during boost: only measured
          // feedback may end maximum heat and start the final hold.
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
            feedback_c_ + positive_slope * ((float)settings_.prediction_lead_ms / 1000.0f);
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

    if (timedFinal()) {
      // Timed final holds run from the first measured target crossing. Leaving
      // the regulation band neither pauses nor resets the wall-clock timer.
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
        feedback_c_ >= settings_.target_c - settings_.hold_band_c &&
        feedback_c_ <= settings_.target_c + settings_.hold_band_c;
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
    const bool in_band = feedback_c_ >= settings_.target_c - settings_.hold_band_c &&
                         feedback_c_ <= settings_.target_c + settings_.hold_band_c;
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

  void recordSlopeSample(uint32_t now_ms, float feedback_c) {
    history_[history_next_].time_ms = now_ms;
    history_[history_next_].feedback_c = feedback_c;
    history_next_ = (uint8_t)((history_next_ + 1) % HISTORY_SIZE);
    if (history_count_ < HISTORY_SIZE) ++history_count_;

    uint32_t oldest_age = 0;
    float oldest_feedback = feedback_c;
    for (uint8_t i = 0; i < history_count_; ++i) {
      const uint32_t age = elapsed(now_ms, history_[i].time_ms);
      if (age > 0 && age <= SLOPE_WINDOW_MS && age >= oldest_age) {
        oldest_age = age;
        oldest_feedback = history_[i].feedback_c;
      }
    }
    const float slope = oldest_age > 0
                            ? (feedback_c - oldest_feedback) /
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
  bool raw_sample_seen_;
  float raw_tc_c_[3];
  float feedback_c_;
  float rear_c_;
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
