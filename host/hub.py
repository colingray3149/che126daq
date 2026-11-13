#!/usr/bin/env python3
"""Local serial DAQ with acknowledged Experiment 2/3/4 control; never uploads firmware."""
import argparse
import asyncio
from collections import deque
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shlex
import time
import tomllib

from aiohttp import web
import plotly
import serial
from serial.tools import list_ports

FIELDS = ['utc', 'host_elapsed_s', 'board_time_s', 'epoch', 'tc1_C', 'tc2_C', 'flags']
CONTROLLER_PROTOCOL = 'exp2-v5'
CONTROLLER_STATES = {'IDLE', 'RUNNING', 'HOLD', 'TRIPPED', 'COMPLETE', 'STOPPED'}
CONTROLLER_PROGRAMS = {'single', 'exp4', 'exp5', 'exp6'}
CONTROLLER_PHASES = {'SINGLE', 'HEAT_100', 'HOLD_100', 'RAMP_200', 'BOOST_FINAL', 'HOLD_FINAL'}
STAGED_PHASES = CONTROLLER_PHASES - {'SINGLE'}
STAGED_PROGRAMS = {'exp4', 'exp5', 'exp6'}
ACTIVE_STATES = {'RUNNING', 'HOLD'}
EXPERIMENT_KEYS = ('target_C', 'hysteresis_C', 'tc1_cutoff_C', 'tc2_cutoff_C',
                   'tc2_cutoff_enabled', 'prediction_lead_s', 'min_off_s',
                   'hold_band_C', 'hold_s', 'swap_inputs')
EXPERIMENT_PROFILES = {
    'exp2': {'filename': 'experiment.toml', 'title': 'Experiment 2'},
    'exp3': {'filename': 'experiment3.toml', 'title': 'Experiment 3'},
    'exp4': {'filename': 'experiment4.toml', 'title': 'Experiment 4'},
    'exp5': {'filename': 'experiment5.toml', 'title': 'Experiment 5'},
    'exp6': {'filename': 'experiment6.toml', 'title': 'Experiment 6'},
}
TEMPERATURE_KEYS = ('target_C', 'tc1_cutoff_C', 'tc2_cutoff_C')
NONNEGATIVE_C_KEYS = ('hysteresis_C', 'hold_band_C')
DURATION_KEYS = ('prediction_lead_s', 'min_off_s', 'hold_s')
MAX_DURATION_MS = 2147483647
SETTINGS_FLOAT_TOLERANCE = 0.0011
TELEMETRY_FRESH_S = 1.5
SAMPLE_FRESH_S = 1.5
ACK_TIMEOUT_S = 2.5
HEARTBEAT_PERIOD_S = 0.5
WRITE_TIMEOUT_S = 0.5


class ControlError(ValueError):
    """A command was not acknowledged; reported output is not physical proof."""


HELP = '''Auto-start: the first successful serial connection starts a saved run.
start              Start a new saved run (or keep the active one).
start exp2         Start Experiment 2 with experiment.toml; no sensor/reset preflight.
start exp3         Start Experiment 3 with experiment3.toml; no sensor/reset preflight.
start exp4         Start Experiment 4 with experiment4.toml; no sensor/reset preflight.
start exp5         Start Experiment 5 with experiment5.toml; no sensor/reset preflight.
start exp6         Start Experiment 6 with experiment6.toml (EXP5 with an ungated next).
next               Advance EXP4/EXP5 from HOLD_100, EXP6 from anywhere in the 100 C stage.
stop               STOP an active experiment, await acknowledgement, then finalize.
stop exp2/exp3/exp4/exp5/exp6
                   Request universal STOP and await acknowledgement; keep cooldown logging.
restart            Finalize current run and start a fresh directory (not while active).
save               Flush current files and report their location; keep recording.
clear              Clear this browser's plot/console only; never delete data.
list               List saved runs, newest first.
view 001           Plot saved data, marked HISTORICAL; recording continues.
live               Restore the current run's live plot.
note your text     Append a comment to the active run, even in historical view.
window 120         Show the latest 120 seconds (window all for retained points).
status             Show connection, recording, controller freshness and faults.
config / channels  Show hub and experiment settings; experiment edits apply on next START.
reconnect          Close/reopen serial once; refused while an experiment is active.
help               Show commands. Up/Down recalls command history.
Experiment 2 assumes 30 V RMS, Experiment 3 assumes 65 V RMS, and Experiments 4/5/6
assume 100 V RMS manual presets. EXP4/EXP5/EXP6 hold at 100 C until explicit next;
EXP5/EXP6 then regulate at its final target for 60 seconds before COMPLETE.
The variac is never set or measured by this software; voltage never rescales data.
Raw CSV tc1_C/tc2_C always mean physical input channels 1/2, including swapped runs.
The requested COM-NC, active-HIGH relay profile FAILS ON if Arduino power/reset
removes the relay drive; software and acknowledgements cannot make that fail-safe.
Serial acknowledgements and heater_on are board reports, not physical proof.
Plots retain at most the configured plot_points; CSV retains every saved row.
NaN is a fault/gap, not zero. All-zero readings do not validate sensors.
No probe identity or calibration is inferred.'''


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class Run:
    def __init__(self, root, config, device, run_metadata):
        root.mkdir(parents=True, exist_ok=True)
        number = max((int(p.name) for p in root.iterdir() if p.name.isdecimal()), default=0) + 1
        while True:
            self.path = root / f'{number:03d}'
            try:
                self.path.mkdir()
                break
            except FileExistsError:
                number += 1
        self.started = utc()
        self.clock = time.monotonic()
        self.rows = 0
        self.config = config
        self.device = device
        self.barrier = run_metadata.get('barrier')
        with (self.path / 'run-metadata.json').open('x') as stream:
            json.dump(run_metadata, stream, indent=2)
            stream.write('\n')
        self.data = (self.path / 'data.csv').open('x', newline='')
        self.writer = csv.writer(self.data)
        self.writer.writerow(FIELDS)
        self.events = (self.path / 'events.csv').open('x', newline='')
        self.event_writer = csv.writer(self.events)
        self.event_writer.writerow(['utc', 'event'])
        self.metadata('recording')
        self.flush()

    def metadata(self, reason):
        path = self.path / 'notes.md'
        # Only the generated prefix is replaced. Everything after Comments is user-owned.
        if path.exists():
            old = path.read_text()
            marker = '## Comments\n'
            if marker not in old:
                raise ValueError('notes.md has no ## Comments heading; refusing to overwrite it')
            comments = old.split(marker, 1)[1]
        else:
            comments = '\n'
        body = (f'# Run {self.path.name}\n\n'
                f'- Started UTC: {self.started}\n- Updated UTC: {utc()}\n'
                f'- State / stop reason: {reason}\n- Samples: {self.rows}\n'
                f'- Serial at start: {self.device}\n'
                + (f'- Barrier: {self.barrier}\n' if self.barrier else '') +
                '- Units: seconds, degrees Celsius; UTC is host wall time.\n'
                '- host_elapsed_s: monotonic seconds since run start; board_time_s: original uptime.\n'
                '- epoch increments on board time regression; flags preserve sensor faults and zero caveats.\n'
                '- TC1 CLK/DO/CS: 22/24/26; TC2: 28/30/32 (saved firmware map, not a wiring inspection).\n'
                '- Probe identity, attachment and calibration: unverified.\n\n'
                '## Configuration\n\n```json\n' + json.dumps(self.config, indent=2) + '\n```\n\n'
                '## Comments\n' + comments)
        temporary = self.path / '.notes.tmp'
        temporary.write_text(body)
        temporary.replace(path)

    def append(self, board, epoch, values, flags):
        elapsed = time.monotonic() - self.clock
        stamp = utc()
        self.writer.writerow([stamp, f'{elapsed:.6f}', board, epoch,
                              *('nan' if v is None else v for v in values), ';'.join(flags)])
        self.data.flush()
        self.rows += 1
        return [elapsed, *values]

    def event(self, text):
        self.event_writer.writerow([utc(), text])
        self.events.flush()

    def flush(self):
        self.data.flush()
        self.events.flush()

    def record_experiment(self, source, requested, applied, request_id):
        (self.path / 'experiment.toml').write_bytes(source)
        snapshot = {'request_id': request_id, 'requested': requested, 'applied': applied}
        (self.path / 'experiment-applied.json').write_text(json.dumps(snapshot, indent=2) + '\n')

    def note(self, text):
        with (self.path / 'notes.md').open('a') as f:
            f.write(f'\n- {utc()} — {text}\n')

    def finish(self, reason):
        self.flush()
        try:
            self.metadata(reason)
        finally:
            self.data.close()
            self.events.close()


class Hub:
    def __init__(self, config, root, config_path):
        self.config = config
        self.root = root
        self.config_path = Path(config_path).resolve()
        self.experiment_paths = {
            profile: self.config_path.parent / details['filename']
            for profile, details in EXPERIMENT_PROFILES.items()
        }
        self.run_mappings_path = Path(__file__).parent / 'web' / 'run-mappings.json'
        self.run = None
        self.last_run = None
        self.points = deque(maxlen=config['plot_points'])
        self.sequence = 0
        self.events = deque(maxlen=30)
        self.port = None
        self.reader = None
        self.device = 'disconnected'
        self.auto_started = False
        self.last_board = None
        self.epoch = 0
        self.last_sample = None
        self.values = [None, None]
        self.zero_count = 0
        self.bad_rows = 0
        self.buffer = b''
        self.controller = None
        self.controller_received = None
        self.last_active = False
        self.control_uncertain = False
        self.pending = None
        self.request_id = 0
        self.command_lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()
        self.heartbeat = None
        self.heartbeat_error_reported = False

    @staticmethod
    def normalize_experiment(data):
        if not isinstance(data, dict):
            raise ValueError('experiment configuration must be a TOML table')
        keys = set(data)
        expected = set(EXPERIMENT_KEYS)
        if keys != expected:
            raise ValueError(f'experiment settings missing {sorted(expected - keys)}; '
                             f'unknown {sorted(keys - expected)}')

        def number(key):
            value = data[key]
            if type(value) not in (int, float):
                raise ValueError(f'{key} must be a finite number')
            try:
                value = float(value)
            except OverflowError as exc:
                raise ValueError(f'{key} must be a finite number') from exc
            if not math.isfinite(value):
                raise ValueError(f'{key} must be a finite number')
            return value

        settings = {}
        for key in TEMPERATURE_KEYS:
            value = number(key)
            if abs(value) > 1e6:
                raise ValueError(f'{key} must have absolute value <= 1000000')
            settings[key] = float(format(value, '.6g'))
        for key in NONNEGATIVE_C_KEYS:
            value = number(key)
            if not 0 <= value <= 1e6:
                raise ValueError(f'{key} must be in [0, 1000000]')
            settings[key] = float(format(value, '.6g'))
        if type(data['tc2_cutoff_enabled']) is not bool:
            raise ValueError('tc2_cutoff_enabled must be a boolean')
        if type(data['swap_inputs']) is not bool:
            raise ValueError('swap_inputs must be a boolean')
        for key in DURATION_KEYS:
            value = number(key)
            if value < 0 or value > MAX_DURATION_MS / 1000:
                raise ValueError(f'{key} must normalize to 0..{MAX_DURATION_MS} milliseconds')
            milliseconds = int(round(value * 1000))
            if not 0 <= milliseconds <= MAX_DURATION_MS:
                raise ValueError(f'{key} must normalize to 0..{MAX_DURATION_MS} milliseconds')
            settings[key] = milliseconds / 1000
        return {key: settings[key] if key not in {'tc2_cutoff_enabled', 'swap_inputs'} else data[key]
                for key in EXPERIMENT_KEYS}

    @staticmethod
    def validate_staged_settings(settings, program):
        """Validate EXP4/EXP5/EXP6 staged-program envelopes on normalized settings."""
        label = program.upper()
        if not 200 < settings['target_C'] <= 700:
            raise ValueError(f'{label} target_C must be > 200 and <= 700')
        if not settings['target_C'] < settings['tc1_cutoff_C'] <= 730:
            raise ValueError(f'{label} requires target_C < tc1_cutoff_C <= 730')
        rear_cutoff = 85 if program == 'exp4' else 120
        if settings['tc2_cutoff_C'] != rear_cutoff or settings['tc2_cutoff_enabled'] is not True:
            raise ValueError(f'{label} requires tc2_cutoff_C = {rear_cutoff} and tc2_cutoff_enabled = true')
        required_hold = 0 if program == 'exp4' else 60
        if settings['hold_s'] != required_hold:
            detail = 'final hold has no timer' if program == 'exp4' else 'final hold is timed'
            raise ValueError(f'{label} requires hold_s = {required_hold}; {detail}')
        if program != 'exp4' and (settings['target_C'] != 700 or settings['tc1_cutoff_C'] != 730):
            raise ValueError(f'{label} requires target_C = 700 and tc1_cutoff_C = 730')
        if not 0 <= settings['hysteresis_C'] <= 5:
            raise ValueError(f'{label} hysteresis_C must be in [0, 5]')
        if not 0 <= settings['hold_band_C'] <= 5:
            raise ValueError(f'{label} hold_band_C must be in [0, 5]')
        return settings

    @staticmethod
    def normalize_voltage(value):
        if type(value) not in (int, float):
            raise ValueError('variac_voltage_V must be a finite nonnegative number')
        try:
            value = float(value)
        except OverflowError as exc:
            raise ValueError('variac_voltage_V must be a finite nonnegative number') from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError('variac_voltage_V must be a finite nonnegative number')
        return value

    def load_experiment(self, profile='exp2'):
        if profile not in EXPERIMENT_PROFILES:
            raise ValueError(f'Unknown experiment profile {profile!r}')
        path = self.experiment_paths[profile]
        try:
            source = path.read_bytes()
            text = source.decode('utf-8')
            data = tomllib.loads(text)
            if not isinstance(data, dict) or 'variac_voltage_V' not in data:
                raise ValueError('variac_voltage_V host-only metadata is required')
            voltage = self.normalize_voltage(data.pop('variac_voltage_V'))
            barrier = data.pop('barrier', None)
            if barrier is not None and not isinstance(barrier, str):
                raise ValueError('barrier must be a string')
            settings = self.normalize_experiment(data)
            if profile in STAGED_PROGRAMS:
                self.validate_staged_settings(settings, profile)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f'Invalid experiment configuration {path}: {exc}') from exc
        metadata = {'experiment': profile, 'swap_inputs': settings['swap_inputs'],
                    'variac_voltage_V': float(voltage)}
        if barrier:
            metadata['barrier'] = barrier
        return source, text, settings, metadata

    @classmethod
    def validate_run_metadata(cls, data):
        if not isinstance(data, dict):
            raise ValueError('run metadata must be a JSON object')
        required = {'experiment', 'swap_inputs', 'variac_voltage_V'}
        if not required.issubset(data):
            raise ValueError(f'run metadata missing {sorted(required - data.keys())}')
        if data['experiment'] not in EXPERIMENT_PROFILES:
            raise ValueError(f'invalid run experiment {data["experiment"]!r}')
        if type(data['swap_inputs']) is not bool:
            raise ValueError('run swap_inputs must be a boolean')
        voltage = cls.normalize_voltage(data['variac_voltage_V'])
        metadata = {'experiment': data['experiment'], 'swap_inputs': data['swap_inputs'],
                    'variac_voltage_V': voltage}
        if isinstance(data.get('barrier'), str) and data['barrier']:
            metadata['barrier'] = data['barrier']
        return metadata

    def display_metadata(self, run_path=None):
        path = run_path or (self.run.path if self.run else self.last_run)
        if path is None and self.root.exists():
            runs = [p for p in self.root.iterdir() if p.is_dir() and p.name.isdecimal()]
            path = max(runs, key=lambda p: int(p.name), default=None)
        if path is None:
            return {'experiment': 'exp2', 'swap_inputs': False, 'variac_voltage_V': 30.0}
        path = Path(path)
        metadata_path = path / 'run-metadata.json'
        if metadata_path.exists():
            return self.validate_run_metadata(json.loads(metadata_path.read_text()))
        fallback = {'experiment': 'exp2', 'swap_inputs': False, 'variac_voltage_V': 30.0}
        if self.run_mappings_path.exists():
            mappings = json.loads(self.run_mappings_path.read_text())
            if not isinstance(mappings, dict):
                raise ValueError('run-mappings.json must be a JSON object')
            if path.name in mappings:
                annotation = mappings[path.name]
                if not isinstance(annotation, dict) or type(annotation.get('swap_inputs')) is not bool:
                    raise ValueError(f'invalid display mapping for run {path.name}')
                fallback['swap_inputs'] = annotation['swap_inputs']
        return fallback

    def event(self, text):
        self.events.append({'utc': utc(), 'text': text})
        print(f'{utc()} {text}', flush=True)
        if self.run:
            self.run.event(text)

    def start(self, run_metadata=None):
        if not self.run:
            if run_metadata is None:
                # Plain recording/restart preserves the latest known physical mapping.
                # Explicit start exp2/exp3/exp4 replaces it from the selected profile.
                # The barrier is named only by an explicit START, never inherited.
                run_metadata = dict(self.display_metadata())
                run_metadata.pop('barrier', None)
            run_metadata = self.validate_run_metadata(run_metadata)
            self.run = Run(self.root, self.config, self.device, run_metadata)
            self.last_run = self.run.path
            self.points.clear()
            self.event(f'Recording {self.run.path}')
        return f'Recording {self.run.path}'

    def stop(self, reason):
        if not self.run:
            return 'Already stopped.'
        run = self.run
        self.event(reason)
        self.run = None
        run.finish(reason)
        return f'Saved {run.rows} samples to {run.path}'

    @property
    def controller_available(self):
        return (self.port is not None and self.controller is not None
                and self.controller_received is not None
                and time.monotonic() - self.controller_received <= TELEMETRY_FRESH_S)

    @property
    def active(self):
        return (self.port is not None and self.controller is not None
                and self.controller['state'] in ACTIVE_STATES)

    def fail_pending(self, message):
        if self.pending and not self.pending['future'].done():
            self.pending['future'].set_exception(ControlError(message))

    def controller_disconnected(self):
        self.fail_pending('Serial disconnected before acknowledgement; command will not be retried and heater state is unknown.')
        self.controller_received = None
        self.heartbeat_error_reported = False
        if self.controller:
            self.event('Controller telemetry is disconnected/stale; last output report is not current and heater state is unknown.')

    def board_reset(self, message):
        self.event(message)
        self.fail_pending(f'{message}; pending command cancelled and will not be retried.')
        self.controller = None
        self.controller_received = None
        self.last_active = False
        self.control_uncertain = False
        self.last_board = None
        self.last_sample = None
        self.values = [None, None]
        self.zero_count = 0

    @staticmethod
    def validate_telemetry(data):
        if not isinstance(data, dict):
            raise ValueError('controller telemetry must be a JSON object')
        required = {'protocol', 'state', 'reason', 'heater_on', 'settings',
                    'tc2_required', 'relay_contact', 'active_high',
                    'hold_s', 'request_id', 'command_ok', 'program', 'phase',
                    'setpoint_C', 'slope_C_per_s'}
        if not required.issubset(data):
            raise ValueError(f'controller telemetry missing {sorted(required - data.keys())}')
        if data['protocol'] != CONTROLLER_PROTOCOL:
            raise ValueError(f'unsupported controller protocol {data["protocol"]!r}')
        if not isinstance(data['state'], str) or data['state'] not in CONTROLLER_STATES:
            raise ValueError(f'invalid controller state {data["state"]!r}')
        if not isinstance(data['program'], str) or data['program'] not in CONTROLLER_PROGRAMS:
            raise ValueError(f'invalid controller program {data["program"]!r}')
        if not isinstance(data['phase'], str) or data['phase'] not in CONTROLLER_PHASES:
            raise ValueError(f'invalid controller phase {data["phase"]!r}')
        if ((data['program'] == 'single' and data['phase'] != 'SINGLE')
                or (data['program'] in STAGED_PROGRAMS and data['phase'] not in STAGED_PHASES)):
            raise ValueError(f'controller program/phase mismatch: {data["program"]!r}/{data["phase"]!r}')
        if (type(data['tc2_required']) is not bool
                or data['tc2_required'] != (data['program'] in STAGED_PROGRAMS)):
            raise ValueError('tc2_required must be true for staged programs and false for single-target programs')
        for key in ('setpoint_C', 'slope_C_per_s'):
            try:
                finite = type(data[key]) in (int, float) and math.isfinite(data[key])
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f'{key} must be a finite number')
        if not isinstance(data['reason'], str) or not data['reason'].isascii() or len(data['reason']) > 160:
            raise ValueError('controller reason must be an ASCII string of at most 160 characters')
        if type(data['heater_on']) is not bool or type(data['active_high']) is not bool:
            raise ValueError('heater_on and active_high must be booleans')
        if type(data['command_ok']) is not bool:
            raise ValueError('command_ok must be a boolean')
        try:
            settings = Hub.normalize_experiment(data['settings'])
            if data['program'] in STAGED_PROGRAMS:
                Hub.validate_staged_settings(settings, data['program'])
        except ValueError as exc:
            raise ValueError(f'invalid controller settings: {exc}') from exc
        if data['relay_contact'] != 'NC' or data['active_high'] is not True:
            raise ValueError('controller is not the requested NC active-HIGH profile')
        if (isinstance(data['hold_s'], bool)
                or not isinstance(data['hold_s'], (int, float))
                or not math.isfinite(data['hold_s']) or data['hold_s'] < 0):
            raise ValueError('hold_s must be finite and nonnegative')
        if type(data['request_id']) is not int or data['request_id'] < 0:
            raise ValueError('request_id must be a nonnegative integer')
        return data

    def consume_telemetry(self, raw):
        try:
            text = raw.decode('ascii')
            if not text.startswith('#CTRL '):
                raise ValueError('expected #CTRL followed by one space')
            data = self.validate_telemetry(json.loads(text[6:]))
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self.bad_rows += 1
            self.controller_received = None
            self.fail_pending('Invalid controller telemetry; pending command outcome is unknown and will not be retried.')
            self.event(f'Invalid controller telemetry ignored; freshness invalidated ({exc}): {raw[:160]!r}')
            return
        previous = self.controller
        self.controller = data
        self.controller_received = time.monotonic()
        self.last_active = data['state'] in ACTIVE_STATES
        if data['state'] in {'TRIPPED', 'COMPLETE', 'STOPPED'} and not data['heater_on']:
            self.control_uncertain = False
        elif not self.last_active and data['heater_on']:
            self.control_uncertain = True
        if (previous is None
                or (previous['state'], previous['heater_on'], previous['program'], previous['phase'])
                != (data['state'], data['heater_on'], data['program'], data['phase'])):
            old = ('unavailable' if previous is None else
                   f'{previous["state"]}/{previous["program"]}/{previous["phase"]}/heater_on={previous["heater_on"]}')
            self.event(f'Controller report {old} -> {data["state"]}/{data["program"]}/{data["phase"]}/'
                       f'heater_on={data["heater_on"]}; reason={data["reason"]}; hold_s={data["hold_s"]}. '
                       'Serial report, not physical proof.')
        if self.pending and data['request_id'] == self.pending['id']:
            future = self.pending['future']
            if not future.done():
                future.set_result(dict(data))

    def next_request_id(self):
        self.request_id = 1 if self.request_id >= 4294967295 else self.request_id + 1
        return self.request_id

    async def write_line(self, text):
        data = text.encode('ascii')
        async with self.write_lock:
            port = self.port
            if port is None:
                raise ControlError(f'Cannot send {text.strip()}: serial disconnected; heater state unknown.')
            try:
                written = await asyncio.to_thread(port.write, data)
            except (serial.SerialException, OSError) as exc:
                raise ControlError(f'Failed writing {text.strip()}: {exc}; heater state unknown.') from exc
            if written != len(data):
                raise ControlError(f'Short serial write for {text.strip()}; heater state unknown.')

    async def request(self, verb, settings=None, program='single'):
        if verb not in {'START', 'NEXT', 'STOP'}:
            raise ValueError('Only internal START, NEXT and STOP requests are permitted')
        if program not in CONTROLLER_PROGRAMS:
            raise ValueError(f'Invalid controller program {program!r}')
        if verb == 'NEXT' and program not in STAGED_PROGRAMS:
            raise ValueError('NEXT is only valid for staged programs')
        if verb == 'START':
            if settings is None:
                raise ValueError('START requires normalized experiment settings')
            temperatures = [format(settings[key], '.6g') for key in
                            ('target_C', 'hysteresis_C', 'tc1_cutoff_C', 'tc2_cutoff_C')]
            durations = [str(int(round(settings[key] * 1000))) for key in DURATION_KEYS]
        elif settings is not None:
            raise ValueError(f'{verb} does not accept experiment settings')
        if self.pending:
            raise ControlError('Another controller request is still pending.')
        request_id = self.next_request_id()
        wire_program = program.upper() if program in STAGED_PROGRAMS and verb != 'STOP' else 'EXP2'
        if verb == 'START':
            command = (f'{wire_program} START {request_id} {" ".join(temperatures)} '
                       f'{int(settings["tc2_cutoff_enabled"])} {" ".join(durations[:2])} '
                       f'{format(settings["hold_band_C"], ".6g")} {durations[2]} '
                       f'{int(settings["swap_inputs"])}\n')
        else:
            command = f'{wire_program} {verb} {request_id}\n'
        future = asyncio.get_running_loop().create_future()
        pending = {'id': request_id, 'verb': verb, 'future': future,
                   'started': time.monotonic()}
        self.pending = pending
        self.event(f'Sending {wire_program} {verb} request_id={request_id}; no output change is assumed.')
        try:
            await self.write_line(command)
            acknowledgement = await asyncio.wait_for(future, ACK_TIMEOUT_S)
        except asyncio.TimeoutError as exc:
            self.event(f'{wire_program} {verb} request_id={request_id} acknowledgement timed out; '
                       'heater state and requested transition are unknown; command will not be retried.')
            raise ControlError(f'{wire_program} {verb} acknowledgement timed out; outcome unknown; '
                               'command will not be retried.') from exc
        finally:
            if self.pending is pending:
                self.pending = None
            if not future.done():
                future.cancel()
        self.event(f'{wire_program} {verb} request_id={request_id} acknowledgement: '
                   f'command_ok={acknowledgement["command_ok"]}, state={acknowledgement["state"]}, '
                   f'program={acknowledgement["program"]}, phase={acknowledgement["phase"]}, '
                   f'heater_on={acknowledgement["heater_on"]}; serial report, not physical proof.')
        return acknowledgement

    @staticmethod
    def settings_mismatches(requested, applied):
        mismatches = []
        for key in (*TEMPERATURE_KEYS, *NONNEGATIVE_C_KEYS):
            if abs(requested[key] - applied[key]) > SETTINGS_FLOAT_TOLERANCE:
                mismatches.append(f'{key}: requested={requested[key]}, acknowledged={applied[key]}')
        for key in DURATION_KEYS:
            requested_ms = int(round(requested[key] * 1000))
            applied_ms = int(round(applied[key] * 1000))
            if requested_ms != applied_ms:
                mismatches.append(f'{key}: requested={requested_ms}ms, acknowledged={applied_ms}ms')
        for key in ('tc2_cutoff_enabled', 'swap_inputs'):
            if requested[key] != applied[key]:
                mismatches.append(f'{key}: requested={requested[key]}, '
                                  f'acknowledged={applied[key]}')
        return mismatches

    async def best_effort_stop(self):
        try:
            acknowledgement = await self.request('STOP')
        except (ControlError, OSError) as exc:
            message = f'Best-effort STOP was not acknowledged: {exc}'
            self.event(message)
            return message
        if not acknowledgement['command_ok']:
            message = f'Best-effort STOP was rejected: {acknowledgement["reason"]}; heater state unknown.'
            self.event(message)
            return message
        if acknowledgement['state'] in ACTIVE_STATES or acknowledgement['heater_on']:
            message = 'STOP acknowledgement still reports an active/on controller; heater state is not confirmed safe.'
            self.event(message)
            return message
        self.last_active = False
        self.control_uncertain = False
        message = 'STOP acknowledged with a non-active, heater_on=false board report; not physical proof.'
        self.event(message)
        return message

    async def start_experiment(self, profile):
        if profile not in EXPERIMENT_PROFILES:
            raise ValueError(f'Unknown experiment profile {profile!r}')
        title = EXPERIMENT_PROFILES[profile]['title']
        # Load before changing the current run or serial output. Invalid/missing
        # configuration leaves the existing recording and controller untouched.
        source, _, requested, run_metadata = self.load_experiment(profile)
        # The operator chooses when to start. No sensor, temperature,
        # controller-state, reset, or telemetry-freshness preflight gates.
        controller = self.controller
        if self.run:
            self.stop(f'Finalizing previous run before {title}')
        self.start(run_metadata)
        self.event(f'{title} normalized requested settings: {json.dumps(requested, sort_keys=True)}')
        sensor_requirement = ('TC2 required; missing/nonfinite rear temperature trips OFF'
                              if profile in STAGED_PROGRAMS else 'TC2 optional')
        self.event(f'{title} profile: {sensor_requirement}; runtime cutoffs use the requested settings; '
                   f'NC active-HIGH relay; {run_metadata["variac_voltage_V"]:g} V RMS manual preset '
                   'assumed, not measured or set by software. Raw CSV channels remain physical inputs 1/2.')
        self.event('SAFETY: COM-NC FAILS ON when Arduino power/reset deenergizes the relay coil; '
                   'software control and acknowledgements cannot provide fail-safe power removal.')
        if controller:
            self.event(f'Pre-START report: {controller["state"]}/heater_on={controller["heater_on"]}; '
                       f'reason={controller["reason"]}; serial report only, not a start requirement.')
        try:
            # PING immediately before START supplies the board heartbeat without changing output.
            await self.write_line('EXP2 PING\n')
            self.control_uncertain = True
            acknowledgement = await self.request(
                'START', requested, profile if profile in STAGED_PROGRAMS else 'single')
        except ControlError as exc:
            if not self.control_uncertain:
                raise
            stop_message = await self.best_effort_stop()
            raise ControlError(f'{exc} {stop_message} No RUNNING/HOLD state was confirmed.') from exc
        except asyncio.CancelledError:
            if self.control_uncertain:
                await self.best_effort_stop()
            raise
        if not acknowledgement['command_ok']:
            self.control_uncertain = False
            raise ControlError(f'START rejected by board: {acknowledgement["reason"]}; no experiment start is claimed.')
        applied = dict(acknowledgement['settings'])
        self.event(f'{title} board acknowledged settings: {json.dumps(applied, sort_keys=True)}')
        mismatches = self.settings_mismatches(requested, applied)
        if mismatches:
            message = 'START settings acknowledgement mismatch: ' + '; '.join(mismatches)
            self.event(f'{message}; requested configuration is not confirmed active.')
            stop_message = await self.best_effort_stop()
            raise ControlError(f'{message}. {stop_message} No new configuration is claimed active.')
        expected_program = profile if profile in STAGED_PROGRAMS else 'single'
        expected_phase = 'HEAT_100' if profile in STAGED_PROGRAMS else 'SINGLE'
        if acknowledgement['program'] != expected_program:
            message = (f'START program acknowledgement mismatch: requested={expected_program}, '
                       f'acknowledged={acknowledgement["program"]}')
            self.event(message)
            stop_message = await self.best_effort_stop()
            raise ControlError(f'{message}. {stop_message} No new configuration is claimed active.')
        if acknowledgement['phase'] != expected_phase:
            message = (f'START phase acknowledgement mismatch: expected={expected_phase}, '
                       f'acknowledged={acknowledgement["phase"]}')
            self.event(message)
            stop_message = await self.best_effort_stop()
            raise ControlError(f'{message}. {stop_message} No new configuration is claimed active.')
        if acknowledgement['state'] not in ACTIVE_STATES:
            stop_message = await self.best_effort_stop()
            raise ControlError(f'START acknowledgement did not report RUNNING/HOLD. {stop_message}')
        try:
            self.run.record_experiment(source, requested, applied, acknowledgement['request_id'])
        except OSError as exc:
            stop_message = await self.best_effort_stop()
            raise ControlError(f'START was acknowledged but saving the experiment snapshot failed: {exc}. '
                               f'{stop_message} No new configuration is claimed active.') from exc
        self.control_uncertain = False
        self.last_active = self.active
        return (f'START request_id={acknowledgement["request_id"]} acknowledged; board reported '
                f'{acknowledgement["state"]}/{acknowledgement["program"]}/{acknowledgement["phase"]} '
                'with all requested settings at acknowledgement. '
                f'Recording {self.run.path}. NC fails ON on Arduino power/reset loss; '
                'serial status is not physical proof.')

    async def next_experiment(self):
        controller = self.controller
        if not self.controller_available or controller is None:
            raise ControlError('NEXT requires fresh controller telemetry; no command sent.')
        program = controller['program']
        label = str(program).upper()
        if program == 'exp6':
            # EXP6 takes NEXT anywhere in the 100 C stage, at any temperature.
            if not self.active or controller['phase'] not in {'HEAT_100', 'HOLD_100'}:
                raise ControlError('NEXT requires an active EXP6 HEAT_100/HOLD_100 report; no command sent.')
        else:
            if (not self.active or program not in STAGED_PROGRAMS
                    or controller['phase'] != 'HOLD_100'):
                raise ControlError('NEXT requires an active EXP4/EXP5 HOLD_100 report; no command sent.')
            if self.last_sample is None or time.monotonic() - self.last_sample > SAMPLE_FRESH_S:
                raise ControlError('NEXT requires a fresh heater sample within the 100 C hold band; no command sent.')
            settings = controller['settings']
            heater = self.values[1 if settings['swap_inputs'] else 0]
            if heater is None or abs(heater - 100.0) > settings['hold_band_C']:
                raise ControlError('NEXT requires current heater temperature within 100 C +/- hold_band_C; no command sent.')
        self.control_uncertain = True
        try:
            acknowledgement = await self.request('NEXT', program=program)
        except (ControlError, OSError) as exc:
            stop_message = await self.best_effort_stop()
            raise ControlError(f'{exc} {stop_message} No RAMP_200 transition is confirmed; '
                               'NEXT was not retried and recording remains open.') from exc
        except asyncio.CancelledError:
            await self.best_effort_stop()
            raise
        if not acknowledgement['command_ok']:
            unsafe_report = not self.active and acknowledgement['heater_on']
            self.control_uncertain = unsafe_report
            message = (f'NEXT rejected by board: {acknowledgement["reason"]}; '
                       'no phase advance is claimed and the command will not be retried.')
            if unsafe_report:
                stop_message = await self.best_effort_stop()
                raise ControlError(f'{message} {stop_message}')
            raise ControlError(message)
        if (acknowledgement['program'] != program or acknowledgement['phase'] != 'RAMP_200'
                or acknowledgement['state'] not in ACTIVE_STATES):
            self.control_uncertain = True
            stop_message = await self.best_effort_stop()
            raise ControlError(f'NEXT acknowledgement did not confirm active {label} RAMP_200; '
                               f'no phase advance is claimed and NEXT will not be retried. {stop_message} '
                               'Recording remains open.')
        self.control_uncertain = False
        self.last_active = self.active
        return (f'NEXT request_id={acknowledgement["request_id"]} acknowledged; board reports '
                f'{acknowledgement["state"]}/{label}/RAMP_200. The existing recording remains active; '
                'serial status is not physical proof.')

    async def stop_experiment(self):
        if not self.active and not self.control_uncertain:
            if self.last_active and self.port is None:
                raise ControlError('Last board report was active but serial is disconnected; heater state unknown. '
                                   'Reconnect and obtain a STOP acknowledgement before finalizing.')
            return 'No active experiment reported; no STOP sent. Cooldown logging remains unchanged.'
        if self.port is None:
            raise ControlError('Experiment outcome is unresolved and serial is disconnected; heater state unknown. '
                               'Reconnect and obtain a STOP acknowledgement before finalizing.')
        acknowledgement = await self.request('STOP')
        if not acknowledgement['command_ok']:
            raise ControlError(f'STOP rejected by board: {acknowledgement["reason"]}; heater state unknown; recording remains open.')
        if acknowledgement['state'] in ACTIVE_STATES or acknowledgement['heater_on']:
            raise ControlError('STOP acknowledgement still reports active/heater_on=true; recording remains open.')
        self.last_active = False
        self.control_uncertain = False
        return (f'STOP request_id={acknowledgement["request_id"]} acknowledged; board reports '
                f'{acknowledgement["state"]}/heater_on=false. Cooldown logging continues in {self.run.path if self.run else "no active run"}. '
                'This is not physical proof that the relay opened.')

    async def stop_recording(self):
        if self.active or self.last_active or self.control_uncertain:
            await self.stop_experiment()
        return self.stop('Stopped by command')

    async def heartbeat_loop(self):
        while True:
            try:
                receiving = (self.controller_available and self.last_sample is not None
                             and time.monotonic() - self.last_sample <= SAMPLE_FRESH_S)
                # Do not keep an unobservable or unresolved experiment alive.
                # Stopping PING lets the board's own timeout latch heat OFF.
                if receiving and (self.pending or (self.active and not self.control_uncertain)):
                    try:
                        await self.write_line('EXP2 PING\n')
                        self.heartbeat_error_reported = False
                    except ControlError as exc:
                        if not self.heartbeat_error_reported:
                            self.event(f'Heartbeat failed; board timeout must latch its own fault: {exc}')
                            self.heartbeat_error_reported = True
                await asyncio.sleep(HEARTBEAT_PERIOD_S)
            except asyncio.CancelledError:
                raise

    async def shutdown(self):
        async with self.command_lock:
            if self.port is not None and (self.active or self.pending or self.last_active or self.control_uncertain):
                await self.best_effort_stop()
        if self.heartbeat:
            self.heartbeat.cancel()
            try:
                await self.heartbeat
            except asyncio.CancelledError:
                pass
            self.heartbeat = None
        await self.disconnect()
        self.stop('Application shutdown')

    async def disconnect(self):
        if self.reader:
            self.reader.cancel()
            try:
                await self.reader
            except asyncio.CancelledError:
                pass
            self.reader = None
        async with self.write_lock:
            if self.port:
                # A pending blocking read has a short timeout; close only after it completes.
                await asyncio.to_thread(self.port.close)
                self.port = None
        if self.buffer:
            self.event(f'Incomplete serial row at close discarded: {self.buffer[:160]!r}')
        self.buffer = b''
        self.device = 'disconnected'
        self.controller_disconnected()

    async def connect(self):
        await self.disconnect()
        cfg = self.config['serial']
        name = cfg['port']
        if not name:
            matches = [p for p in list_ports.comports()
                       if p.vid == cfg['vid'] and p.pid == cfg['pid']
                       and p.serial_number == cfg['serial_number']]
            if len(matches) != 1:
                self.event(f'Connection unavailable: expected exactly one matching Mega ADK, found {len(matches)}. Use reconnect after checking USB/config.')
                return
            name = matches[0].device
        try:
            self.port = await asyncio.to_thread(serial.Serial, name, cfg['baud'], timeout=0.3,
                                                write_timeout=WRITE_TIMEOUT_S, exclusive=True)
        except (serial.SerialException, OSError) as exc:
            self.event(f'Connection failed: {exc}')
            return
        self.device = f'{name} @ {cfg["baud"]} baud'
        self.last_board = None
        self.last_sample = None
        self.epoch += 1
        self.buffer = b''
        self.event(f'Opened {self.device}; opening may reset board uptime. Sensor attachment/validity unverified.')
        if not self.auto_started:
            self.start()
            self.auto_started = True
        self.reader = asyncio.create_task(self.read_serial())

    async def read_serial(self):
        try:
            while True:
                # Shield/join prevents reconnect from closing a port with a worker still reading.
                pending = asyncio.create_task(asyncio.to_thread(self.port.read, 512))
                closing = False
                try:
                    chunk = await asyncio.shield(pending)
                except asyncio.CancelledError:
                    chunk = await pending
                    closing = True
                self.buffer += chunk
                while b'\n' in self.buffer:
                    line, self.buffer = self.buffer.split(b'\n', 1)
                    self.consume(line)
                if len(self.buffer) > 4096:
                    self.bad_rows += 1
                    self.event(f'Oversized partial serial row discarded: {self.buffer[:100]!r}')
                    self.buffer = b''
                if closing:
                    raise asyncio.CancelledError
        except (serial.SerialException, OSError) as exc:
            self.event(f'Serial disconnected/error: {exc}; recording remains open, reconnect explicitly.')
            if self.buffer:
                self.event(f'Incomplete serial row at disconnect discarded: {self.buffer[:160]!r}')
                self.buffer = b''
            async with self.write_lock:
                if self.port:
                    self.port.close()
                    self.port = None
            self.device = 'disconnected'
            self.controller_disconnected()
        except Exception as exc:
            self.event(f'Acquisition stopped by error: {exc}')
            if not self.last_active and not self.control_uncertain:
                self.stop(f'Acquisition error: {exc}')
            async with self.write_lock:
                if self.port:
                    self.port.close()
                    self.port = None
            self.device = 'disconnected'
            self.controller_disconnected()

    def consume(self, raw):
        if not raw.strip():
            return
        if raw.startswith(b'#CTRL'):
            self.consume_telemetry(raw)
            return
        if raw.strip() == b'time_s,t1_C,t2_C':
            if self.last_board is not None:
                self.epoch += 1
            self.board_reset('CSV header received (startup/reset); controller freshness and pending commands cleared; no automatic START.')
            return
        try:
            text = raw.decode('ascii').strip()
            parts = text.split(',')
            if len(parts) != 3:
                raise ValueError('expected three CSV columns')
            board, a, b = map(float, parts)
            if not math.isfinite(board) or board < 0 or any(math.isinf(v) for v in (a, b)):
                raise ValueError('invalid numeric value')
        except (ValueError, UnicodeError) as exc:
            self.bad_rows += 1
            self.event(f'Malformed serial row ({exc}): {raw[:160]!r}')
            return
        flags = []
        if self.last_board is not None and board < self.last_board:
            previous_board = self.last_board
            self.epoch += 1
            flags.append('board_time_regression')
            self.board_reset(f'Board time regressed {previous_board} → {board}; new epoch {self.epoch}; '
                             'controller freshness and pending commands cleared; no automatic START.')
        self.last_board = board
        self.last_sample = time.monotonic()
        values = [None if math.isnan(v) else v for v in (a, b)]
        previous = self.values
        self.values = values
        for i, v in enumerate(values):
            if v is None:
                flags.append(f'TC{i+1}_fault')
                if previous[i] is not None:
                    self.event(f'TC{i+1}: nan fault; plotted as gap.')
        self.zero_count = self.zero_count + 1 if values == [0.0, 0.0] else 0
        if self.zero_count:
            flags.append('all_zero_unverified')
            if self.zero_count == 3:
                self.event('Repeated all-zero stream: NOT proof of valid temperatures; check probes, wiring and amplifier status.')
        if self.run:
            point = self.run.append(board, self.epoch, values, flags)
            self.sequence += 1
            self.points.append([self.sequence, *point])

    def status(self):
        age = None if self.last_sample is None else round(time.monotonic() - self.last_sample, 1)
        controller_age = (None if self.controller_received is None
                          else round(time.monotonic() - self.controller_received, 3))
        available = self.controller_available
        link = 'disconnected' if self.port is None else ('fresh' if available else 'stale')
        if self.controller is None:
            controller = {'protocol': None, 'state': None, 'reason': 'No validated controller telemetry',
                          'heater_on': None, 'settings': None, 'tc2_required': False,
                          'relay_contact': None, 'active_high': None, 'hold_s': None,
                          'request_id': 0, 'command_ok': False, 'program': None, 'phase': None,
                          'setpoint_C': None, 'slope_C_per_s': None}
        else:
            controller = dict(self.controller)
        if not available:
            controller['heater_on'] = None
        controller.update(age=controller_age, available=available,
                          pending=self.pending is not None, active=self.active, link=link,
                          uncertain=self.control_uncertain)
        display = self.display_metadata()
        return {'device': self.device, 'connected': self.port is not None,
                'recording': self.run is not None, 'run': self.last_run.name if self.last_run else None,
                'path': str(self.last_run) if self.last_run else None,
                'rows': self.run.rows if self.run else None, 'age': age, 'values': self.values,
                'zero_count': self.zero_count, 'bad_rows': self.bad_rows, 'epoch': self.epoch,
                'sequence': self.sequence, 'plot_points': self.config['plot_points'],
                'display_swapped': display['swap_inputs'], 'experiment': display['experiment'],
                'variac_voltage_V': display['variac_voltage_V'],
                'controller': controller, 'events': list(self.events)}

    def history(self, name):
        if not name.isascii() or not name.isdecimal():
            raise ValueError('Use a run number from list, e.g. view 001')
        path = self.root / name / 'data.csv'
        points = deque(maxlen=self.config['plot_points'])
        with path.open(newline='') as f:
            for i, row in enumerate(csv.DictReader(f)):
                values = [float(row[k]) for k in ('tc1_C', 'tc2_C')]
                points.append([i + 1, float(row['host_elapsed_s']),
                               *(v if math.isfinite(v) else None for v in values)])
        return list(points)

    async def command(self, text):
        async with self.command_lock:
            return await self.execute_command(text)

    async def execute_command(self, text):
        parts = shlex.split(text)
        if not parts:
            raise ValueError('Enter a command; help lists commands.')
        cmd, *args = parts
        no_args = {'help', 'status', 'start', 'stop', 'next', 'restart', 'save', 'clear', 'list', 'live', 'config', 'channels', 'reconnect'}
        if cmd in no_args and args and not (cmd in {'start', 'stop'} and len(args) == 1
                                             and args[0] in EXPERIMENT_PROFILES):
            raise ValueError(f'{cmd} takes no arguments (except exactly: {cmd} exp2, {cmd} exp3, {cmd} exp4, {cmd} exp5 or {cmd} exp6)'
                             if cmd in {'start', 'stop'} else f'{cmd} takes no arguments')
        result = {}
        if cmd == 'help':
            message = HELP
        elif cmd == 'status':
            message = json.dumps(self.status(), indent=2)
        elif cmd in ('config', 'channels'):
            profiles = {}
            for profile in EXPERIMENT_PROFILES:
                _, source_text, experiment, metadata = self.load_experiment(profile)
                profiles[profile] = {
                    'config_path': str(self.experiment_paths[profile]),
                    'source': source_text,
                    'edited_settings': experiment,
                    'variac_voltage_V': metadata['variac_voltage_V'],
                }
            applied = self.controller['settings'] if self.controller else None
            message = json.dumps({
                'hub_config_path': str(self.config_path),
                'hub_settings': self.config,
                'hub_changes_apply': 'after server restart',
                'experiments': profiles,
                'experiment_changes_apply': 'on next start exp2, start exp3, start exp4, start exp5 or start exp6; active settings do not change',
                'applied_controller_settings': applied,
                'raw_csv_channels': 'tc1_C/tc2_C always remain physical input channels 1/2',
                'variac_voltage_V': 'host-only manual preset metadata; never measured, set, or used to rescale data',
            }, indent=2)
        elif cmd == 'start' and len(args) == 1 and args[0] in EXPERIMENT_PROFILES:
            message = await self.start_experiment(args[0])
            result['effect'] = 'live'
        elif cmd == 'stop' and len(args) == 1 and args[0] in EXPERIMENT_PROFILES:
            message = await self.stop_experiment()
        elif cmd == 'next':
            message = await self.next_experiment()
        elif cmd == 'start':
            if self.active or self.last_active or self.control_uncertain:
                raise ControlError('Refusing to replace recording while an experiment is active or unconfirmed; use stop exp2, stop exp3, stop exp4, stop exp5 or stop exp6 first.')
            message = self.start()
            result['effect'] = 'live'
        elif cmd == 'stop':
            message = await self.stop_recording()
        elif cmd == 'restart':
            if self.active or self.last_active or self.control_uncertain or self.pending:
                raise ControlError('Refusing restart while an experiment is active or unconfirmed; obtain a STOP acknowledgement first.')
            message = self.stop('Restarted by command') + '\n' + self.start()
            result['effect'] = 'live'
        elif cmd == 'save':
            if not self.run:
                message = f'No active recording. Last saved: {self.last_run or "none"}'
            else:
                self.run.flush()
                self.run.metadata('recording')
                message = f'Flushed {self.run.rows} samples: {self.run.path} (still recording)'
        elif cmd == 'note':
            if not args or not self.run:
                raise ValueError('Usage: note your comment (requires an active run)')
            self.run.note(' '.join(args))
            message = f'Comment appended to run {self.run.path.name}; active run, not historical view.'
        elif cmd == 'list':
            runs = sorted((p for p in self.root.glob('*') if p.is_dir() and p.name.isdecimal()), key=lambda p: int(p.name), reverse=True)
            message = '\n'.join(f'{p.name}  {"RECORDING" if self.run and p == self.run.path else "saved"}  {p / "data.csv"}' for p in runs) or 'No saved runs.'
        elif cmd == 'view':
            if len(args) != 1:
                raise ValueError('Usage: view 001')
            history_points = self.history(args[0])  # Validate run identifier before metadata access.
            display = self.display_metadata(self.root / args[0])
            result.update(effect='history', name=args[0], points=history_points,
                          display_swapped=display['swap_inputs'], experiment=display['experiment'],
                          variac_voltage_V=display['variac_voltage_V'])
            message = f'HISTORICAL run {args[0]} — saved snapshot, last {self.config["plot_points"]} points maximum. Active logging is unchanged.'
        elif cmd in ('clear', 'live'):
            result['effect'] = cmd
            message = 'View cleared only; disk and recording unchanged.' if cmd == 'clear' else 'Current stream restored.'
        elif cmd == 'window':
            if len(args) != 1:
                raise ValueError('Usage: window 120 | window all')
            seconds = None if args[0] == 'all' else float(args[0])
            if seconds is not None and (not math.isfinite(seconds) or seconds <= 0):
                raise ValueError('Window must be positive seconds or all')
            result.update(effect='window', seconds=seconds)
            message = f'Plot window: {args[0]} (retained points only).'
        elif cmd == 'reconnect':
            if self.active or self.pending or (self.control_uncertain and self.port is not None):
                raise ControlError('Refusing reconnect while an experiment is active or a command is unresolved; use stop exp2, stop exp3, stop exp4, stop exp5 or stop exp6 and await its acknowledgement.')
            await self.connect()
            message = f'Connection: {self.device}. Opening serial may reset the board; no automatic START is sent.'
        else:
            raise ValueError(f'Unknown command: {cmd}. Type help.')
        return dict(result, message=message)


async def serve(config_path, runs_override=None, port_override=None, wait_for_start=False):
    config = tomllib.loads(config_path.read_text())
    if config['plot_points'] < 2 or config['serial']['baud'] <= 0:
        raise ValueError('plot_points must be >=2 and serial baud positive')
    root = Path(runs_override) if runs_override else config_path.parent / config['runs_dir']
    hub = Hub(config, root.resolve(), config_path)
    # Suppress only automatic recording allocation, not acquisition or explicit START.
    hub.auto_started = wait_for_start
    webroot = Path(__file__).parent / 'web'
    app = web.Application(client_max_size=16384)

    async def index(request):
        return web.FileResponse(webroot / 'index.html')

    async def state(request):
        try:
            since = int(request.query.get('since', '0'))
        except ValueError:
            raise web.HTTPBadRequest(text='since must be an integer')
        return web.json_response(dict(status=hub.status(), points=[p for p in hub.points if p[0] > since]))

    async def command(request):
        # No CORS, no cross-origin commands, no shell execution.
        origin = request.headers.get('Origin')
        if origin and origin != f'{request.scheme}://{request.host}':
            raise web.HTTPForbidden(text='Cross-origin commands are not allowed')
        try:
            body = await request.json()
            if not isinstance(body, dict) or not isinstance(body.get('command'), str):
                raise ValueError('Expected a command string')
            return web.json_response(await hub.command(body['command']))
        except (ValueError, OSError, csv.Error) as exc:
            return web.json_response({'message': str(exc), 'error': True}, status=400)

    async def startup(app):
        hub.heartbeat = asyncio.create_task(hub.heartbeat_loop())
        await hub.connect()

    async def cleanup(app):
        await hub.shutdown()

    app.router.add_get('/', index)
    app.router.add_get('/api/state', state)
    app.router.add_post('/api/command', command)
    app.router.add_get('/plotly.js', lambda request: web.FileResponse(Path(plotly.__file__).parent / 'package_data' / 'plotly.min.js'))
    app.router.add_static('/static/', webroot)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    return app, port_override or config['port']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parent.parent / 'hub.toml')
    parser.add_argument('--runs-dir', help='Override storage, e.g. isolated /tmp smoke evidence')
    parser.add_argument('--port', type=int, help='Override localhost HTTP port')
    parser.add_argument('--wait-for-start', action='store_true',
                        help='Connect and show live sensor status without allocating a run until explicit START')
    args = parser.parse_args()
    async def make_app():
        app, _ = await serve(args.config.resolve(), args.runs_dir, args.port, args.wait_for_start)
        return app
    config = tomllib.loads(args.config.read_text())
    web.run_app(make_app(), host='127.0.0.1', port=args.port or config['port'])


if __name__ == '__main__':
    main()
