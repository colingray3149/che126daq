"""Local web server: the page in web/ and a small JSON API.

GET  /api/state                    everything the page shows (also pushed on /api/stream)
GET  /api/stream                   server-sent events: state, sample, event
GET  /api/live                     samples since the page/run started
GET  /api/ports                    serial ports
GET  /api/programs                 programs/*.json
GET  /api/runs                     run list;  /api/runs/<id>  detail;  /api/runs/<id>/data  arrays
GET  /runs/<id>/<file>             files inside a run folder
POST /api/cmd {cmd: start|next|stop|end|heat_on|heat_off|hold|clear|reconnect|restart|note}
POST /api/settings {...changes}    POST /api/programs {...program}   POST /api/programs/delete {file}
POST /api/preview {program, next_after_s}                     predicted run
POST /api/runs/<id>/notes {text}   POST /api/runs/<id>/meta {title, setup}
POST /api/runs/<id>/png/<name>     PNG bytes      POST /api/firmware {port}
"""

from __future__ import annotations

import json
import os
import queue
import re
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import board

CTYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".png": "image/png", ".svg": "image/svg+xml", ".csv": "text/csv; charset=utf-8", ".md": "text/plain; charset=utf-8",
    ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".toml": "text/plain; charset=utf-8",
    ".html_report": "text/html",
}


def make_handler(app, web_dir):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "che126daq"

        def log_message(self, fmt, *args):
            pass

        def _json(self, obj, status=200):
            body = json.dumps(obj, separators=(",", ":"), allow_nan=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _error(self, msg, status=400):
            self._json({"error": msg}, status)

        def _file(self, path, download=False):
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                return self._error("not found", 404)
            ext = os.path.splitext(path)[1].lower()
            self.send_response(200)
            self.send_header("Content-Type", CTYPES.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(path))
            self.end_headers()
            self.wfile.write(data)

        def _index(self):
            # Stamp asset URLs with their modification time so a browser never runs
            # an old cached app.js against new HTML (it happened with the old hub's tab).
            with open(os.path.join(web_dir, "index.html"), encoding="utf-8") as f:
                html = f.read()

            def stamp(m):
                rel = m.group(2)
                try:
                    v = int(os.path.getmtime(os.path.join(web_dir, rel)))
                except OSError:
                    v = 0
                return '%s="/web/%s?v=%d"' % (m.group(1), rel, v)

            html = re.sub(r'(src|href)="/web/([^"?]+)"', stamp, html)
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 20_000_000:
                raise ValueError("request too large")
            return self.rfile.read(n) if n else b""

        def _guard(self, fn):
            try:
                fn()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except KeyError:
                self._error("not found", 404)
            except ValueError as e:
                self._error(str(e))
            except Exception as e:
                traceback.print_exc()
                self._error("%s: %s" % (type(e).__name__, e), 500)

        def do_GET(self):
            self._guard(self._get)

        def do_POST(self):
            self._guard(self._post)

        def _get(self):
            url = urlparse(self.path)
            path = unquote(url.path)
            q = parse_qs(url.query)
            if path in ("/", "/index.html"):
                return self._index()
            if path.startswith("/web/"):
                rel = os.path.normpath(path[5:])
                if rel.startswith("..") or os.path.isabs(rel):
                    return self._error("not found", 404)
                return self._file(os.path.join(web_dir, rel))
            if path.startswith("/analysis/"):
                rel = os.path.normpath(path[len("/analysis/"):])
                if rel.startswith("..") or os.path.isabs(rel):
                    return self._error("not found", 404)
                return self._file(os.path.join(app.root, "analysis", rel))
            if path == "/api/ping":
                return self._json({"app": "che126daq"})
            if path == "/api/state":
                return self._json(app.state())
            if path == "/api/live":
                with app.lock:
                    rows = list(app.live)
                    events = list(app.events)
                    run_start = (time.monotonic() - app.session_start - app.run.elapsed()) if app.run else None
                return self._json({
                    "t": [r[0] for r in rows], "tc1": [r[1] for r in rows], "tc2": [r[2] for r in rows], "tc3": [r[3] for r in rows],
                    "heat": [r[4] for r in rows], "sp": [r[5] for r in rows], "sp_tc": [r[6] for r in rows],
                    "events": events, "run_start": run_start,
                    "predicted": (app.run.meta.get("predicted") if app.run else None),
                })
            if path == "/api/stream":
                return self._stream()
            if path == "/api/ports":
                return self._json({"ports": board.list_ports()})
            if path == "/api/programs":
                return self._json({"programs": app.list_programs()})
            if path == "/api/runs":
                return self._json({"runs": app.library.list()})
            m = re.fullmatch(r"/api/runs/(\d{3,})", path)
            if m:
                return self._json(app.library.detail(m.group(1)))
            m = re.fullmatch(r"/api/runs/(\d{3,})/data", path)
            if m:
                return self._json(app.library.load(m.group(1)))
            m = re.fullmatch(r"/runs/(\d{3,})/([A-Za-z0-9_. -]+)", path)
            if m and ".." not in m.group(2):
                return self._file(os.path.join(app.library.folder(m.group(1)), m.group(2)), download="dl" in q)
            return self._error("not found", 404)

        def _stream(self):
            q = queue.Queue(maxsize=4000)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with app.clients_lock:
                app.clients.append(q)
            try:
                self.wfile.write(("retry: 1500\nevent: state\ndata: %s\n\n" % json.dumps(app.state(), default=str)).encode())
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=10)
                    except queue.Empty:
                        msg = ": keepalive\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                with app.clients_lock:
                    if q in app.clients:
                        app.clients.remove(q)
                self.close_connection = True

        def _post(self):
            path = urlparse(self.path).path
            m = re.fullmatch(r"/api/runs/(\d{3,})/png/([A-Za-z0-9_-]+)", path)
            if m:
                folder = app.library.folder(m.group(1))
                data = self._body()
                if not data.startswith(b"\x89PNG"):
                    raise ValueError("not a PNG")
                tmp = os.path.join(folder, m.group(2) + ".png.tmp")
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, os.path.join(folder, m.group(2) + ".png"))
                app.refresh_readmes(m.group(1))
                return self._json({"ok": True})
            raw = self._body()
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except ValueError:
                raise ValueError("request body is not JSON")
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            if path == "/api/cmd":
                return self._cmd(body)
            if path == "/api/settings":
                return self._json(app.apply_settings(body))
            if path == "/api/programs":
                return self._json({"ok": True, "file": app.save_program(body)})
            if path == "/api/programs/delete":
                app.delete_program(body.get("file"))
                return self._json({"ok": True})
            if path == "/api/preview":
                return self._json(app.preview(body.get("program"), body.get("next_after_s")))
            m = re.fullmatch(r"/api/runs/(\d{3,})/notes", path)
            if m:
                app.library.save_notes(m.group(1), str(body.get("text") or ""))
                app.refresh_readmes(m.group(1))
                return self._json({"ok": True})
            m = re.fullmatch(r"/api/runs/(\d{3,})/meta", path)
            if m:
                return self._json(app_update_meta(app, m.group(1), body))
            if path == "/api/firmware":
                port = body.get("port") or app.board.port
                if not port or port.startswith("sim://"):
                    raise ValueError("pick the board's serial port first (Settings > Serial port)")
                app.upload_firmware(port)
                return self._json({"ok": True})
            return self._error("not found", 404)

        def _cmd(self, body):
            cmd = body.get("cmd")
            if cmd == "start":
                rid = app.start_run(body.get("program"), body.get("title"), body.get("setup"), body.get("variac_V"))
                return self._json({"ok": True, "run": rid})
            if cmd == "next":
                app.next()
            elif cmd == "stop":
                app.stop_heat()
            elif cmd == "end":
                app.end_run()
            elif cmd == "heat_on":
                app.manual_heat("on", cutoffs=body.get("cutoffs"))
            elif cmd == "heat_off":
                app.manual_heat("off")
            elif cmd == "hold":
                if body.get("temp") in (None, ""):
                    raise ValueError("type a hold temperature")
                app.manual_heat("hold", body.get("tc"), body.get("temp"), cutoffs=body.get("cutoffs"))
            elif cmd == "clear":
                app.clear_trip()
            elif cmd == "reconnect":
                app.event("Reconnect requested")
                app.board.reconnect()
            elif cmd == "restart":
                app.restart()
            elif cmd == "note":
                text = str(body.get("text") or "").strip()
                if not app.run:
                    raise ValueError("start a run first; notes go into the run's events")
                if text:
                    app.event("Note: " + text)
            else:
                raise ValueError("unknown command %r" % cmd)
            return self._json({"ok": True})

    return Handler


def app_update_meta(app, rid, body):
    from .util import atomic_write

    folder = app.library.folder(rid)
    meta = app.library.meta(rid)
    if not meta:
        raise ValueError("runs before this app keep their details in runs/catalog.json")
    for k in ("title", "setup"):
        if k in body:
            meta[k] = str(body[k])[:2000]
    atomic_write(os.path.join(folder, "run.json"), json.dumps(meta, indent=1) + "\n")
    if app.run and app.run.number == rid:
        app.run.meta.update({k: meta[k] for k in ("title", "setup")})
    else:
        app.refresh_readmes(rid)
    return {"ok": True}


def serve(app, web_dir, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, web_dir))
    server.daemon_threads = True
    return server
