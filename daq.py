#!/usr/bin/env python3
"""CHE 126 DAQ — run this file.

    python daq.py            (or press Run in VS Code / Zed)

It finds the Arduino, opens the control page in your browser and records every
run under runs/. Nothing to install: the serial library ships in vendor/.

    python daq.py --sim         practice with a simulated rig (no hardware)
    python daq.py --port COM5   use this serial port
    python daq.py --no-browser  do not open a browser tab
"""

import os
import sys

if sys.version_info < (3, 8):
    sys.exit("Python 3.8 or newer is needed; this is Python %s." % sys.version.split()[0])

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
sys.path.insert(0, ROOT)


def main():
    import argparse
    import json
    import threading
    import urllib.request
    import webbrowser

    from che126.app import App
    from che126.server import serve

    ap = argparse.ArgumentParser(description="CHE 126 DAQ")
    ap.add_argument("--port", help="serial port, e.g. COM5 or /dev/cu.usbmodem1101 (default: find the Arduino)")
    ap.add_argument("--sim", action="store_true", help="practice with a simulated rig")
    ap.add_argument("--http-port", type=int, help="page port (default 8765)")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = ap.parse_args()

    app = App(ROOT, forced_port=args.port or ("sim://" if args.sim else ""))
    port = args.http_port or int(app.settings.get().get("http_port") or 8765)
    url = "http://127.0.0.1:%d/" % port
    try:
        server = serve(app, os.path.join(ROOT, "web"), port)
    except OSError:
        try:
            with urllib.request.urlopen(url + "api/ping", timeout=1) as r:
                running = json.load(r).get("app") == "che126daq"
        except Exception:
            running = False
        if running:
            print("The DAQ is already running. Opening %s" % url)
            if not args.no_browser:
                webbrowser.open(url)
            return
        sys.exit("Port %d is in use by another program. Start with: python daq.py --http-port %d" % (port, port + 1))

    print("CHE 126 DAQ")
    print("  Page:  %s" % url)
    print("  Runs:  %s" % app.settings.runs_dir(ROOT))
    print("  Quit:  Ctrl+C here (the heater turns off)")
    app.event("DAQ started" + (" in PRACTICE mode: simulated rig, no hardware" if args.sim else ""))
    app.board.start()
    threading.Thread(target=app.control_loop, name="control", daemon=True).start()
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping: heater off, saving the run.")
        try:
            app.board.send("HEAT 0")
            with app.lock:
                app.runner.stop("DAQ closed")
                app._finish_run("DAQ closed")
        finally:
            app.board.close()
            server.server_close()


if __name__ == "__main__":
    main()
