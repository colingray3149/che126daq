// Native behavioral checks against the same controller compiled into the Mega sketch.
// Run: c++ -std=c++17 -Wall -Wextra -pedantic tests/exp2_controller_test.cpp -o /tmp/exp2-controller-test && /tmp/exp2-controller-test
#include "../firmware/thermocouple_logger/exp2_controller.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

using che126_exp2::Controller;
using che126_exp2::Phase;
using che126_exp2::Settings;
using che126_exp2::BOOST_FINAL;
using che126_exp2::HEAT_100;
using che126_exp2::HOLD_100;
using che126_exp2::HOLD_FINAL;
using che126_exp2::RAMP_200;

static void expectSettings(const Controller &c, const Settings &expected) {
    const Settings &actual=c.settings();
    assert(actual.target_c==expected.target_c);
    assert(actual.hysteresis_c==expected.hysteresis_c);
    assert(actual.tc1_cutoff_c==expected.tc1_cutoff_c);
    assert(actual.tc2_cutoff_c==expected.tc2_cutoff_c);
    assert(actual.tc2_cutoff_enabled==expected.tc2_cutoff_enabled);
    assert(actual.prediction_lead_ms==expected.prediction_lead_ms);
    assert(actual.min_off_ms==expected.min_off_ms);
    assert(actual.hold_band_c==expected.hold_band_c);
    assert(actual.hold_duration_ms==expected.hold_duration_ms);
    assert(actual.swap_inputs==expected.swap_inputs);
}

static uint32_t ready(Controller &c, uint32_t base=0, float hot=25, float rear=25) {
    c.reset(base);
    uint32_t now=base;
    for (unsigned i=0; i<12; ++i) {
        now+=500;
        c.handleCommand("EXP2 PING",now);
        c.onSample(now,hot,rear);
    }
    return now;
}

static void armLine(Controller &c, const char *line, uint32_t now,
                    float hot=25, float rear=25) {
    c.handleCommand(line,now);
    assert(c.commandOk());
    c.handleCommand("EXP2 PING",now+500);
    c.onSample(now+500,hot,rear);
}

static void arm(Controller &c, uint32_t now, float hot=25, float rear=25) {
    armLine(c,"EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 0",
            now,hot,rear);
}

static void armExp4(Controller &c, uint32_t now, float raw1=25, float raw2=25) {
    armLine(c,"EXP4 START 1 700 3 730 85 1 5000 5000 5 0 1",
            now,raw1,raw2);
    assert(c.program()==che126_exp2::PROGRAM_EXP4);
    assert(c.phase()==HEAT_100);
    assert(c.tc2Required());
    assert(c.setpointC()==100.0f);
}

static void armExp4NoPrediction(Controller &c, uint32_t now) {
    armLine(c,"EXP4 START 1 700 3 730 85 1 0 0 5 0 1",now);
    assert(c.commandOk());
    assert(c.phase()==HEAT_100);
}

static uint32_t reachExp4Phase(Controller &c, Phase desired, uint32_t base=0) {
    uint32_t now=ready(c,base);
    armExp4NoPrediction(c,now);
    now+=500;
    if (desired==HEAT_100) return now;

    c.handleCommand("EXP2 PING",now+500);
    c.onSample(now+500,25,100);
    now+=500;
    assert(c.phase()==HOLD_100);
    assert(c.state()==che126_exp2::HOLD);
    if (desired==HOLD_100) return now;

    c.handleCommand("EXP4 NEXT 2",now);
    assert(c.commandOk());
    assert(c.phase()==RAMP_200);
    if (desired==RAMP_200) return now;

    c.handleCommand("EXP2 PING",now+500);
    c.onSample(now+500,25,200);
    now+=500;
    assert(c.phase()==BOOST_FINAL);
    assert(c.heaterOn());
    if (desired==BOOST_FINAL) return now;

    c.handleCommand("EXP2 PING",now+500);
    c.onSample(now+500,25,700);
    now+=500;
    assert(c.phase()==HOLD_FINAL);
    assert(!c.heaterOn());
    return now;
}

static float phaseHeater(Phase phase) {
    return phase==HEAT_100 ? 25.0f :
           phase==HOLD_100 || phase==RAMP_200 ? 100.0f :
           phase==BOOST_FINAL ? 200.0f : 700.0f;
}

int main() {
    {
        Controller c;
        const Settings defaults=Controller::defaultSettings();
        expectSettings(c,defaults);
        assert(c.settings().target_c==300.0f);
        assert(c.settings().hysteresis_c==3.0f);
        assert(c.settings().tc1_cutoff_c==320.0f);
        assert(c.settings().tc2_cutoff_c==140.0f);
        assert(c.settings().tc2_cutoff_enabled);
        assert(c.settings().prediction_lead_ms==5000);
        assert(c.settings().min_off_ms==5000);
        assert(c.settings().hold_band_c==5.0f);
        assert(c.settings().hold_duration_ms==1800000);
        assert(!c.settings().swap_inputs);
        assert(c.program()==che126_exp2::PROGRAM_SINGLE);
        assert(c.phase()==che126_exp2::SINGLE);
        assert(!c.tc2Required());
        assert(c.setpointC()==300.0f);
        assert(c.slopeCPerSecond()==0.0f);
        const Settings exp4=Controller::defaultExp4Settings();
        assert(exp4.target_c==700.0f);
        assert(exp4.tc1_cutoff_c==730.0f);
        assert(exp4.tc2_cutoff_c==85.0f);
        assert(exp4.hold_duration_ms==0);
        assert(exp4.swap_inputs);
    }
    {
        Controller c; uint32_t now=ready(c,0,95,25);
        c.handleCommand("EXP2 START 42 100 10 150 120 1 0 0 4 2000 0",now);
        assert(c.commandOk());
        assert(c.requestId()==42);
        assert(strcmp(c.reason(),"START")==0);
        Settings expected=Controller::defaultSettings();
        expected.target_c=100; expected.hysteresis_c=10;
        expected.tc1_cutoff_c=150; expected.tc2_cutoff_c=120;
        expected.prediction_lead_ms=0; expected.min_off_ms=0;
        expected.hold_band_c=4; expected.hold_duration_ms=2000;
        expectSettings(c,expected);  // Applied in the immediate START acknowledgement.

        c.handleCommand("EXP2 START 43 100 10 150",now);
        assert(!c.commandOk());
        assert(c.requestId()==43);
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        expectSettings(c,expected);  // Rejection cannot partially mutate settings.

        c.handleCommand("EXP2 START 44 100 10 150 120 1 0 0 4 2000 0",now);
        assert(c.commandOk());  // Repeated START is a new manual re-arm.
        assert(c.holdSeconds()==0);
        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,95,25);
        assert(!c.heaterOn());  // Above the configured 90 C re-enable threshold.
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,90,25);
        assert(c.heaterOn());
        c.handleCommand("EXP2 PING",now+1500);
        c.onSample(now+1500,100,25);
        assert(!c.heaterOn());  // The new target, not 300 C, cuts off.
        expectSettings(c,expected);
    }
    {
        Controller c;
        c.handleCommand("EXP2 START 77 1e6 0 -1e6 1e6 0 0 0 0 0 0",0);
        assert(c.commandOk());  // Bounded exponent forms and reversed cutoffs are valid.
        assert(c.settings().target_c==1000000.0f);
        assert(c.settings().tc1_cutoff_c==-1000000.0f);
        assert(c.settings().tc2_cutoff_c==1000000.0f);
        assert(!c.settings().tc2_cutoff_enabled);
        assert(c.settings().hold_duration_ms==0);
    }
    {
        Controller c;
        c.handleCommand("EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 0",0);  // No samples, PING, or startup streak.
        assert(c.commandOk());
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        assert(!c.heaterOn());
        c.update(0);
        assert(!c.heaterOn());  // Acceptance does not bypass runtime interlocks.
    }
    {
        Controller c;
        uint32_t now=ready(c);
        assert(!c.heaterOn());
        arm(c,now);
        assert(c.heaterOn());
        c.onSample(now+1000,25,139.75f);
        assert(c.heaterOn());
        c.onSample(now+1500,25,140.0f);
        assert(!c.heaterOn());
        assert(strcmp(Controller::stateName(c.state()),"TRIPPED")==0);
        assert(strcmp(c.reason(),"TC2_LIMIT")==0);
        c.handleCommand("EXP2 PING",now+2000);
        c.onSample(now+2000,25,25);
        assert(!c.heaterOn());  // Cooling alone must never re-arm.
        assert(strcmp(Controller::stateName(c.state()),"TRIPPED")==0);
        c.handleCommand("EXP2 START 2 300 3 320 140 1 5000 5000 5 1800000 0",now+2000);
        assert(c.commandOk());  // An explicit operator START does re-arm.
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        assert(!c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c); arm(c,now);
        c.onSample(now+1000,NAN,140);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"TC2_LIMIT")==0);
    }
    for (unsigned which=0; which<4; ++which) {
        Controller c; uint32_t now=ready(c); arm(c,now);
        float a=which==0 ? NAN : which==2 ? 0 : 25;
        float b=which==1 ? NAN : which==3 ? 0 : 25;
        c.onSample(now+1000,a,b);
        if (which==0 || which==2) {
            assert(!c.heaterOn());
            assert(strcmp(Controller::stateName(c.state()),"TRIPPED")==0);
            assert(strcmp(c.reason(),"SENSOR_FAULT")==0);
        } else {
            assert(c.heaterOn());  // Missing TC2 does not block TC1-only tests.
            assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        }
    }
    {
        Controller c; uint32_t now=ready(c); arm(c,now);
        c.onSample(now+1000,320,25);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"HOT_LIMIT")==0);
    }
    {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP2 START 1 100 3 150 42 1 0 0 5 0 0",now);
        assert(c.heaterOn());
        c.onSample(now+1000,25,41.75f);
        assert(c.heaterOn());
        c.onSample(now+1500,25,42);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"TC2_LIMIT")==0);
    }
    {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP2 START 1 100 3 120 140 1 0 0 5 0 0",now);
        assert(c.heaterOn());
        c.onSample(now+1000,120,25);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"HOT_LIMIT")==0);
    }
    {
        Controller c; uint32_t now=ready(c,0,25,42);
        armLine(c,"EXP2 START 1 100 3 120 42 0 0 0 5 0 0",now,25,42);
        assert(c.heaterOn());
        assert(!c.settings().tc2_cutoff_enabled);
        c.onSample(now+1000,25,100);
        assert(c.heaterOn());
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
    }
    {
        Controller c; uint32_t now=ready(c); arm(c,now);
        c.handleCommand("EXP2 PING",now+1500);
        c.update(now+2001);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"SENSOR_STALE")==0);
    }
    {
        Controller c; uint32_t now=ready(c); arm(c,now);
        c.onSample(now+2900,25,25);
        c.update(now+3001);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"HOST_TIMEOUT")==0);
    }
    {
        Controller c; uint32_t now=ready(c); arm(c,now);
        c.onSample(now+1000,299,25);  // Predictive OFF before reaching target.
        assert(!c.heaterOn());
        c.handleCommand("EXP2 PING",now+1500);
        c.onSample(now+1500,25,25);
        assert(!c.heaterOn());  // Do not reclose during minimum OFF dwell.
    }
    {
        Controller c; uint32_t now=ready(c,0,90,25);
        armLine(c,"EXP2 START 1 100 5 150 120 1 5000 0 5 0 0",now,90,25);
        assert(c.heaterOn());
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,96,25);  // Trailing 5 s slope is 1.2 C/s: projects to 102 C.
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"HOLD")==0);
    }
    {
        Controller c; uint32_t now=ready(c,0,90,25);
        armLine(c,"EXP2 START 1 100 5 150 120 1 0 0 5 0 0",now,90,25);
        assert(c.heaterOn());
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,96,25);
        assert(c.heaterOn());  // Zero lead disables prediction, not target cutoff.
    }
    {
        Controller c; uint32_t now=ready(c,0,90,25);
        armLine(c,"EXP2 START 1 100 5 150 120 1 0 5000 5 0 0",now,90,25);
        assert(c.heaterOn());
        const uint32_t off=now+1000;
        c.handleCommand("EXP2 PING",off);
        c.onSample(off,100,25);
        assert(!c.heaterOn());
        for (unsigned i=1; i<=9; ++i) {
            c.handleCommand("EXP2 PING",off+i*500);
            c.onSample(off+i*500,90,25);
            assert(!c.heaterOn());  // Includes 4.5 s, before configured dwell.
        }
        c.handleCommand("EXP2 PING",off+5000);
        c.onSample(off+5000,90,25);
        assert(c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c); arm(c,now);
        c.handleCommand("EXP2 STOP 2",now+501);
        assert(!c.heaterOn());
        c.onSample(now+1000,25,25);
        assert(!c.heaterOn());  // STOP remains latched without a new START.
        c.handleCommand("EXP2 START 3 300 3 320 140 1 5000 5000 5 1800000 0",now+1000);
        assert(c.commandOk());
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        assert(!c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c,0,0,25);
        c.handleCommand("EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 0",now);
        assert(c.commandOk());  // No sensor preflight, including invalid TC1.
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        c.update(now);
        assert(!c.heaterOn());  // Runtime feedback interlock still cuts heat.
        assert(strcmp(Controller::stateName(c.state()),"TRIPPED")==0);
    }
    {
        Controller c; uint32_t now=ready(c,0,300,25); arm(c,now,300,25);
        for (unsigned i=1; i<=20; ++i) {
            c.handleCommand("EXP2 PING",now+500+i*500);
            c.onSample(now+500+i*500,300,25);
        }
        assert(c.holdSeconds()>=9);
        c.handleCommand("EXP2 START 2 300 3 320 140 1 5000 5000 5 1800000 0",now+10500);
        assert(c.commandOk());
        assert(c.holdSeconds()==0);  // Every explicit START begins a new hold.
        now+=11000;
        c.handleCommand("EXP2 PING",now);
        c.onSample(now,310,25);
        assert(c.holdSeconds()==0);
        for (unsigned i=1; i<=3602; ++i) {
            c.handleCommand("EXP2 PING",now+i*500);
            c.onSample(now+i*500,300,25);
        }
        assert(strcmp(Controller::stateName(c.state()),"COMPLETE")==0);
        assert(!c.heaterOn());
        c.handleCommand("EXP2 START 3 300 3 320 140 1 5000 5000 5 1800000 0",now+1801000);
        assert(c.commandOk());
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        assert(!c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c,0,100,25);
        armLine(c,"EXP2 START 1 100 3 320 140 1 5000 5000 5 0 0",now,100,25);
        assert(strcmp(Controller::stateName(c.state()),"HOLD")==0);
        for (unsigned i=1; i<=3602; ++i) {
            c.handleCommand("EXP2 PING",now+500+i*500);
            c.onSample(now+500+i*500,100,25);
        }
        assert(strcmp(Controller::stateName(c.state()),"HOLD")==0);
        assert(c.holdSeconds()>=1800);  // Zero duration never completes.
        assert(!c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c,0,100,25);
        armLine(c,"EXP2 START 1 100 3 320 140 1 5000 5000 2 2000 0",now,100,25);
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,103,25);
        assert(strcmp(Controller::stateName(c.state()),"RUNNING")==0);
        c.handleCommand("EXP2 PING",now+1500);
        c.onSample(now+1500,102,25);  // Inclusive edge of the new +/-2 C band.
        assert(strcmp(Controller::stateName(c.state()),"HOLD")==0);
        for (unsigned i=1; i<=4; ++i) {
            c.handleCommand("EXP2 PING",now+1500+i*500);
            c.onSample(now+1500+i*500,100,25);
        }
        assert(strcmp(Controller::stateName(c.state()),"COMPLETE")==0);
        assert(!c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c,0,25,NAN);
        arm(c,now,25,NAN);
        assert(c.heaterOn());
        c.onSample(now+1000,299,NAN);
        assert(!c.heaterOn());  // Single-TC regulation still predicts cutoff.
        assert(strcmp(Controller::stateName(c.state()),"HOLD")==0);
    }
    {
        Controller c; uint32_t now=ready(c,UINT32_MAX-3000); arm(c,now);
        assert(c.heaterOn());
        c.onSample(now+1000,25,140);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"TC2_LIMIT")==0);
    }
    {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP2 START 1 100 5 120 85 1 0 0 5 0 1",now);
        assert(c.settings().swap_inputs);
        assert(c.heaterOn());  // Raw TC2 is the logical heater feedback.
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,25,100);
        assert(!c.heaterOn());  // Raw TC2 reaching target requests OFF.
        c.handleCommand("EXP2 PING",now+1500);
        c.onSample(now+1500,25,95);
        assert(c.heaterOn());  // Raw TC2 also controls re-enable.
        c.onSample(now+2000,25,120);
        assert(!c.heaterOn());
        assert(strcmp(c.reason(),"HOT_LIMIT")==0);
    }
    {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP2 START 1 300 3 320 85 1 5000 5000 5 1800000 1",now);
        assert(c.heaterOn());
        c.onSample(now+1000,84.75f,25);
        assert(c.heaterOn());
        c.onSample(now+1500,85,25);
        assert(!c.heaterOn());  // Raw TC1 is the logical rear probe.
        assert(strcmp(c.reason(),"TC2_LIMIT")==0);
    }
    for (unsigned which=0; which<2; ++which) {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP2 START 1 300 3 320 85 1 5000 5000 5 1800000 1",now);
        assert(c.heaterOn());
        c.onSample(now+1000,25,which==0 ? NAN : 0);
        assert(!c.heaterOn());
        assert(strcmp(Controller::stateName(c.state()),"TRIPPED")==0);
        assert(strcmp(c.reason(),"SENSOR_FAULT")==0);
    }
    {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP2 START 1 300 3 320 85 1 5000 5000 5 1800000 1",now);
        assert(c.heaterOn());
        c.onSample(now+1000,NAN,25);
        assert(c.heaterOn());  // Raw TC1 remains optional rear feedback.
    }
    {
        Controller c; uint32_t now=ready(c,0,25,98);
        c.onSample(now+500,30,98);
        assert(c.slopeCPerSecond()>0.0f);
        const uint32_t start=now+500;
        c.handleCommand("EXP2 START 1 100 5 150 120 1 0 0 5 0 1",start);
        assert(c.commandOk());
        assert(c.settings().swap_inputs);
        assert(c.slopeCPerSecond()==0.0f);  // Old raw TC1 slope is not reusable.
        c.update(start);
        assert(!c.heaterOn());  // Cached raw TC2=98, not raw TC1=30, is hot.

        c.handleCommand("EXP2 PING",start+500);
        c.onSample(start+500,30,98);
        assert(c.slopeCPerSecond()==0.0f);
        c.handleCommand("EXP2 PING",start+1000);
        c.onSample(start+1000,30,99);
        assert(fabs(c.slopeCPerSecond()-1.0f)<0.0001f);  // Reseeded from raw TC2.

        const Settings expected=c.settings();
        c.handleCommand("EXP2 START 2 50 1 150 120 1 0 0 5 0 2",start+1000);
        assert(!c.commandOk());
        expectSettings(c,expected);  // Bad swap field cannot partially re-map START.
        assert(c.settings().swap_inputs);
        assert(strcmp(Controller::stateName(c.state()),"HOLD")==0);

        c.update(start+2500);
        assert(strcmp(c.reason(),"SENSOR_STALE")==0);  // START did not refresh sample time.
        c.handleCommand("EXP2 START 3 100 5 150 120 1 0 0 5 0 0",start+2500);
        assert(c.commandOk());
        assert(!c.settings().swap_inputs);
        c.onSample(start+3000,30,98);
        assert(c.heaterOn());  // Mapping can change back on a later manual START.
    }
    {
        Controller c; uint32_t now=ready(c);
        c.handleCommand("EXP4 NEXT 8",now);
        assert(!c.commandOk());  // NEXT is meaningless to the single program.
        assert(c.phase()==che126_exp2::SINGLE);

        armExp4NoPrediction(c,now);
        now+=500;
        assert(c.heaterOn());
        const Settings expected=c.settings();
        c.handleCommand("EXP4 NEXT 9",now);
        assert(!c.commandOk());  // Early NEXT cannot queue a later transition.
        assert(c.requestId()==9);
        assert(c.phase()==HEAT_100);
        assert(c.heaterOn());
        expectSettings(c,expected);

        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,100);
        now+=500;
        assert(c.phase()==HOLD_100);
        assert(!c.heaterOn());
        for (unsigned i=1; i<=10; ++i) {
            c.handleCommand("EXP2 PING",now+i*500);
            c.onSample(now+i*500,25,100);
            assert(c.phase()==HOLD_100);  // No hold timer can synthesize NEXT.
        }
        now+=5000;
        c.handleCommand("EXP4 NEXT 10",now);
        assert(c.commandOk());
        assert(c.requestId()==10);
        assert(c.phase()==RAMP_200);
        assert(c.state()==che126_exp2::RUNNING);
        assert(c.setpointC()==100.0f);
        assert(!c.heaterOn());

        const char *const rejected[]={"EXP4 NEXT 11","EXP4 NEXT 999","EXP4 NEXT 0",
                                      "EXP4 NEXT 12 extra","EXP2 NEXT 13"};
        for (unsigned i=0; i<sizeof(rejected)/sizeof(rejected[0]); ++i) {
            c.handleCommand(rejected[i],now);
            assert(!c.commandOk());
            assert(c.phase()==RAMP_200);
            assert(c.setpointC()==100.0f);
            assert(!c.heaterOn());  // Duplicate/new-id NEXT changes no trajectory/output.
            expectSettings(c,expected);
        }
    }
    {
        Controller c;
        const uint32_t now=reachExp4Phase(c,RAMP_200,UINT32_MAX-10000);
        for (unsigned i=1; i<=91; ++i) {
            const uint32_t t=now+i*1000;
            c.handleCommand("EXP2 PING",t);
            c.onSample(t,25,25);
            assert(c.phase()==RAMP_200);
            if (i==45) assert(fabs(c.setpointC()-150.0f)<0.0001f);
        }
        assert(fabs(c.setpointC()-200.0f)<0.0001f);
        assert(c.state()==che126_exp2::RUNNING);  // Ninety seconds alone is not 200 C.
        assert(c.heaterOn());

        c.handleCommand("EXP2 PING",now+92000);
        c.onSample(now+92000,25,200);
        assert(c.phase()==BOOST_FINAL);  // Measured crossing, including across millis wrap.
        assert(c.setpointC()==700.0f);
        assert(c.heaterOn());
        c.handleCommand("EXP2 PING",now+93000);
        c.onSample(now+93000,25,700);
        assert(c.phase()==HOLD_FINAL);
        assert(!c.heaterOn());
        assert(c.state()==che126_exp2::HOLD);
    }
    {
        Controller c; uint32_t now=ready(c);
        armLine(c,"EXP4 START 1 700 3 730 85 1 0 5000 5 0 1",now);
        now+=500;
        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,100);
        now+=500;
        assert(c.phase()==HOLD_100);
        assert(!c.heaterOn());
        const uint32_t off=now;
        c.handleCommand("EXP4 NEXT 2",now);
        assert(c.commandOk());
        c.handleCommand("EXP2 PING",off+500);
        c.onSample(off+500,25,150);
        assert(!c.heaterOn());
        c.handleCommand("EXP2 PING",off+1000);
        c.onSample(off+1000,25,200);
        assert(c.phase()==BOOST_FINAL);
        assert(!c.heaterOn());  // Crossing 200 C shortly after OFF cannot bypass dwell.
        for (unsigned i=2; i<=5; ++i) {
            c.handleCommand("EXP2 PING",off+i*1000);
            c.onSample(off+i*1000,25,200);
            assert(c.heaterOn()==(i==5));
        }
    }
    {
        Controller c; uint32_t now=ready(c); armExp4(c,now); now+=500;
        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,100);
        now+=500;
        assert(c.phase()==HOLD_100);
        c.handleCommand("EXP4 NEXT 2",now);
        assert(c.commandOk());
        for (unsigned i=1; i<=91; ++i) {
            const uint32_t t=now+i*1000;
            c.handleCommand("EXP2 PING",t);
            c.onSample(t,25,199);
        }
        assert(c.phase()==RAMP_200);
        assert(c.setpointC()==200.0f);
        assert(c.heaterOn());  // Saturated reference cannot trap at 199 C.
        c.handleCommand("EXP2 PING",now+92000);
        c.onSample(now+92000,25,200);
        assert(c.phase()==BOOST_FINAL);
        assert(c.heaterOn());
    }
    {
        Controller c; uint32_t now=ready(c); armExp4(c,now); now+=500;
        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,100);
        now+=500;
        assert(c.phase()==HOLD_100);
        c.handleCommand("EXP4 NEXT 2",now);
        assert(c.commandOk());

        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,190);
        now+=500;
        assert(c.phase()==RAMP_200);
        for (unsigned i=1; i<=12; ++i) {
            c.handleCommand("EXP2 PING",now+i*500);
            c.onSample(now+i*500,25,190);
        }
        now+=6000;  // Flush the old jump out of the trailing slope window.
        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,200);
        now+=500;
        assert(c.phase()==BOOST_FINAL);
        assert(c.heaterOn());  // Continuous ON, never a fixed-duty boost.

        c.handleCommand("EXP2 PING",now+500);
        c.onSample(now+500,25,600);
        now+=500;
        assert(c.phase()==HOLD_FINAL);  // Predicted intercept precedes measured 700 C.
        assert(!c.heaterOn());
        assert(c.setpointC()==700.0f);
        assert(c.state()==che126_exp2::RUNNING);
        assert(c.holdSeconds()==0);  // Predictive capture below band is not hold time.
        const uint32_t final_start=now;
        for (unsigned i=1; i<=1801; ++i) {
            const uint32_t t=final_start+i*1000;
            c.handleCommand("EXP2 PING",t);
            c.onSample(t,25,600);
        }
        assert(c.phase()==HOLD_FINAL);
        assert(c.state()==che126_exp2::RUNNING);  // No legacy 1800 s completion.
        assert(c.holdSeconds()==0);

        now=final_start+1801000;
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,25,700);
        now+=1000;
        assert(c.state()==che126_exp2::HOLD);
        assert(c.holdSeconds()==0);
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,25,700);
        now+=1000;
        assert(c.holdSeconds()==1);
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,25,600);
        now+=1000;
        assert(c.phase()==HOLD_FINAL);
        assert(c.state()==che126_exp2::RUNNING);
        assert(c.holdSeconds()==0);  // Leaving the band resets continuous hold time.
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,25,700);
        now+=1000;
        assert(c.state()==che126_exp2::HOLD);
        assert(c.holdSeconds()==0);
        c.handleCommand("EXP2 PING",now+1000);
        c.onSample(now+1000,25,700);
        assert(c.holdSeconds()==1);
    }
    {
        const Phase phases[]={HEAT_100,HOLD_100,RAMP_200,BOOST_FINAL,HOLD_FINAL};
        for (unsigned i=0; i<sizeof(phases)/sizeof(phases[0]); ++i) {
            Controller c;
            const uint32_t now=reachExp4Phase(c,phases[i]);
            c.onSample(now+500,85,phaseHeater(phases[i]));
            assert(!c.heaterOn());
            assert(c.state()==che126_exp2::TRIPPED);
            assert(strcmp(c.reason(),"TC2_LIMIT")==0);
            assert(c.phase()==phases[i]);  // Rear limit wins over any transition.
        }
        for (unsigned i=0; i<sizeof(phases)/sizeof(phases[0]); ++i) {
            Controller c;
            const uint32_t now=reachExp4Phase(c,phases[i]);
            c.onSample(now+500,NAN,phaseHeater(phases[i]));
            assert(!c.heaterOn());
            assert(c.state()==che126_exp2::TRIPPED);
            assert(strcmp(c.reason(),"TC2_FAULT")==0);
            assert(c.phase()==phases[i]);
        }
        for (unsigned i=0; i<sizeof(phases)/sizeof(phases[0]); ++i) {
            Controller c;
            const uint32_t now=reachExp4Phase(c,phases[i]);
            c.handleCommand("EXP2 STOP 99",now+500);
            assert(c.commandOk());
            assert(!c.heaterOn());
            assert(c.state()==che126_exp2::STOPPED);
            assert(strcmp(c.reason(),"STOP")==0);
            assert(c.phase()==phases[i]);  // STOP never erases diagnostic phase.
        }
    }
    {
        Controller c;
        const uint32_t now=reachExp4Phase(c,RAMP_200);
        c.update(now+1500);
        assert(!c.heaterOn());
        assert(c.state()==che126_exp2::TRIPPED);
        assert(strcmp(c.reason(),"SENSOR_STALE")==0);
        assert(c.phase()==RAMP_200);
    }
    {
        Controller c;
        const uint32_t now=reachExp4Phase(c,RAMP_200);
        const Settings expected=c.settings();
        const bool output=c.heaterOn();
        static const char *const invalid[] = {
            "EXP4 START 90 200 3 730 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700.001 3 730 85 1 5000 5000 5 0 1",
            "EXP4 START 90 701 3 730 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 700 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730.001 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 731 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730 84.999 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730 85.001 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730 85 0 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730 85 1 5000 5000 5 1 1",
            "EXP4 START 90 700 5.001 730 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730 85 1 5000 5000 5.001 0 1",
            "EXP4 START 90 700 3 730 85 1 2147483648 5000 5 0 1",
            "EXP4 START 90 700 3 730 85 1 5000 2147483648 5 0 1",
            "EXP4 START 90 700 -1 730 85 1 5000 5000 5 0 1",
            "EXP4 START 90 700 3 730 85 1 5000 5000 5 0 2"
        };
        for (unsigned i=0; i<sizeof(invalid)/sizeof(invalid[0]); ++i) {
            assert(c.handleCommand(invalid[i],now));
            assert(!c.commandOk());
            assert(c.requestId()==90);
            assert(c.phase()==RAMP_200);
            assert(c.setpointC()==100.0f);
            assert(c.heaterOn()==output);
            expectSettings(c,expected);  // Rejection is atomic in every field.
        }
    }
    {
        static const char *const invalid[] = {
            "EXP2 START",
            "EXP2 START 1",
            "EXP2 START 0 300 3 320 140 1 5000 5000 5 1800000 0",
            "EXP2 START 4294967296 300 3 320 140 1 5000 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 140 2 5000 5000 5 1800000 0",
            "EXP2 START 1 300 -1 320 140 1 5000 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 140 1 -1 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 140 1 2147483648 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 140 1 5000 -1 5 1800000 0",
            "EXP2 START 1 300 3 320 140 1 5000 5000 -5 1800000 0",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 -1 0",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 2147483648 0",
            "EXP2 START 1 1.00001e6 3 320 140 1 5000 5000 5 1800000 0",
            "EXP2 START 1 300 3 -1.00001e6 140 1 5000 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 nan 1 5000 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 inf 1 5000 5000 5 1800000 0",
            "EXP2 START 1 1.234567 3 320 140 1 5000 5000 5 1800000 0",
            "EXP2 START 1 1e 3 320 140 1 5000 5000 5 1800000 0",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 2",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 -1",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 0 9",
            "EXP2 START 1 300 3 320 140 1 5000 5000 5 1800000 0 "
        };
        Controller c;
        const Settings expected=c.settings();
        for (unsigned i=0; i<sizeof(invalid)/sizeof(invalid[0]); ++i) {
            assert(c.handleCommand(invalid[i],0));
            assert(!c.commandOk());
            assert(!c.heaterOn());
            assert(strcmp(Controller::stateName(c.state()),"IDLE")==0);
            assert(strcmp(c.reason(),"BAD_COMMAND")==0);
            expectSettings(c,expected);
        }
    }
    puts("EXP2/EXP4 passed: v5 atomic envelopes, explicit NEXT, staged ramp/boost/final hold, all-phase rear/STOP interlocks, staleness, mapping and millis rollover; legacy single-target behavior preserved.");
}
