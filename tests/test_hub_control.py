"""Consumer-visible acquisition boundaries and Experiment 2/3 configuration behavior."""
import asyncio
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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


def experiment_text(settings, variac_voltage_V=30.0):
    def value(key):
        item = settings[key]
        return str(item).lower() if isinstance(item, bool) else repr(item)
    lines = [f'{key} = {value(key)}' for key in hub_module.EXPERIMENT_KEYS]
    lines.append(f'variac_voltage_V = {variac_voltage_V!r}')
    return '\n'.join(lines) + '\n'


def controller_telemetry(request_id, settings, state='RUNNING', command_ok=True, heater_on=False):
    return {
        'protocol': 'exp2-v4',
        'state': state,
        'reason': state,
        'heater_on': heater_on,
        'tc2_required': False,
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

    def queue(self, settings, state='RUNNING', command_ok=True, heater_on=False):
        self.acknowledgements.append((settings, state, command_ok, heater_on))

    def write(self, data):
        self.writes.append(data)
        parts = data.decode('ascii').strip().split()
        if len(parts) >= 3 and parts[0] == 'EXP2' and parts[1] in {'START', 'STOP'}:
            settings, state, command_ok, heater_on = self.acknowledgements.pop(0)
            report = controller_telemetry(int(parts[2]), settings, state, command_ok, heater_on)
            raw = ('#CTRL ' + json.dumps(report)).encode('ascii')
            self.loop.call_soon_threadsafe(self.hub.consume, raw)
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
        self.hub = hub_module.Hub({'plot_points': 10}, base / 'runs', self.config_path)
        self.port = FakePort(self.hub)
        self.hub.port = self.port
        self.hub.device = 'fake serial'

    async def asyncTearDown(self):
        self.hub.stop('Test complete')
        self.storage.cleanup()




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
