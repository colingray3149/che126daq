"""Consumer-visible acquisition boundaries and staged experiment control behavior."""
import asyncio
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('che126_hub', Path(__file__).parents[1] / 'host' / 'hub.py')
hub_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hub_module)


def experiment_settings(**updates):
    settings = {
        'target_C': 300.0,
        'hysteresis_C': 3.0,
        'feedback_cutoff_C': 320.0,
        'rear_cutoff_C': 140.0,
        'rear_cutoff_enabled': True,
        'prediction_lead_s': 5.0,
        'min_off_s': 5.0,
        'hold_band_C': 5.0,
        'hold_s': 1800.0,
        'feedback_channel': 3,
        'rear_channel': 1,
    }
    settings.update(updates)
    return settings


def exp4_settings(**updates):
    settings = experiment_settings(target_C=700.0, feedback_cutoff_C=730.0, rear_cutoff_C=85.0,
                                   hold_s=0.0, feedback_channel=2, rear_channel=1)
    settings.update(updates)
    return settings


def exp5_settings(**updates):
    settings = experiment_settings(target_C=700.0, feedback_cutoff_C=730.0, rear_cutoff_C=120.0,
                                   hold_s=60.0, feedback_channel=2, rear_channel=1)
    settings.update(updates)
    return settings


def exp7_settings(**updates):
    settings = exp5_settings(target_C=650.0, hold_s=90.0, feedback_channel=3, rear_channel=1,
                             external_channel=2, preheat_target_C=100.0,
                             ramp_target_C=200.0, ramp_s=90.0)
    settings.update(updates)
    return settings


def exp8_settings(**updates):
    settings = exp7_settings(feedback_channel=2, rear_channel=1, external_channel=2)
    settings.update(updates)
    return settings


def experiment_text(settings, variac_voltage_V=30.0):
    def value(key):
        item = settings[key]
        return str(item).lower() if isinstance(item, bool) else repr(item)
    keys = (*hub_module.EXPERIMENT_KEYS, *hub_module.EXP7_KEYS) if 'external_channel' in settings else hub_module.EXPERIMENT_KEYS
    lines = [f'{key} = {value(key)}' for key in keys]
    lines.append(f'variac_voltage_V = {variac_voltage_V!r}')
    return '\n'.join(lines) + '\n'


def controller_telemetry(request_id, settings, state='RUNNING', command_ok=True, heater_on=False,
                         program='single', phase=None, setpoint_C=None, slope_C_per_s=0.0):
    if phase is None:
        phase = 'HEAT_100' if program in hub_module.STAGED_PROGRAMS else 'SINGLE'
    if setpoint_C is None:
        setpoint_C = {'HEAT_100': 100.0, 'HOLD_100': 100.0, 'RAMP_200': 100.0,
                      'BOOST_FINAL': 200.0, 'HOLD_FINAL': settings['target_C']}.get(
                          phase, settings['target_C'])
    report = {
        'protocol': 'exp2-v6',
        'state': state,
        'reason': state,
        'heater_on': heater_on,
        'program': program,
        'phase': phase,
        'setpoint_C': setpoint_C,
        'slope_C_per_s': slope_C_per_s,
        'rear_required': program in hub_module.STAGED_PROGRAMS,
        'relay_contact': 'NC',
        'active_high': True,
        'hold_s': 0,
        'request_id': request_id,
        'command_ok': command_ok,
        'settings': settings,
    }
    if program in hub_module.EXTENDED_PROGRAMS:
        report['phase_feedback_channel'] = (2 if program == 'exp8' else settings['external_channel']
                                          if phase in {'HEAT_100', 'HOLD_100', 'RAMP_200'}
                                          else settings['feedback_channel'])
    return report


class FakePort:
    """Captures serial commands and supplies independently configured board reports."""
    def __init__(self, hub):
        self.hub = hub
        self.loop = asyncio.get_running_loop()
        self.writes = []
        self.acknowledgements = []

    def queue(self, settings, state='RUNNING', command_ok=True, heater_on=False,
              program='single', phase=None, setpoint_C=None, verb=None):
        self.acknowledgements.append((verb, {
            'settings': settings, 'state': state, 'command_ok': command_ok,
            'heater_on': heater_on, 'program': program, 'phase': phase,
            'setpoint_C': setpoint_C,
        }))

    def write(self, data):
        self.writes.append(data)
        parts = data.decode('ascii').strip().split()
        controlled = (len(parts) >= 3 and
                      ((parts[0] == 'EXP2' and parts[1] in {'START', 'STOP'})
                       or (parts[0] in {'EXP4', 'EXP5', 'EXP6', 'EXP7', 'EXP8'}
                           and parts[1] in {'START', 'NEXT'})))
        if controlled:
            for i, (verb, details) in enumerate(self.acknowledgements):
                if verb is None or verb == parts[1]:
                    self.acknowledgements.pop(i)
                    report = controller_telemetry(int(parts[2]), **details)
                    raw = ('#CTRL ' + json.dumps(report)).encode('ascii')
                    self.loop.call_soon_threadsafe(self.hub.consume, raw)
                    break
        return len(data)


class AcquisitionBoundaries(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        config_path = Path(self.storage.name) / 'hub.toml'
        self.hub = hub_module.Hub({'plot_points': 10}, Path(self.storage.name) / 'runs', config_path)
        self.hub.start()

    def tearDown(self):
        self.hub.stop('Test complete')
        self.storage.cleanup()

    def test_reset_header_separates_saved_epochs_without_double_counting(self):
        self.hub.consume(b'10.0,25,26,27')
        self.hub.consume(b'time_s,t1_C,t2_C,t3_C')
        self.hub.consume(b'0.5,28,29,30')
        self.hub.consume(b'1.0,31,32,33')
        with (self.hub.run.path / 'data.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertNotEqual(rows[0]['epoch'], rows[1]['epoch'])
        self.assertEqual(rows[1]['epoch'], rows[2]['epoch'])
        self.assertEqual(float(rows[1]['board_time_s']), .5)
        self.assertEqual([float(rows[-1][key]) for key in ('tc1_C', 'tc2_C', 'tc3_C')], [31, 32, 33])

    def test_malformed_controller_state_does_not_destroy_acquisition(self):
        self.hub.consume(b'1.0,25,26,27')
        telemetry = controller_telemetry(1, experiment_settings())
        telemetry['state'] = []
        self.hub.consume(('#CTRL ' + json.dumps(telemetry)).encode())
        self.hub.consume(b'1.5,28,29,30')
        self.assertEqual(self.hub.bad_rows, 1)
        self.assertFalse(self.hub.controller_available)
        with (self.hub.run.path / 'data.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([tuple(float(r[key]) for key in ('tc1_C', 'tc2_C', 'tc3_C')) for r in rows],
                         [(25, 26, 27), (28, 29, 30)])

    def test_legacy_two_channel_live_protocol_is_rejected(self):
        self.hub.consume(b'time_s,t1_C,t2_C')
        self.hub.consume(b'1.0,25,26')
        self.assertEqual(self.hub.bad_rows, 2)
        self.assertEqual(self.hub.values, [None, None, None])
        self.assertEqual(self.hub.run.rows, 0)

    def test_tc3_raw_value_and_fault_persist_without_substitution(self):
        self.hub.stop('Switching to legacy mapping')
        self.hub.start({'experiment': 'exp2', 'feedback_channel': 3, 'rear_channel': 1,
                        'variac_voltage_V': 30.0})
        self.hub.consume(b'1.0,25,26,300')
        self.hub.consume(b'1.5,27,28,nan')
        with (self.hub.run.path / 'data.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['tc3_C'], '300.0')
        self.assertEqual((rows[1]['tc1_C'], rows[1]['tc2_C'], rows[1]['tc3_C']),
                         ('27.0', '28.0', 'nan'))
        self.assertIn('TC3_fault', rows[1]['flags'])
        self.assertEqual(self.hub.values, [27.0, 28.0, None])
        self.assertEqual(list(self.hub.points)[-1], [2, mock.ANY, 27.0, 28.0, None])
        self.assertIsNone(self.hub.status()['values'][2])

    def test_exp8_unplugged_tc3_is_unused_without_hiding_tc1_tc2_faults(self):
        self.hub.consume(b'1.0,25,nan,nan')
        with (self.hub.run.path / 'data.csv').open() as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row['tc3_C'], 'nan')
        self.assertIn('TC3_unused', row['flags'])
        self.assertIn('TC2_fault', row['flags'])
        self.assertNotIn('TC3_fault', row['flags'])
        self.assertNotIn('TC1_fault', row['flags'])
        self.assertEqual(self.hub.values, [25.0, None, None])

    def test_v6_envelope_channels_and_rear_requirement_are_strict(self):
        valid = controller_telemetry(1, exp7_settings(), program='exp7', phase='HOLD_100')
        invalid = []
        for key, value in (
                ('protocol', 'exp2-v5'), ('program', 'exp3'), ('phase', 'SINGLE'),
                ('setpoint_C', float('nan')), ('slope_C_per_s', float('inf')),
                ('rear_required', False)):
            report = dict(valid)
            report[key] = value
            invalid.append(report)
        single = controller_telemetry(2, experiment_settings())
        single['rear_required'] = True
        invalid.append(single)
        for channels in ({'feedback_channel': 0}, {'feedback_channel': 4},
                         {'feedback_channel': True}, {'feedback_channel': 3.0},
                         {'rear_channel': 0}, {'rear_channel': 4},
                         {'feedback_channel': 1, 'rear_channel': 1}):
            invalid.append(dict(valid, settings=exp7_settings(**channels)))
        invalid.append(dict(valid, settings=exp7_settings(feedback_cutoff_C=731.0)))
        for report in invalid:
            with self.subTest(settings=report['settings'], protocol=report['protocol'],
                              rear_required=report['rear_required']):
                before = self.hub.bad_rows
                self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
                self.assertEqual(self.hub.bad_rows, before + 1)
                self.assertIsNone(self.hub.controller_received)
        self.hub.consume(('#CTRL ' + json.dumps(valid)).encode())
        self.assertEqual(self.hub.controller['program'], 'exp7')
        self.assertEqual(self.hub.controller['settings']['feedback_channel'], 3)
        self.assertTrue(self.hub.controller['rear_required'])

    def test_exp7_phase_feedback_switches_from_external_to_internal(self):
        for phase, channel in (('HEAT_100', 2), ('HOLD_100', 2), ('RAMP_200', 2),
                               ('BOOST_FINAL', 3), ('HOLD_FINAL', 3)):
            with self.subTest(phase=phase):
                report = controller_telemetry(1, exp7_settings(), program='exp7', phase=phase)
                self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
                self.assertEqual(self.hub.controller['phase_feedback_channel'], channel)
                self.assertEqual(self.hub.controller['settings']['external_channel'], 2)
        report = controller_telemetry(1, exp7_settings(), program='exp7', phase='BOOST_FINAL')
        report['phase_feedback_channel'] = 2
        before = self.hub.bad_rows
        self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
        self.assertEqual(self.hub.bad_rows, before + 1)
        self.assertIsNone(self.hub.controller_received)

    def test_exp8_phase_feedback_stays_on_aliased_tc2(self):
        for phase in ('HEAT_100', 'HOLD_100', 'RAMP_200', 'BOOST_FINAL', 'HOLD_FINAL'):
            with self.subTest(phase=phase):
                report = controller_telemetry(1, exp8_settings(), program='exp8', phase=phase)
                self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
                self.assertEqual(self.hub.controller['phase_feedback_channel'], 2)
                self.assertEqual(self.hub.controller['settings']['feedback_channel'], 2)
                self.assertEqual(self.hub.controller['settings']['external_channel'], 2)
        report['phase_feedback_channel'] = 3
        before = self.hub.bad_rows
        self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
        self.assertEqual(self.hub.bad_rows, before + 1)
        self.assertIsNone(self.hub.controller_received)


class ExperimentConfiguration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = tempfile.TemporaryDirectory()
        base = Path(self.storage.name)
        self.config_path = base / 'operator-config' / 'hub.toml'
        self.config_path.parent.mkdir()
        self.config_path.write_text('plot_points = 10\n')
        profile_settings = {
            'exp2': (experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2), 30.0),
            'exp3': (experiment_settings(rear_cutoff_C=85.0, feedback_channel=2, rear_channel=1), 65.0),
            'exp4': (exp4_settings(), 100.0),
            'exp5': (exp5_settings(), 100.0),
            'exp6': (exp5_settings(), 100.0),
            'exp7': (exp7_settings(), 100.0),
            'exp8': (exp8_settings(), 100.0),
        }
        self.profile_paths = {}
        for profile, (settings, voltage) in profile_settings.items():
            path = self.config_path.parent / hub_module.EXPERIMENT_PROFILES[profile]['filename']
            path.write_text(experiment_text(settings, variac_voltage_V=voltage))
            self.profile_paths[profile] = path
        self.hub = hub_module.Hub({'plot_points': 10}, base / 'runs', self.config_path)
        self.port = FakePort(self.hub)
        self.hub.port = self.port
        self.hub.device = 'fake serial'

    async def asyncTearDown(self):
        self.hub.stop('Test complete')
        self.storage.cleanup()

    async def start_exp4(self, settings=None):
        requested = settings or exp4_settings()
        self.profile_paths['exp4'].write_text(experiment_text(requested, variac_voltage_V=100.0))
        self.port.queue(requested, program='exp4', phase='HEAT_100')
        result = await self.hub.execute_command('start exp4')
        self.assertEqual(result['effect'], 'live')
        return requested

    def enter_exp4_hold(self, tc1=25.0, tc2=100.0, tc3=40.0):
        settings = self.hub.controller['settings']
        report = controller_telemetry(self.hub.request_id, settings, state='HOLD',
                                      program='exp4', phase='HOLD_100')
        self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
        self.hub.consume(f'1.0,{tc1},{tc2},{tc3}'.encode())

    async def start_exp7(self, settings=None):
        requested = settings or exp7_settings()
        self.profile_paths['exp7'].write_text(experiment_text(requested, variac_voltage_V=100.0))
        self.port.queue(requested, program='exp7', phase='HEAT_100')
        result = await self.hub.execute_command('start exp7')
        self.assertEqual(result['effect'], 'live')
        return requested

    async def start_exp8(self, settings=None):
        requested = settings or exp8_settings()
        self.profile_paths['exp8'].write_text(experiment_text(requested, variac_voltage_V=100.0))
        self.port.queue(requested, program='exp8', phase='HEAT_100')
        result = await self.hub.execute_command('start exp8')
        self.assertEqual(result['effect'], 'live')
        return requested

    async def test_invalid_edit_leaves_current_run_and_serial_untouched(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        events_before = (current.path / 'events.csv').read_bytes()
        notes_before = (current.path / 'notes.md').read_bytes()
        writes_before = list(self.port.writes)
        for source in ('target_C = [\n',
                       experiment_text(experiment_settings(target_C=float('nan'))),
                       experiment_text(experiment_settings(target_C=10**400))):
            with self.subTest(source=source):
                self.profile_paths['exp2'].write_text(source)
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp2')
        self.assertIs(self.hub.run, current)
        self.assertFalse(current.data.closed)
        self.assertFalse(current.events.closed)
        self.assertEqual((current.path / 'events.csv').read_bytes(), events_before)
        self.assertEqual((current.path / 'notes.md').read_bytes(), notes_before)
        self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_invalid_channel_mapping_atomically_rejects_start(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        invalid = (
            {'feedback_channel': 0}, {'feedback_channel': 4}, {'feedback_channel': True},
            {'feedback_channel': 3.0}, {'rear_channel': 0}, {'rear_channel': 4},
            {'rear_channel': False}, {'rear_channel': 1.0},
            {'external_channel': 0}, {'external_channel': 4}, {'external_channel': True},
            {'external_channel': 2.0}, {'external_channel': 1}, {'external_channel': 3},
            {'feedback_channel': 1, 'rear_channel': 1},
        )
        for channels in invalid:
            with self.subTest(channels=channels):
                settings = exp7_settings(**channels)
                self.profile_paths['exp7'].write_text(experiment_text(settings, variac_voltage_V=100.0))
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp7')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)
        legacy = experiment_text(exp7_settings(), variac_voltage_V=100.0)
        legacy = legacy.replace('feedback_channel = 3\nrear_channel = 1', 'swap_inputs = false')
        self.profile_paths['exp7'].write_text(legacy)
        with self.assertRaises(ValueError):
            await self.hub.start_experiment('exp7')
        self.assertIs(self.hub.run, current)
        self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_exp8_requires_tc2_alias_and_tc1_rear_atomically(self):
        current = self.hub.run
        writes_before = list(self.port.writes)
        for channels in ({'feedback_channel': 3}, {'external_channel': 3}, {'rear_channel': 2}):
            with self.subTest(channels=channels):
                settings = exp8_settings(**channels)
                self.profile_paths['exp8'].write_text(experiment_text(settings, variac_voltage_V=100.0))
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp8')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)
        # The same feedback/external alias remains invalid for EXP7.
        self.profile_paths['exp7'].write_text(experiment_text(
            exp7_settings(feedback_channel=2, external_channel=2), variac_voltage_V=100.0))
        with self.assertRaises(ValueError):
            await self.hub.start_experiment('exp7')
        self.assertIs(self.hub.run, current)
        self.assertEqual(self.port.writes, writes_before)

    async def test_exp7_requires_exact_extended_keys_atomically(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        complete = experiment_text(exp7_settings(), variac_voltage_V=100.0)
        sources = [('base-only EXP7', experiment_text(exp5_settings(), variac_voltage_V=100.0)),
                   ('unknown EXP7 key', complete + 'unexpected = 1\n')]
        for key in hub_module.EXP7_KEYS:
            line = next(line for line in complete.splitlines(keepends=True) if line.startswith(f'{key} = '))
            sources.append((f'missing {key}', complete.replace(line, '')))
        for label, source in sources:
            with self.subTest(label=label):
                self.profile_paths['exp7'].write_text(source)
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp7')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)
        self.profile_paths['exp4'].write_text(complete)
        with self.assertRaises(ValueError):
            await self.hub.start_experiment('exp4')
        self.assertIs(self.hub.run, current)
        self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_exp7_threshold_and_duration_envelope_is_atomic(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        invalid = (
            exp7_settings(preheat_target_C=0.0), exp7_settings(preheat_target_C=-1.0),
            exp7_settings(preheat_target_C=200.0), exp7_settings(ramp_target_C=100.0),
            exp7_settings(ramp_target_C=650.0), exp7_settings(ramp_target_C=651.0),
            exp7_settings(ramp_s=-0.001), exp7_settings(ramp_s=hub_module.MAX_DURATION_MS / 1000 + 0.001),
            exp7_settings(preheat_target_C=float('nan')), exp7_settings(ramp_s=float('inf')),
        )
        for settings in invalid:
            with self.subTest(settings={key: settings[key] for key in hub_module.EXP7_KEYS}):
                self.profile_paths['exp7'].write_text(experiment_text(settings, variac_voltage_V=100.0))
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp7')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)

    async def test_acknowledgement_mismatch_stops_without_claiming_configuration(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        mismatched = dict(requested, target_C=299)
        self.port.queue(mismatched)
        self.port.queue(mismatched, state='STOPPED')
        with self.assertRaises(hub_module.ControlError):
            await self.hub.start_experiment('exp2')
        self.assertFalse((self.hub.run.path / 'experiment-applied.json').exists())
        self.assertEqual(self.hub.controller['state'], 'STOPPED')

    async def test_exp7_acknowledgement_mismatch_stops_without_applied_snapshot(self):
        mismatched = exp7_settings(preheat_target_C=101.0)
        self.port.queue(mismatched, program='exp7', phase='HEAT_100')
        self.port.queue(mismatched, state='STOPPED', program='exp7', phase='HEAT_100')
        with self.assertRaisesRegex(hub_module.ControlError, 'preheat_target_C'):
            await self.hub.execute_command('start exp7')
        self.assertFalse((self.hub.run.path / 'experiment-applied.json').exists())
        self.assertEqual(self.hub.controller['state'], 'STOPPED')

    async def test_exp7_tc3_mapping_persists_with_raw_csv_and_history(self):
        await self.start_exp7()
        run_path = self.hub.run.path
        self.hub.consume(b'1.0,25,40,300')
        with (run_path / 'data.csv').open() as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(tuple(float(row[key]) for key in ('tc1_C', 'tc2_C', 'tc3_C')), (25, 40, 300))
        metadata = json.loads((run_path / 'run-metadata.json').read_text())
        self.assertEqual(metadata, {'experiment': 'exp7', 'feedback_channel': 3, 'rear_channel': 1,
                                    'external_channel': 2, 'variac_voltage_V': 100.0})
        self.assertNotIn('swap_inputs', metadata)
        status = self.hub.status()
        self.assertEqual((status['display_feedback_channel'], status['display_rear_channel'],
                          status['display_external_channel']), (3, 1, 2))
        self.assertEqual(status['values'], [25.0, 40.0, 300.0])
        viewed = await self.hub.execute_command(f'view {run_path.name}')
        self.assertEqual((viewed['display_feedback_channel'], viewed['display_rear_channel'],
                          viewed['display_external_channel']), (3, 1, 2))
        self.assertEqual(viewed['points'][0][-3:], [25.0, 40.0, 300.0])

    async def test_exp8_start_applies_alias_and_external_cutoff_below_manual_target(self):
        requested = await self.start_exp8(exp8_settings(feedback_cutoff_C=300.0))
        run_path = self.hub.run.path
        snapshot = json.loads((run_path / 'experiment-applied.json').read_text())
        self.assertEqual(snapshot['requested'], requested)
        self.assertEqual(snapshot['applied'], requested)
        self.assertEqual(snapshot['applied']['target_C'], 650.0)
        self.assertEqual(snapshot['applied']['feedback_cutoff_C'], 300.0)
        metadata = json.loads((run_path / 'run-metadata.json').read_text())
        self.assertEqual(metadata, {'experiment': 'exp8', 'feedback_channel': 2, 'rear_channel': 1,
                                    'external_channel': 2, 'variac_voltage_V': 100.0})
        self.hub.consume(b'1.0,25,40,300')
        with (run_path / 'data.csv').open() as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(tuple(float(row[key]) for key in ('tc1_C', 'tc2_C', 'tc3_C')), (25, 40, 300))
        status = self.hub.status()
        self.assertEqual((status['experiment'], status['display_feedback_channel'],
                          status['display_rear_channel'], status['display_external_channel']),
                         ('exp8', 2, 1, 2))
        viewed = await self.hub.execute_command(f'view {run_path.name}')
        self.assertEqual((viewed['experiment'], viewed['display_feedback_channel'],
                          viewed['display_rear_channel'], viewed['display_external_channel']),
                         ('exp8', 2, 1, 2))
        self.assertEqual(viewed['points'][0][-3:], [25.0, 40.0, 300.0])

    async def test_exp8_acknowledgement_mismatch_stops_without_applied_snapshot(self):
        mismatched = exp8_settings(ramp_target_C=201.0)
        self.port.queue(mismatched, program='exp8', phase='HEAT_100')
        self.port.queue(mismatched, state='STOPPED', program='exp8', phase='HEAT_100')
        with self.assertRaisesRegex(hub_module.ControlError, 'ramp_target_C'):
            await self.hub.execute_command('start exp8')
        self.assertFalse((self.hub.run.path / 'experiment-applied.json').exists())
        self.assertEqual(self.hub.controller['state'], 'STOPPED')

    async def test_next_uses_selected_internal_feedback_not_external_tc2(self):
        requested = exp4_settings(feedback_channel=3, rear_channel=1)
        await self.start_exp4(requested)
        self.enter_exp4_hold(tc1=25, tc2=40, tc3=100)
        self.port.queue(requested, program='exp4', phase='RAMP_200')
        result = await self.hub.execute_command('next')
        self.assertIn('RAMP_200', result['message'])
        self.assertEqual(self.hub.controller['phase'], 'RAMP_200')

    async def test_next_rejects_out_of_band_internal_feedback_despite_external_tc2(self):
        await self.start_exp4(exp4_settings(feedback_channel=3, rear_channel=1))
        self.enter_exp4_hold(tc1=25, tc2=100, tc3=110)
        writes_before = list(self.port.writes)
        with self.assertRaisesRegex(hub_module.ControlError, 'feedback temperature'):
            await self.hub.execute_command('next')
        self.assertEqual(self.port.writes, writes_before)
        self.hub.consume(b'1.1,25,100,nan')
        with self.assertRaisesRegex(hub_module.ControlError, 'feedback temperature'):
            await self.hub.execute_command('next')
        self.assertEqual(self.port.writes, writes_before)

    async def test_exp7_next_sent_from_entry_with_stale_missing_samples(self):
        requested = await self.start_exp7()
        run = self.hub.run
        self.hub.controller_received -= hub_module.TELEMETRY_FRESH_S + 1
        self.hub.values = [None, None, None]
        self.hub.last_sample = None
        for phase in ('HEAT_100', 'HOLD_100'):
            with self.subTest(phase=phase):
                report = controller_telemetry(self.hub.request_id, requested, state='HOLD',
                                              program='exp7', phase=phase)
                self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
                self.hub.controller_received -= hub_module.TELEMETRY_FRESH_S + 1
                writes_before = len(self.port.writes)
                self.port.queue(requested, program='exp7', phase='RAMP_200')
                result = await self.hub.execute_command('next')
                self.assertIn('RAMP_200', result['message'])
                self.assertEqual(len(self.port.writes), writes_before + 1)
                self.assertTrue(self.port.writes[-1].startswith(b'EXP7 NEXT '))
                self.assertIs(self.hub.run, run)
                self.assertEqual(self.hub.controller['phase'], 'RAMP_200')

    async def test_exp7_next_later_and_terminal_reports_are_acknowledged_noops(self):
        requested = await self.start_exp7()
        cases = (('RUNNING', 'RAMP_200'), ('RUNNING', 'BOOST_FINAL'), ('HOLD', 'HOLD_FINAL'),
                 ('COMPLETE', 'HOLD_FINAL'), ('STOPPED', 'HEAT_100'), ('TRIPPED', 'RAMP_200'))
        for state, phase in cases:
            with self.subTest(state=state, phase=phase):
                report = controller_telemetry(self.hub.request_id, requested, state=state,
                                              program='exp7', phase=phase)
                self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
                writes_before = len(self.port.writes)
                self.port.queue(requested, state=state, program='exp7', phase=phase)
                result = await self.hub.execute_command('next')
                self.assertIn('no-op', result['message'])
                self.assertIn(f'{state}/EXP7/{phase}', result['message'])
                self.assertEqual(len(self.port.writes), writes_before + 1)
                self.assertEqual((self.hub.controller['state'], self.hub.controller['phase']), (state, phase))
                self.assertFalse(self.hub.control_uncertain)

    async def test_exp8_second_next_starts_hold_and_later_next_is_noop(self):
        requested = await self.start_exp8()
        run = self.hub.run
        self.hub.values = [None, None, None]
        self.hub.controller_received -= hub_module.TELEMETRY_FRESH_S + 1
        writes_before = len(self.port.writes)
        self.port.queue(requested, program='exp8', phase='RAMP_200')
        first = await self.hub.execute_command('next')
        self.assertIn('RAMP_200', first['message'])
        self.assertEqual(len(self.port.writes), writes_before + 1)

        boost = controller_telemetry(self.hub.request_id, requested, program='exp8', phase='BOOST_FINAL')
        self.hub.consume(('#CTRL ' + json.dumps(boost)).encode())
        self.hub.controller_received -= hub_module.TELEMETRY_FRESH_S + 1
        self.port.queue(requested, state='HOLD', program='exp8', phase='HOLD_FINAL')
        second = await self.hub.execute_command('next')
        self.assertIn('HOLD_FINAL; final hold timer acknowledged', second['message'])
        self.assertEqual(len(self.port.writes), writes_before + 2)
        self.assertEqual(self.hub.controller['phase'], 'HOLD_FINAL')
        self.assertIs(self.hub.run, run)

        self.port.queue(requested, state='HOLD', program='exp8', phase='HOLD_FINAL')
        repeated = await self.hub.execute_command('next')
        self.assertIn('no-op', repeated['message'])
        self.assertIn('timers are unchanged', repeated['message'])
        self.assertEqual(len(self.port.writes), writes_before + 3)
        self.assertEqual(self.hub.controller['phase'], 'HOLD_FINAL')
        self.assertFalse(self.hub.control_uncertain)

    async def test_default_exp8_next_routes_without_telemetry_and_from_boot_idle(self):
        requested = exp8_settings()
        self.port.queue(requested, program='exp8', phase='RAMP_200')
        result = await self.hub.execute_command('next')
        self.assertIn('RAMP_200', result['message'])
        self.assertTrue(self.port.writes[-1].startswith(b'EXP8 NEXT '))
        self.assertIsNone(self.hub.run)

        idle_settings = experiment_settings()
        idle = controller_telemetry(self.hub.request_id, idle_settings, state='IDLE',
                                    program='single', phase='SINGLE')
        self.hub.consume(('#CTRL ' + json.dumps(idle)).encode())
        self.hub.controller_received -= hub_module.TELEMETRY_FRESH_S + 1
        self.port.queue(idle_settings, state='IDLE', program='single', phase='SINGLE')
        result = await self.hub.execute_command('next')
        self.assertIn('no-op', result['message'])
        self.assertIn('IDLE/SINGLE/SINGLE', result['message'])
        self.assertTrue(self.port.writes[-1].startswith(b'EXP8 NEXT '))
        self.assertIsNone(self.hub.run)
        self.assertFalse(self.hub.control_uncertain)

    async def test_barrier_is_recorded_but_not_inherited_by_plain_recording(self):
        self.profile_paths['exp7'].write_text(experiment_text(exp7_settings(), variac_voltage_V=100.0)
                                              + 'barrier = "1 mica / 2 ceramic fiber / 1 aluminum"\n')
        self.port.queue(exp7_settings(), program='exp7', phase='HEAT_100')
        await self.hub.start_experiment('exp7')
        metadata = json.loads((self.hub.run.path / 'run-metadata.json').read_text())
        self.assertEqual(metadata['barrier'], '1 mica / 2 ceramic fiber / 1 aluminum')
        self.assertIn('- Barrier: 1 mica / 2 ceramic fiber / 1 aluminum\n',
                      (self.hub.run.path / 'notes.md').read_text())
        self.hub.stop('Test')
        self.hub.start()
        inherited = json.loads((self.hub.run.path / 'run-metadata.json').read_text())
        self.assertNotIn('barrier', inherited)
        self.assertEqual((inherited['feedback_channel'], inherited['rear_channel'], inherited['external_channel']),
                         (3, 1, 2))

    async def test_invalid_exp5_envelope_preserves_run_and_serial(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        invalid_settings = (
            exp5_settings(target_C=200.0), exp5_settings(target_C=700.1),
            exp5_settings(feedback_cutoff_C=700.0), exp5_settings(feedback_cutoff_C=730.1),
            exp5_settings(rear_cutoff_C=0.0), exp5_settings(rear_cutoff_C=120.1),
            exp5_settings(rear_cutoff_enabled=False), exp5_settings(hold_s=0.0),
            exp5_settings(hysteresis_C=5.1), exp5_settings(hold_band_C=5.1),
        )
        for settings in invalid_settings:
            with self.subTest(settings=settings):
                self.profile_paths['exp5'].write_text(experiment_text(settings, variac_voltage_V=100.0))
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp5')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_invalid_exp4_envelope_preserves_run_and_serial(self):
        requested = experiment_settings(rear_cutoff_C=85.0, feedback_channel=1, rear_channel=2)
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        invalid_settings = (
            exp4_settings(target_C=200.0), exp4_settings(target_C=700.1),
            exp4_settings(feedback_cutoff_C=700.0), exp4_settings(feedback_cutoff_C=730.1),
            exp4_settings(rear_cutoff_C=0.0), exp4_settings(rear_cutoff_C=85.1),
            exp4_settings(rear_cutoff_enabled=False), exp4_settings(hold_s=0.001),
            exp4_settings(hysteresis_C=5.1), exp4_settings(hold_band_C=5.1),
        )
        for settings in invalid_settings:
            with self.subTest(settings=settings):
                self.profile_paths['exp4'].write_text(experiment_text(settings, variac_voltage_V=100.0))
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp4')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_exp4_start_program_mismatch_stops_without_applied_claim(self):
        requested = exp4_settings()
        self.port.queue(requested, program='single', phase='SINGLE')
        self.port.queue(requested, state='STOPPED', program='single', phase='SINGLE')
        with self.assertRaisesRegex(hub_module.ControlError, 'program acknowledgement mismatch'):
            await self.hub.start_experiment('exp4')
        self.assertFalse((self.hub.run.path / 'experiment-applied.json').exists())
        self.assertEqual(self.hub.controller['state'], 'STOPPED')

    async def test_next_rejection_retains_run_and_does_not_claim_or_retry(self):
        requested = await self.start_exp4()
        self.enter_exp4_hold()
        run = self.hub.run
        writes_before = len(self.port.writes)
        self.port.queue(requested, state='HOLD', command_ok=False,
                        program='exp4', phase='HOLD_100')
        with self.assertRaisesRegex(hub_module.ControlError, 'NEXT rejected'):
            await self.hub.execute_command('next')
        self.assertIs(self.hub.run, run)
        self.assertEqual(len(self.port.writes), writes_before + 1)
        self.assertEqual(self.hub.controller['phase'], 'HOLD_100')
        self.assertIsNone(self.hub.pending)
        self.assertFalse(self.hub.control_uncertain)

    async def test_next_timeout_sends_stop_retains_run_and_never_retries_next(self):
        requested = await self.start_exp4()
        self.enter_exp4_hold()
        run = self.hub.run
        writes_before = len(self.port.writes)
        self.port.queue(requested, state='STOPPED', program='exp4', phase='HOLD_100', verb='STOP')
        with mock.patch.object(hub_module, 'ACK_TIMEOUT_S', 0.01):
            with self.assertRaisesRegex(hub_module.ControlError, 'will not be retried'):
                await self.hub.execute_command('next')
            await asyncio.sleep(0.03)
        self.assertIs(self.hub.run, run)
        self.assertFalse(run.data.closed)
        self.assertEqual(len(self.port.writes), writes_before + 2)
        self.assertEqual(self.hub.controller['state'], 'STOPPED')
        self.assertIsNone(self.hub.pending)
        self.assertFalse(self.hub.control_uncertain)

    async def test_next_mismatched_acceptance_stops_without_phase_claim(self):
        requested = await self.start_exp4()
        self.enter_exp4_hold()
        run = self.hub.run
        writes_before = len(self.port.writes)
        self.port.queue(requested, state='HOLD', program='exp4', phase='HOLD_100', verb='NEXT')
        self.port.queue(requested, state='STOPPED', program='exp4', phase='HOLD_100', verb='STOP')
        with self.assertRaisesRegex(hub_module.ControlError, 'did not confirm active EXP4 RAMP_200'):
            await self.hub.execute_command('next')
        self.assertIs(self.hub.run, run)
        self.assertFalse(run.data.closed)
        self.assertEqual(len(self.port.writes), writes_before + 2)
        self.assertEqual(self.hub.controller['state'], 'STOPPED')
        self.assertFalse(self.hub.control_uncertain)

    async def test_next_requires_hold_phase_and_fresh_in_band_feedback(self):
        await self.start_exp4()
        writes_before = list(self.port.writes)
        with self.assertRaisesRegex(hub_module.ControlError, 'HOLD_100'):
            await self.hub.execute_command('next')
        self.enter_exp4_hold(tc2=110)
        with self.assertRaisesRegex(hub_module.ControlError, 'feedback temperature'):
            await self.hub.execute_command('next')
        self.assertEqual(self.port.writes, writes_before)

    async def test_legacy_run_metadata_raw_csv_and_annotation_decode(self):
        run_path = self.hub.root / '017'
        run_path.mkdir(parents=True)
        original_metadata = json.dumps({'experiment': 'exp3', 'swap_inputs': True,
                                        'variac_voltage_V': 65.0, 'barrier': 'archived barrier'})
        (run_path / 'run-metadata.json').write_text(original_metadata)
        (run_path / 'data.csv').write_text(
            'utc,host_elapsed_s,board_time_s,epoch,tc1_C,tc2_C,flags\n'
            '2026-01-01T00:00:00Z,0,1,0,25,300,\n')
        annotated_path = self.hub.root / '016'
        annotated_path.mkdir()
        (annotated_path / 'data.csv').write_text(
            'utc,host_elapsed_s,board_time_s,epoch,tc1_C,tc2_C,flags\n'
            '2025-01-01T00:00:00Z,0,1,0,20,200,\n')
        self.hub.run_mappings_path = Path(self.storage.name) / 'run-mappings.json'
        self.hub.run_mappings_path.write_text(json.dumps({
            '016': {'swap_inputs': False, 'reason': 'Archived original mapping'}
        }))
        restarted = hub_module.Hub({'plot_points': 10}, self.hub.root, self.config_path)
        restarted.run_mappings_path = self.hub.run_mappings_path
        idle = restarted.status()
        self.assertEqual((idle['experiment'], idle['display_feedback_channel'],
                          idle['display_rear_channel'], idle['display_external_channel']),
                         ('exp8', 2, 1, 2))
        viewed = await restarted.execute_command('view 017')
        self.assertEqual((viewed['display_feedback_channel'], viewed['display_rear_channel']), (2, 1))
        self.assertEqual(viewed['points'], [[1, 0.0, 25.0, 300.0, None]])
        self.assertEqual((run_path / 'run-metadata.json').read_text(), original_metadata)
        annotated = await restarted.execute_command('view 016')
        self.assertEqual((annotated['display_feedback_channel'], annotated['display_rear_channel']), (1, 2))
        self.assertEqual(annotated['points'], [[1, 0.0, 20.0, 200.0, None]])
        restarted.start()
        inherited = json.loads((restarted.run.path / 'run-metadata.json').read_text())
        self.assertEqual((inherited['experiment'], inherited['feedback_channel'],
                          inherited['rear_channel'], inherited['external_channel']),
                         ('exp8', 2, 1, 2))
        self.assertNotIn('swap_inputs', inherited)
        restarted.stop('Test complete')


if __name__ == '__main__':
    unittest.main()
