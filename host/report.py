#!/usr/bin/env python3
"""Read-only CSV snapshot to self-contained interactive graphs; never opens serial."""
import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import html
import io
import json
import math
from pathlib import Path
import tempfile
import time

import plotly.graph_objects as go

from hub import Hub


def snapshot(path):
    """Bound reads to the opening size; exclude a concurrently written partial row."""
    with path.open('rb') as stream:
        size = stream.seek(0, 2)
        stream.seek(0)
        data = stream.read(size)
    end = data.rfind(b'\n') + 1
    return data[:end], len(data) - end


def temperature(value):
    number = float(value)
    return number if math.isfinite(number) else None


def build_report(run_path, watch=False):
    run_path = Path(run_path).resolve()
    source, partial_bytes = snapshot(run_path / 'data.csv')
    rows = list(csv.DictReader(io.StringIO(source.decode('utf-8'))))
    if not rows:
        raise ValueError('No complete temperature samples saved yet')
    elapsed = [float(row['host_elapsed_s']) for row in rows]
    if any(not math.isfinite(t) or t < 0 for t in elapsed):
        raise ValueError('Invalid host elapsed time in saved CSV')
    if any(b < a for a, b in zip(elapsed, elapsed[1:])):
        raise ValueError('Saved host elapsed time decreases; refusing misleading connected trace')
    # Reuse the hub's saved/legacy mapping rules without connecting any hardware.
    metadata = Hub({'plot_points': 1}, run_path.parent,
                   run_path.parent.parent / 'hub.toml').display_metadata(run_path)
    settings_path = run_path / 'experiment-applied.json'
    settings = json.loads(settings_path.read_text())['applied'] if settings_path.exists() else None
    notes = (run_path / 'notes.md').read_text()
    state = next((line.split(': ', 1)[1] for line in notes.splitlines()
                  if line.startswith('- State / stop reason: ')), 'unknown')
    status = 'RECORDING SNAPSHOT — not final' if state == 'recording' else 'SAVED RUN SNAPSHOT'
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    digest = hashlib.sha256(source).hexdigest()
    run_name = html.escape(run_path.name)
    raw_channels = (2, 1) if metadata['swap_inputs'] else (1, 2)
    custom = [[html.escape(row['utc']), html.escape(row['flags'] or 'none'), row['epoch']]
              for row in rows]
    panels, summaries = [], []
    for i, (role, raw, color) in enumerate(zip(('HEATER', 'REAR'), raw_channels,
                                               ('#176bb6', '#b65000'))):
        values = [temperature(row[f'tc{raw}_C']) for row in rows]
        finite = [value for value in values if value is not None]
        label = f'TC{i + 1} · {role} (raw TC{raw})'
        fig = go.Figure(go.Scatter(
            x=elapsed, y=values, customdata=custom, name=label,
            mode='lines+markers' if len(finite) == 1 else 'lines',
            marker={'size': 7, 'color': color},
            connectgaps=False, line={'color': color, 'width': 2},
            hovertemplate=('Elapsed %{x:.2f} s<br>%{y:.2f} °C<br>UTC %{customdata[0]}'
                           '<br>Flags: %{customdata[1]}<br>Epoch: %{customdata[2]}'
                           '<extra>%{fullData.name}</extra>')))
        fig.update_layout(
            template='plotly_white', autosize=True, height=440,
            title={'text': f'Run {run_name} · {label}', 'x': 0.06, 'font': {'size': 17}},
            margin={'l': 82, 'r': 32, 't': 72, 'b': 80}, showlegend=False,
            font={'family': 'system-ui, sans-serif', 'size': 13},
            hovermode='closest', dragmode='zoom',
            xaxis={'title': {'text': 'Elapsed time since run start (s)', 'standoff': 18},
                   'range': [0, max(elapsed[-1], 1)], 'automargin': True,
                   'showline': True, 'ticks': 'outside', 'mirror': True},
            yaxis={'title': {'text': 'Temperature (°C)', 'standoff': 16},
                   'automargin': True, 'showline': True, 'ticks': 'outside', 'mirror': True})
        if not finite:
            fig.add_annotation(
                text='No finite temperature samples<br>Missing readings are not zero',
                x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False)
        detail = 'No saved controller settings for this run.'
        if settings:
            detail = (f'Heater target {settings["target_C"]:g}°C · high cutoff {settings["tc1_cutoff_C"]:g}°C'
                      if i == 0 else
                      (f'Rear cutoff {settings["tc2_cutoff_C"]:g}°C — applies to raw TC{raw}, not the heater'
                       if settings['tc2_cutoff_enabled'] else 'Rear cutoff disabled'))
            if i == 0 and metadata['experiment'] in {'exp4', 'exp5', 'exp6'}:
                program = metadata['experiment'].upper()
                final = ('; 60s from measured target, then heat OFF'
                         if program in {'EXP5', 'EXP6'} else '; indefinite final hold')
                detail = (f'{program}: hold 100°C → explicit NEXT → 90s ramp to 200°C → '
                          f'boost/hold {settings["target_C"]:g}°C · high cutoff '
                          f'{settings["tc1_cutoff_C"]:g}°C{final}; phase transitions are in saved events')
        graph = fig.to_html(full_html=False, include_plotlyjs=(i == 0),
                            div_id=f'tc{i + 1}-graph', config={
                                'responsive': True, 'displaylogo': False, 'scrollZoom': True,
                                'toImageButtonOptions': {'format': 'png', 'width': 1600,
                                                        'height': 800, 'scale': 2,
                                                        'filename': f'run-{run_path.name}-tc{i + 1}'},
                                'modeBarButtonsToRemove': ['select2d', 'lasso2d']})
        panels.append(f'<section class="panel"><p>{html.escape(detail)}</p>{graph}</section>')
        fmt = lambda v: '—' if v is None else f'{v:.2f}'
        summaries.append(f'<tr><th scope="row">{label}</th><td>{fmt(min(finite) if finite else None)}</td>'
                         f'<td>{fmt(max(finite) if finite else None)}</td><td>{fmt(values[-1])}</td>'
                         f'<td>{len(values) - len(finite)}</td></tr>')
    events_path = run_path / 'events.csv'
    event_rows = []
    if events_path.exists():
        event_data, _ = snapshot(events_path)
        event_rows = list(csv.DictReader(io.StringIO(event_data.decode('utf-8'))))
        # Do not include events recorded after the last snapshotted temperature.
        event_rows = [r for r in event_rows if r['utc'] <= rows[-1]['utc']]
    events = ''.join(f'<tr><td>{html.escape(r["utc"])}</td><td>{html.escape(r["event"])}</td></tr>'
                     for r in event_rows)
    download = base64.b64encode(source).decode('ascii')
    refresh_message = ('Auto-refresh every 15 seconds while the report watcher is running; '
                       'zoom and scroll are preserved. No DAQ controls.'
                       if watch else 'This offline snapshot does not update or control the DAQ. '
                       'Regenerate after recording ends for final graphs.')
    body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Run {run_name} · full temperature report</title>
<style>
* {{box-sizing:border-box}} body {{margin:0;background:#f4f6f9;color:#172333;font:15px/1.5 system-ui,sans-serif}}
main {{max-width:1600px;margin:auto;padding:24px}} h1 {{margin:4px 0;font-size:28px}}
.meta {{color:#4a5b6e;margin:6px 0;overflow-wrap:anywhere}} .status {{font-weight:650;color:#805400}}
.toolbar {{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:18px 0}}
button,.download {{border:1px solid #aab8c8;border-radius:5px;background:white;color:#172333;padding:9px 14px;font:inherit;cursor:pointer;text-decoration:none}}
button:focus-visible,a:focus-visible {{outline:3px solid #176bb6;outline-offset:2px}}
.plots {{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}
.panel {{min-width:0;background:white;border:1px solid #cbd4df;border-radius:8px}}
.panel p {{margin:12px 18px 0;color:#4a5b6e;font-size:13px}}
.table-wrap {{overflow-x:auto}} table {{width:100%;border-collapse:collapse;background:white;margin:14px 0}}
th,td {{text-align:left;padding:10px 14px;border-bottom:1px solid #dce2e9;vertical-align:top}}
summary {{cursor:pointer;font-weight:600;padding:12px 0}} pre {{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}
@media(max-width:1100px) {{.plots {{grid-template-columns:1fr}} main {{padding:12px}}}}
@media print {{.toolbar,.modebar {{display:none!important}} .plots {{display:block}} .panel {{break-inside:avoid;margin-bottom:18px}}}}
</style></head><body><main>
<div class="status">{status}</div><h1>Run {run_name} · temperature history</h1>
<p class="meta">{len(rows):,} complete samples · {elapsed[0]:.2f}–{elapsed[-1]:.2f} s · no downsampling or smoothing</p>
<p class="meta">First sample: {html.escape(rows[0]['utc'])}<br>Last sample: {html.escape(rows[-1]['utc'])}</p>
<p class="meta">Independent temperature axes. Blue TC1 = heater / raw TC{raw_channels[0]}; orange TC2 = rear / raw TC{raw_channels[1]}.
Manual preset {metadata['variac_voltage_V']:g} V (metadata, not measured); no voltage-based temperature scaling.</p>
<div class="toolbar"><button id="reset">Fit full run</button>
<label><input type="checkbox" id="link-time" checked> Link time-axis zoom</label>
<button data-svg="tc1-graph">Heater SVG</button><button data-svg="tc2-graph">Rear SVG</button>
<a class="download" download="run-{run_name}-snapshot.csv" href="data:text/csv;base64,{download}">Download raw CSV snapshot</a></div>
<p class="meta">Drag to zoom · shift-drag to pan · double-click to reset · camera saves high-resolution PNG.
{refresh_message}</p>
<div class="plots">{''.join(panels)}</div>
<div class="table-wrap"><table><caption>Measured temperatures (°C); missing/nonfinite readings remain gaps</caption>
<thead><tr><th>Probe / saved source</th><th>Minimum</th><th>Maximum</th><th>Last</th><th>Fault samples</th></tr></thead>
<tbody>{''.join(summaries)}</tbody></table></div>
<details><summary>Recorded events through this snapshot ({len(event_rows)})</summary><div class="table-wrap"><table>
<thead><tr><th>UTC</th><th>Event — serial reports are not physical power measurements</th></tr></thead><tbody>{events}</tbody></table></div></details>
<details><summary>Saved run notes and acquisition configuration</summary><pre>{html.escape(notes)}</pre></details>
<p class="meta">Generated {stamp}. Saved run state: {html.escape(state)}.<br>
Source: {html.escape(str(run_path / 'data.csv'))}<br>SHA-256 of included CSV: {digest}<br>
{partial_bytes} trailing incomplete bytes excluded. Sensor identity/calibration and relay power removal are not verified by these graphs.</p>
</main><script>
const graphs = ['tc1-graph','tc2-graph'].map(id => document.getElementById(id));
let synchronizing = false;
for (const graph of graphs) {{
  graph.on('plotly_relayout', async change => {{
    if (synchronizing || !document.getElementById('link-time').checked) return;
    const update = Object.fromEntries(Object.entries(change).filter(([key]) => key.startsWith('xaxis.range') || key === 'xaxis.autorange'));
    if (!Object.keys(update).length) return;
    synchronizing = true;
    try {{ await Plotly.relayout(graphs.find(other => other !== graph), update); }}
    finally {{ synchronizing = false; }}
  }});
}}
document.getElementById('reset').onclick = async () => {{
  synchronizing = true;
  try {{ await Promise.all(graphs.map(graph => Plotly.relayout(graph, {{'xaxis.range':[0,{max(elapsed[-1], 1)}], 'yaxis.autorange':true}}))); }}
  finally {{ synchronizing = false; }}
}};
for (const button of document.querySelectorAll('[data-svg]')) {{
  button.onclick = () => Plotly.downloadImage(button.dataset.svg, {{format:'svg',width:1600,height:800,filename:'run-{run_name}-' + button.dataset.svg}});
}}
if ({json.dumps(watch)}) {{
  const storageKey = 'report-view:' + location.pathname;
  try {{
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
    if (saved) {{
      document.getElementById('link-time').checked = saved.linked;
      Promise.all(graphs.map((graph, i) => Plotly.relayout(graph, saved.axes[i]))).then(() => {{
        window.scrollTo(saved.scroll[0], saved.scroll[1]);
      }});
    }}
  }} catch (error) {{ console.warn('Unable to restore report view', error); }}
  setTimeout(() => {{
    const axes = graphs.map(graph => {{
      const update = {{}};
      const x = graph.layout.xaxis;
      const fullEnd = graph.data[0].x.at(-1);
      if (!x.autorange && (x.range[0] !== 0 || x.range[1] !== Math.max(fullEnd, 1))) {{
        update['xaxis.range'] = x.range;
      }}
      if (!graph.layout.yaxis.autorange) update['yaxis.range'] = graph.layout.yaxis.range;
      return update;
    }});
    try {{
      sessionStorage.setItem(storageKey, JSON.stringify({{
        axes, linked: document.getElementById('link-time').checked, scroll: [scrollX, scrollY]
      }}));
    }} catch (error) {{ console.warn('Unable to preserve report view', error); }}
    location.reload();
  }}, 15000);
}}
</script></body></html>'''
    return body, len(rows), digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path, help='Saved run folder, e.g. runs/023')
    parser.add_argument('--watch', action='store_true',
                        help='Regenerate and refresh the report every 15 seconds; never control acquisition')
    args = parser.parse_args()
    while True:
        started = time.monotonic()
        body, count, digest = build_report(args.run, watch=args.watch)
        destination = args.run.resolve() / 'report.html'
        # The only written file is a derived report; input CSV/metadata are never changed.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                         prefix='.report-', suffix='.html', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
        temporary.replace(destination)
        print(f'{destination}\n{count} complete samples; CSV SHA-256 {digest}', flush=True)
        if not args.watch:
            break
        time.sleep(max(0, 15 - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
