#!/usr/bin/env python3
"""Local, read-only serial DAQ. No firmware uploads or hardware controls."""
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
HELP = '''Auto-start: the first successful serial connection starts a saved run.
start              Start a new saved run (or keep the active one).
stop               Finalize recording; serial stays open, no samples saved/plotted.
restart            Finalize current run and start a fresh directory.
save               Flush current files and report their location; keep recording.
clear              Clear this browser's plot/console only; never delete data.
list               List saved runs, newest first.
view 001           Plot saved data, marked HISTORICAL; recording continues.
live               Restore the current run's live plot.
note your text     Append a comment to the active run, even in historical view.
window 120         Show the latest 120 seconds (window all for retained points).
status             Show connection, recording, faults and saved location.
config / channels  Show configuration (edit hub.toml, restart server to change).
reconnect          Close/reopen serial once; opening may reset the board.
help               Show commands. Up/Down recalls command history.
Plots retain at most the configured plot_points; CSV retains every saved row.
NaN is a fault/gap, not zero. All-zero readings do not validate sensors.
No probe identity or calibration is inferred. No heater controls are provided.'''


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class Run:
    def __init__(self, root, config, device):
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
    def __init__(self, config, root):
        self.config = config
        self.root = root
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

    def event(self, text):
        self.events.append({'utc': utc(), 'text': text})
        print(f'{utc()} {text}', flush=True)
        if self.run:
            self.run.event(text)

    def start(self):
        if not self.run:
            self.run = Run(self.root, self.config, self.device)
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

    async def disconnect(self):
        if self.reader:
            self.reader.cancel()
            try:
                await self.reader
            except asyncio.CancelledError:
                pass
            self.reader = None
        if self.port:
            # A pending blocking read has a short timeout; close only after it completes.
            await asyncio.to_thread(self.port.close)
            self.port = None
        if self.buffer:
            self.event(f'Incomplete serial row at close discarded: {self.buffer[:160]!r}')
        self.buffer = b''
        self.device = 'disconnected'

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
            self.port = await asyncio.to_thread(serial.Serial, name, cfg['baud'], timeout=0.3, exclusive=True)
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
            self.port.close()
            self.port = None
            self.device = 'disconnected'
        except Exception as exc:
            self.event(f'Acquisition stopped by error: {exc}')
            self.stop(f'Acquisition error: {exc}')
            if self.port:
                self.port.close()
                self.port = None
            self.device = 'disconnected'

    def consume(self, raw):
        if not raw.strip():
            return
        if raw.strip() == b'time_s,t1_C,t2_C':
            self.event('CSV header received (startup/reset).')
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
            self.epoch += 1
            flags.append('board_time_regression')
            self.event(f'Board time regressed {self.last_board} → {board}; new epoch {self.epoch}.')
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
        return {'device': self.device, 'connected': self.port is not None,
                'recording': self.run is not None, 'run': self.last_run.name if self.last_run else None,
                'path': str(self.last_run) if self.last_run else None,
                'rows': self.run.rows if self.run else None, 'age': age, 'values': self.values,
                'zero_count': self.zero_count, 'bad_rows': self.bad_rows, 'epoch': self.epoch,
                'sequence': self.sequence, 'plot_points': self.config['plot_points'],
                'events': list(self.events)}

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
        parts = shlex.split(text)
        if not parts:
            raise ValueError('Enter a command; help lists commands.')
        cmd, *args = parts
        no_args = {'help', 'status', 'start', 'stop', 'restart', 'save', 'clear', 'list', 'live', 'config', 'channels', 'reconnect'}
        if cmd in no_args and args:
            raise ValueError(f'{cmd} takes no arguments')
        result = {}
        if cmd == 'help':
            message = HELP
        elif cmd == 'status':
            message = json.dumps(self.status(), indent=2)
        elif cmd in ('config', 'channels'):
            message = json.dumps(self.config, indent=2) + '\nEdit hub.toml and restart the server to apply changes.'
        elif cmd == 'start':
            message = self.start()
            result['effect'] = 'live'
        elif cmd == 'stop':
            message = self.stop('Stopped by command')
        elif cmd == 'restart':
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
            result.update(effect='history', name=args[0], points=self.history(args[0]))
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
            await self.connect()
            message = f'Connection: {self.device}. Opening serial may reset the board.'
        else:
            raise ValueError(f'Unknown command: {cmd}. Type help.')
        return dict(result, message=message)


async def serve(config_path, runs_override=None, port_override=None):
    config = tomllib.loads(config_path.read_text())
    if config['plot_points'] < 2 or config['serial']['baud'] <= 0:
        raise ValueError('plot_points must be >=2 and serial baud positive')
    root = Path(runs_override) if runs_override else config_path.parent / config['runs_dir']
    hub = Hub(config, root.resolve())
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
        await hub.connect()

    async def cleanup(app):
        await hub.disconnect()
        hub.stop('Application shutdown')

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
    args = parser.parse_args()
    async def make_app():
        app, _ = await serve(args.config.resolve(), args.runs_dir, args.port)
        return app
    config = tomllib.loads(args.config.read_text())
    web.run_app(make_app(), host='127.0.0.1', port=args.port or config['port'])


if __name__ == '__main__':
    main()
