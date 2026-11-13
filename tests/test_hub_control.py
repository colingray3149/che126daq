"""Consumer-visible acquisition boundaries and Experiment 2/3/4/5 control behavior."""
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
        'tc1_cutoff_C': 320.0,
        'tc2_cutoff_C': 140.0,
        'tc2_cutoff_enabled': True,
        'prediction_lead_s': 5.0,
        'min_off_s': 5.0,
        'hold_band_C': 5.0,
        'hold_s': 1800.0,
        'swap_inputs': False,
    }
    settings.update(updates)
    return settings


def exp4_settings(**updates):
    settings = experiment_settings(target_C=700.0, tc1_cutoff_C=730.0, tc2_cutoff_C=85.0,
                                   hold_s=0.0, swap_inputs=True)
    settings.update(updates)
    return settings


def exp5_settings(**updates):
    settings = experiment_settings(target_C=700.0, tc1_cutoff_C=730.0, tc2_cutoff_C=120.0,
                                   hold_s=60.0, swap_inputs=True)
    settings.update(updates)
    return settings


def experiment_text(settings, variac_voltage_V=30.0):
    def value(key):
        item = settings[key]
        return str(item).lower() if isinstance(item, bool) else repr(item)
    lines = [f'{key} = {value(key)}' for key in hub_module.EXPERIMENT_KEYS]
    lines.append(f'variac_voltage_V = {variac_voltage_V!r}')
    return '\n'.join(lines) + '\n'


def controller_telemetry(request_id, settings, state='RUNNING', command_ok=True, heater_on=False,
                         program='single', phase=None, setpoint_C=None, slope_C_per_s=0.0):
    if phase is None:
        phase = 'HEAT_100' if program in {'exp4', 'exp5', 'exp6'} else 'SINGLE'
    if setpoint_C is None:
        setpoint_C = {'HEAT_100': 100.0, 'HOLD_100': 100.0, 'RAMP_200': 100.0,
                      'BOOST_FINAL': 200.0, 'HOLD_FINAL': settings['target_C']}.get(
                          phase, settings['target_C'])
    return {
        'protocol': 'exp2-v5',
        'state': state,
        'reason': state,
        'heater_on': heater_on,
        'program': program,
        'phase': phase,
        'setpoint_C': setpoint_C,
        'slope_C_per_s': slope_C_per_s,
        'tc2_required': program in {'exp4', 'exp5', 'exp6'},
        'relay_contact': 'NC',
        'active_high': True,
        'hold_s': 0,
        'request_id': request_id,
        'command_ok': command_ok,
        'settings': settings,
    }


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
                       or (parts[0] in {'EXP4', 'EXP5', 'EXP6'} and parts[1] in {'START', 'NEXT'})))
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
        self.hub.consume(b'10.0,25,26')
        self.hub.consume(b'time_s,t1_C,t2_C')
        self.hub.consume(b'0.5,27,28')
        self.hub.consume(b'1.0,29,30')
        with (self.hub.run.path / 'data.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertNotEqual(rows[0]['epoch'], rows[1]['epoch'])
        self.assertEqual(rows[1]['epoch'], rows[2]['epoch'])
        self.assertEqual(float(rows[1]['board_time_s']), .5)

    def test_malformed_controller_state_does_not_destroy_acquisition(self):
        self.hub.consume(b'1.0,25,26')
        telemetry = controller_telemetry(1, experiment_settings())
        telemetry['state'] = []
        self.hub.consume(('#CTRL ' + json.dumps(telemetry)).encode())
        self.hub.consume(b'1.5,27,28')
        self.assertEqual(self.hub.bad_rows, 1)
        self.assertFalse(self.hub.controller_available)
        with (self.hub.run.path / 'data.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([(float(r['tc1_C']), float(r['tc2_C'])) for r in rows],
                         [(25, 26), (27, 28)])
    def test_v5_envelope_fields_and_conditional_tc2_are_strict(self):
        valid = controller_telemetry(1, exp4_settings(), program='exp4', phase='HOLD_100')
        invalid = []
        for key, value in (
                ('protocol', 'exp2-v4'), ('program', 'exp3'), ('phase', 'SINGLE'),
                ('setpoint_C', float('nan')), ('slope_C_per_s', float('inf')),
                ('tc2_required', False)):
            report = dict(valid)
            report[key] = value
            invalid.append(report)
        single = controller_telemetry(2, experiment_settings())
        single['tc2_required'] = True
        invalid.append(single)
        invalid.append(dict(valid, settings=exp4_settings(tc1_cutoff_C=731.0)))
        for report in invalid:
            with self.subTest(report={key: report[key] for key in
                                      ('protocol', 'program', 'phase', 'setpoint_C',
                                       'slope_C_per_s', 'tc2_required')}):
                before = self.hub.bad_rows
                self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
                self.assertEqual(self.hub.bad_rows, before + 1)
                self.assertIsNone(self.hub.controller_received)
        self.hub.consume(('#CTRL ' + json.dumps(valid)).encode())
        self.assertEqual(self.hub.controller['program'], 'exp4')
        self.assertEqual(self.hub.controller['phase'], 'HOLD_100')
        self.assertTrue(self.hub.controller['tc2_required'])

    def test_exp5_telemetry_requires_timed_hold_and_exact_cutoffs(self):
        valid = controller_telemetry(2, exp5_settings(), state='HOLD',
                                     program='exp5', phase='HOLD_FINAL')
        self.hub.consume(('#CTRL ' + json.dumps(valid)).encode())
        self.assertEqual(self.hub.controller['program'], 'exp5')
        self.assertEqual(self.hub.controller['phase'], 'HOLD_FINAL')
        invalid = (
            dict(valid, settings=exp5_settings(hold_s=0.0)),
            dict(valid, settings=exp5_settings(tc1_cutoff_C=729.0)),
            dict(valid, settings=exp5_settings(tc2_cutoff_C=85.0)),
            dict(valid, settings=exp5_settings(target_C=699.0)),
            dict(valid, tc2_required=False),
            dict(valid, phase='SINGLE'),
        )
        for report in invalid:
            with self.subTest(program=report['program'], phase=report['phase'],
                              settings=report['settings']):
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
        self.experiment_path = self.config_path.parent / 'experiment.toml'
        self.experiment_path.write_text(experiment_text(experiment_settings()))
        self.experiment3_path = self.config_path.parent / 'experiment3.toml'
        self.experiment3_path.write_text(experiment_text(
            experiment_settings(tc2_cutoff_C=85.0, swap_inputs=True), variac_voltage_V=65.0))
        self.experiment4_path = self.config_path.parent / 'experiment4.toml'
        self.experiment4_path.write_text(experiment_text(exp4_settings(), variac_voltage_V=100.0))
        self.experiment5_path = self.config_path.parent / 'experiment5.toml'
        self.experiment5_path.write_text(experiment_text(exp5_settings(), variac_voltage_V=100.0))
        self.experiment6_path = self.config_path.parent / 'experiment6.toml'
        self.experiment6_path.write_text(experiment_text(exp5_settings(), variac_voltage_V=100.0))
        self.hub = hub_module.Hub({'plot_points': 10}, base / 'runs', self.config_path)
        self.port = FakePort(self.hub)
        self.hub.port = self.port
        self.hub.device = 'fake serial'

    async def asyncTearDown(self):
        self.hub.stop('Test complete')
        self.storage.cleanup()

    async def start_exp4(self):
        requested = exp4_settings()
        self.port.queue(requested, program='exp4', phase='HEAT_100')
        result = await self.hub.execute_command('start exp4')
        self.assertEqual(result['effect'], 'live')
        return requested

    def enter_exp4_hold(self, heater=100.0):
        settings = self.hub.controller['settings']
        report = controller_telemetry(self.hub.request_id, settings, state='HOLD',
                                      program='exp4', phase='HOLD_100')
        self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
        self.hub.consume(f'1.0,25,{heater}'.encode())

    async def start_exp5(self):
        requested = exp5_settings()
        self.port.queue(requested, program='exp5', phase='HEAT_100')
        result = await self.hub.execute_command('start exp5')
        self.assertEqual(result['effect'], 'live')
        return requested

    def enter_exp5_hold(self, heater=100.0):
        settings = self.hub.controller['settings']
        report = controller_telemetry(self.hub.request_id, settings, state='HOLD',
                                      program='exp5', phase='HOLD_100')
        self.hub.consume(('#CTRL ' + json.dumps(report)).encode())
        self.hub.consume(f'1.0,25,{heater}'.encode())

    async def test_invalid_edit_leaves_current_run_and_serial_untouched(self):
        requested = experiment_settings()
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
                self.experiment_path.write_text(source)
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp2')

        self.assertIs(self.hub.run, current)
        self.assertFalse(current.data.closed)
        self.assertFalse(current.events.closed)
        self.assertEqual((current.path / 'events.csv').read_bytes(), events_before)
        self.assertEqual((current.path / 'notes.md').read_bytes(), notes_before)
        self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_acknowledgement_mismatch_stops_without_claiming_configuration(self):
        requested = experiment_settings()
        mismatched = experiment_settings(target_C=299)
        self.port.queue(mismatched)
        self.port.queue(mismatched, state='STOPPED')
        with self.assertRaises(hub_module.ControlError):
            await self.hub.start_experiment('exp2')
        self.assertFalse((self.hub.run.path / 'experiment-applied.json').exists())
        self.assertEqual(self.hub.controller['state'], 'STOPPED')


    async def test_exp3_mapping_persists_without_changing_raw_csv(self):
        requested = experiment_settings(tc2_cutoff_C=85.0, swap_inputs=True)
        self.port.queue(requested)
        result = await self.hub.execute_command('start exp3')
        self.assertEqual(result['effect'], 'live')
        run_path = self.hub.run.path
        self.hub.consume(b'1.0,25,300')
        with (run_path / 'data.csv').open() as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual((float(row['tc1_C']), float(row['tc2_C'])), (25.0, 300.0))
        metadata = json.loads((run_path / 'run-metadata.json').read_text())
        self.assertEqual(metadata, {'experiment': 'exp3', 'swap_inputs': True,
                                    'variac_voltage_V': 65.0})
        applied = json.loads((run_path / 'experiment-applied.json').read_text())
        self.assertTrue(applied['requested']['swap_inputs'])
        self.assertTrue(applied['applied']['swap_inputs'])
        status = self.hub.status()
        self.assertTrue(status['display_swapped'])
        self.assertEqual(status['experiment'], 'exp3')
        self.assertEqual(status['variac_voltage_V'], 65.0)
        self.port.queue(requested, state='STOPPED')
        await self.hub.execute_command('stop exp3')
        self.assertEqual(self.hub.run.path, run_path)
        self.assertFalse(self.hub.run.data.closed)

        self.hub.stop('Test saved run')
        restarted = hub_module.Hub({'plot_points': 10}, self.hub.root, self.config_path)
        self.assertTrue(restarted.status()['display_swapped'])
        viewed = await restarted.execute_command(f'view {run_path.name}')
        self.assertTrue(viewed['display_swapped'])
        self.assertEqual(viewed['experiment'], 'exp3')
        self.assertEqual(viewed['variac_voltage_V'], 65.0)

    async def test_swap_acknowledgement_mismatch_stops_and_saves_no_applied_snapshot(self):
        mismatched = experiment_settings(tc2_cutoff_C=85.0, swap_inputs=False)
        self.port.queue(mismatched)
        self.port.queue(mismatched, state='STOPPED')
        with self.assertRaisesRegex(hub_module.ControlError, 'swap_inputs'):
            await self.hub.execute_command('start exp3')
        self.assertFalse((self.hub.run.path / 'experiment-applied.json').exists())
        self.assertEqual(self.hub.controller['state'], 'STOPPED')

    async def test_exp4_start_next_stop_retain_run_and_raw_channels(self):
        requested = await self.start_exp4()
        run = self.hub.run
        run_path = run.path
        self.assertEqual(self.port.writes[0], b'EXP2 PING\n')
        self.assertTrue(self.port.writes[1].startswith(b'EXP4 START '))
        self.assertEqual(self.hub.controller['program'], 'exp4')
        self.assertEqual(self.hub.controller['phase'], 'HEAT_100')
        metadata = json.loads((run_path / 'run-metadata.json').read_text())
        self.assertEqual(metadata, {'experiment': 'exp4', 'swap_inputs': True,
                                    'variac_voltage_V': 100.0})
        applied = json.loads((run_path / 'experiment-applied.json').read_text())
        self.assertEqual(applied['requested'], requested)
        self.assertEqual(applied['applied'], requested)

        self.enter_exp4_hold()
        with (run_path / 'data.csv').open() as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual((float(row['tc1_C']), float(row['tc2_C'])), (25.0, 100.0))
        self.assertIn('HOLD_100', (run_path / 'events.csv').read_text())
        self.port.queue(requested, program='exp4', phase='RAMP_200')
        result = await self.hub.execute_command('next')
        self.assertIn('RAMP_200', result['message'])
        self.assertIs(self.hub.run, run)
        self.assertEqual(self.hub.controller['phase'], 'RAMP_200')
        self.assertTrue(self.port.writes[-1].startswith(b'EXP4 NEXT '))
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [run_path])

        self.port.queue(requested, state='STOPPED', program='exp4', phase='RAMP_200')
        await self.hub.execute_command('stop exp4')
        self.assertTrue(self.port.writes[-1].startswith(b'EXP2 STOP '))
        self.assertIs(self.hub.run, run)
        self.assertFalse(run.data.closed)

        status = self.hub.status()
        self.assertEqual(status['experiment'], 'exp4')
        self.assertEqual(status['variac_voltage_V'], 100.0)
        self.assertTrue(status['display_swapped'])
        viewed = await self.hub.execute_command(f'view {run_path.name}')
        self.assertEqual(viewed['experiment'], 'exp4')
        self.assertEqual(viewed['variac_voltage_V'], 100.0)
        config = json.loads((await self.hub.execute_command('config'))['message'])
        self.assertEqual(config['experiments']['exp4']['edited_settings'], requested)
        self.assertEqual(config['experiments']['exp4']['variac_voltage_V'], 100.0)
        help_text = (await self.hub.execute_command('help'))['message']
        self.assertIn('start exp4', help_text)
        self.assertIn('next', help_text)

    async def test_exp5_start_next_snapshot_config_and_help(self):
        source = experiment_text(exp5_settings(), variac_voltage_V=100.0) + '# exact START source\n'
        self.experiment5_path.write_text(source)
        requested = await self.start_exp5()
        run = self.hub.run
        self.assertEqual(self.port.writes[0], b'EXP2 PING\n')
        self.assertEqual(self.port.writes[1],
                         b'EXP5 START 1 700 3 730 120 1 5000 5000 5 60000 1\n')
        self.assertEqual(self.hub.controller['program'], 'exp5')
        self.assertEqual(self.hub.controller['phase'], 'HEAT_100')
        self.assertEqual((run.path / 'experiment.toml').read_text(), source)
        snapshot = json.loads((run.path / 'experiment-applied.json').read_text())
        self.assertEqual(snapshot['requested'], requested)
        self.assertEqual(snapshot['applied'], requested)
        self.assertEqual(json.loads((run.path / 'run-metadata.json').read_text()), {
            'experiment': 'exp5', 'swap_inputs': True, 'variac_voltage_V': 100.0})

        self.enter_exp5_hold()
        self.port.queue(requested, program='exp5', phase='RAMP_200')
        result = await self.hub.execute_command('next')
        self.assertIn('EXP5/RAMP_200', result['message'])
        self.assertIs(self.hub.run, run)
        self.assertEqual(self.port.writes[-1], b'EXP5 NEXT 2\n')
        self.assertEqual(sum(line.startswith(b'EXP5 NEXT ') for line in self.port.writes), 1)

        config = json.loads((await self.hub.execute_command('config'))['message'])
        self.assertEqual(config['experiments']['exp5']['edited_settings'], requested)
        self.assertEqual(config['experiments']['exp5']['variac_voltage_V'], 100.0)
        help_text = (await self.hub.execute_command('help'))['message']
        self.assertIn('start exp5', help_text)
        self.assertIn('EXP4/EXP5', help_text)

    async def test_exp6_next_sent_from_heat_100_at_any_temperature(self):
        requested = exp5_settings()
        self.port.queue(requested, program='exp6', phase='HEAT_100')
        result = await self.hub.execute_command('start exp6')
        self.assertEqual(result['effect'], 'live')
        self.assertTrue(self.port.writes[-1].startswith(b'EXP6 START 1 700 3 730 120 1 '))
        self.hub.consume(b'1.0,25,40')  # heater far below the 100 C band
        self.port.queue(requested, program='exp6', phase='RAMP_200')
        result = await self.hub.execute_command('next')
        self.assertIn('EXP6/RAMP_200', result['message'])
        self.assertEqual(self.port.writes[-1], b'EXP6 NEXT 2\n')

    async def test_barrier_is_recorded_in_run_metadata_and_notes(self):
        self.experiment6_path.write_text(experiment_text(exp5_settings(), variac_voltage_V=100.0)
                                         + 'barrier = "1 mica / 2 ceramic fiber / 1 aluminum"\n')
        self.port.queue(exp5_settings(), program='exp6', phase='HEAT_100')
        await self.hub.execute_command('start exp6')
        metadata = json.loads((self.hub.run.path / 'run-metadata.json').read_text())
        self.assertEqual(metadata['barrier'], '1 mica / 2 ceramic fiber / 1 aluminum')
        self.assertIn('- Barrier: 1 mica / 2 ceramic fiber / 1 aluminum\n',
                      (self.hub.run.path / 'notes.md').read_text())
        self.assertEqual(self.hub.display_metadata()['barrier'], metadata['barrier'])
        self.hub.stop('Test')
        self.hub.start()  # plain recording after the run must not inherit the barrier
        self.assertNotIn('barrier', json.loads((self.hub.run.path / 'run-metadata.json').read_text()))

    async def test_invalid_exp5_envelope_preserves_run_and_serial(self):
        requested = experiment_settings()
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        invalid_settings = (
            exp5_settings(target_C=699.0), exp5_settings(tc1_cutoff_C=729.0),
            exp5_settings(tc2_cutoff_C=119.9), exp5_settings(tc2_cutoff_enabled=False),
            exp5_settings(hold_s=0.0), exp5_settings(hold_s=59.999),
            exp5_settings(hold_s=60.001), exp5_settings(hysteresis_C=5.1),
            exp5_settings(hold_band_C=5.1),
        )
        for settings in invalid_settings:
            with self.subTest(settings=settings):
                self.experiment5_path.write_text(experiment_text(settings, variac_voltage_V=100.0))
                with self.assertRaises(ValueError):
                    await self.hub.start_experiment('exp5')
                self.assertIs(self.hub.run, current)
                self.assertEqual(self.port.writes, writes_before)
        self.assertEqual([p for p in self.hub.root.iterdir() if p.is_dir()], [current.path])

    async def test_invalid_exp4_envelope_preserves_run_and_serial(self):
        requested = experiment_settings()
        self.port.queue(requested)
        await self.hub.start_experiment('exp2')
        current = self.hub.run
        writes_before = list(self.port.writes)
        invalid_settings = (
            exp4_settings(target_C=200.0), exp4_settings(target_C=700.1),
            exp4_settings(tc1_cutoff_C=700.0), exp4_settings(tc1_cutoff_C=730.1),
            exp4_settings(tc2_cutoff_C=84.9), exp4_settings(tc2_cutoff_enabled=False),
            exp4_settings(hold_s=0.001), exp4_settings(hysteresis_C=5.1),
            exp4_settings(hold_band_C=5.1),
        )
        for settings in invalid_settings:
            with self.subTest(settings=settings):
                self.experiment4_path.write_text(experiment_text(settings, variac_voltage_V=100.0))
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
        self.assertTrue(any(line.startswith(b'EXP4 START ') for line in self.port.writes))
        self.assertTrue(self.port.writes[-1].startswith(b'EXP2 STOP '))

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
        self.assertTrue(self.port.writes[-1].startswith(b'EXP4 NEXT '))
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
        self.assertTrue(self.port.writes[-2].startswith(b'EXP4 NEXT '))
        self.assertTrue(self.port.writes[-1].startswith(b'EXP2 STOP '))
        self.assertEqual(self.hub.controller['state'], 'STOPPED')
        self.assertEqual(self.hub.controller['phase'], 'HOLD_100')
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
        self.assertTrue(self.port.writes[-1].startswith(b'EXP2 STOP '))
        self.assertEqual(self.hub.controller['state'], 'STOPPED')
        self.assertFalse(self.hub.control_uncertain)

    async def test_next_requires_hold_phase_and_fresh_in_band_heater(self):
        await self.start_exp4()
        writes_before = list(self.port.writes)
        with self.assertRaisesRegex(hub_module.ControlError, 'HOLD_100'):
            await self.hub.execute_command('next')
        self.enter_exp4_hold(heater=110.0)
        with self.assertRaisesRegex(hub_module.ControlError, 'within 100 C'):
            await self.hub.execute_command('next')
        self.assertEqual(self.port.writes, writes_before)

    async def test_legacy_run_annotation_survives_restart_and_history_view(self):
        run_path = self.hub.root / '017'
        run_path.mkdir(parents=True)
        (run_path / 'data.csv').write_text(
            ','.join(hub_module.FIELDS) + '\n2026-01-01T00:00:00Z,0,1,0,25,300,\n')
        self.hub.run_mappings_path = Path(self.storage.name) / 'run-mappings.json'
        self.hub.run_mappings_path.write_text(json.dumps({
            '017': {'swap_inputs': True, 'reason': 'Operator reported reversed probes'}
        }))
        restarted = hub_module.Hub({'plot_points': 10}, self.hub.root, self.config_path)
        restarted.run_mappings_path = self.hub.run_mappings_path
        self.assertTrue(restarted.status()['display_swapped'])
        restarted.start()
        self.assertEqual(restarted.run.path.name, '018')
        self.assertTrue(restarted.status()['display_swapped'])
        inherited = json.loads((restarted.run.path / 'run-metadata.json').read_text())
        self.assertTrue(inherited['swap_inputs'])
        restarted.stop('Test complete')
        viewed = await restarted.execute_command('view 017')
        self.assertTrue(viewed['display_swapped'])
        self.assertEqual(viewed['experiment'], 'exp2')
        self.assertEqual(viewed['points'][0][-2:], [25.0, 300.0])


if __name__ == '__main__':
    unittest.main()
