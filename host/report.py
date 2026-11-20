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


def build_report(run_path, watch=False, figures=None):
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
    raw_channels = (metadata['feedback_channel'], metadata['rear_channel'])
    exp7_mixed = (metadata['experiment'] == 'exp7' and settings is not None
                  and all(key in settings for key in
                          ('external_channel', 'preheat_target_C', 'ramp_target_C', 'ramp_s')))
    exp8 = metadata['experiment'] == 'exp8'
    external_raw = metadata.get('external_channel')
    channels = [('EXTERNAL / CONTROL FEEDBACK' if exp8 else
                 'INTERNAL / FINAL FEEDBACK' if exp7_mixed else 'CONTROL FEEDBACK',
                 raw_channels[0], '#176bb6'),
                ('REAR', raw_channels[1], '#b65000')]
    if not exp8 and 'tc3_C' in rows[0]:
        external = external_raw or next(raw for raw in (1, 2, 3) if raw not in raw_channels)
        channels.append(('EXTERNAL / ENTRY + RAMP FEEDBACK' if exp7_mixed else 'DIAGNOSTIC',
                         external, '#43812b'))
    custom = [[html.escape(row['utc']), html.escape(row['flags'] or 'none'), row['epoch']]
              for row in rows]
    panels, summaries = [], []
    for i, (role, raw, color) in enumerate(channels):
        values = [temperature(row[f'tc{raw}_C']) for row in rows]
        finite = [value for value in values if value is not None]
        label = f'{role} (raw TC{raw})'
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
        if exp8 and i == 0:
            if settings:
                detail = (f'EXP8: EXTERNAL raw TC{settings["feedback_channel"]} continuous heat permission to '
                          f'{settings["preheat_target_C"]:g}°C → latched OFF/wait NEXT (early advance allowed) → '
                          f'{settings["ramp_s"]:g}s on/off reference ramp to {settings["ramp_target_C"]:g}°C → '
                          f'BOOST_FINAL at measured TC{settings["feedback_channel"]} ≥ {settings["ramp_target_C"]:g}°C '
                          f'with continuous permission. TC513 independently regulates its manual '
                          f'{settings["target_C"]:g}°C setpoint; that setpoint/PV is NOT measured by this DAQ. '
                          f'Operator enters NEXT when TC513 front-panel PV reaches {settings["target_C"]:g}°C '
                          f'to start HOLD_FINAL for {settings["hold_s"]:g}s from that confirmation; another NEXT '
                          f'is ACK/no-op and never resets the timer. Expiry commands permission OFF. External-only '
                          f'high cutoff {settings["feedback_cutoff_C"]:g}°C; rear protection remains independent. '
                          f'Relay events report commanded permission, not actual heater power/state.')
        elif i == 2:
            detail = ('External channel controls entry/ramp; internal channel controls boost/final hold. '
                      'All raw channels remain visible.'
                      if exp7_mixed else 'Diagnostic only; not a fallback control input.')
        elif settings:
            # Archived v5 settings retain their original logical-TC key names.
            feedback_cutoff = settings.get('feedback_cutoff_C', settings.get('tc1_cutoff_C'))
            rear_cutoff = settings.get('rear_cutoff_C', settings.get('tc2_cutoff_C'))
            rear_enabled = settings.get('rear_cutoff_enabled', settings.get('tc2_cutoff_enabled'))
            detail = (f'Feedback target {settings["target_C"]:g}°C · high cutoff {feedback_cutoff:g}°C'
                      if i == 0 else
                      (f'Rear cutoff {rear_cutoff:g}°C — applies to raw TC{raw}, not feedback'
                       if rear_enabled else 'Rear cutoff disabled'))
            if i == 0 and metadata['experiment'] in {'exp4', 'exp5', 'exp6', 'exp7'}:
                program = metadata['experiment'].upper()
                # Missing phase fields occur only in archived pre-clarification EXP7 settings.
                preheat = settings.get('preheat_target_C', 100.0)
                ramp_target = settings.get('ramp_target_C', 200.0)
                ramp_s = settings.get('ramp_s', 90.0)
                final = (f'; {settings["hold_s"]:g}s from measured target, then heat OFF'
                         if program in {'EXP5', 'EXP6', 'EXP7'} else '; indefinite final hold')
                if exp7_mixed:
                    detail = (f'EXP7: EXTERNAL raw TC{settings["external_channel"]} continuous heat to '
                              f'{preheat:g}°C → latched OFF/wait NEXT (early advance allowed) → '
                              f'{ramp_s:g}s reference ramp to {ramp_target:g}°C → INTERNAL raw TC'
                              f'{settings["feedback_channel"]} boost/hold {settings["target_C"]:g}°C'
                              f'{final}; internal high cutoff {feedback_cutoff:g}°C; rear protection '
                              f'remains independent; phase transitions are in saved events')
                else:
                    detail = (f'{program}: hold {preheat:g}°C → explicit NEXT → {ramp_s:g}s ramp to '
                              f'{ramp_target:g}°C → boost/hold {settings["target_C"]:g}°C · high cutoff '
                              f'{feedback_cutoff:g}°C{final}; phase transitions are in saved events')
        graph = fig.to_html(full_html=False, include_plotlyjs=(i == 0),
                            div_id=f'tc{i + 1}-graph', config={
                                'responsive': True, 'displaylogo': False, 'scrollZoom': True,
                                'toImageButtonOptions': {'format': 'png', 'width': 1600,
                                                        'height': 800, 'scale': 2,
                                                        'filename': f'run-{run_path.name}-tc{i + 1}'},
                                'modeBarButtonsToRemove': ['select2d', 'lasso2d']})
        panels.append(f'<section class="panel"><p>{html.escape(detail)}</p>{graph}</section>')
        if figures is not None:
            figures.append(fig)
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
    if exp8:
        source_summary = (f'EXP8 external control feedback = raw TC{raw_channels[0]}; '
                          f'rear = raw TC{raw_channels[1]}. Only these two channels are plotted; '
                          'raw TC3 remains in the downloaded CSV but its unused EXP8 panel is omitted. '
                          'D33 reports commanded heat permission, not actual heater power/state. ')
        if settings:
            source_summary += (f'TC513 manual setpoint {settings["target_C"]:g}°C and its front-panel PV '
                               'are external to the DAQ, not temperature measurements in this report. '
                               f'HOLD_FINAL is {settings["hold_s"]:g}s from operator NEXT confirmation at PV '
                               f'{settings["target_C"]:g}°C, not from a DAQ target crossing.')
        else:
            source_summary += 'TC513 setpoint/PV is external to the DAQ and is not plotted.'
    elif exp7_mixed:
        source_summary = (f'EXP7 phase feedback: external raw TC{settings["external_channel"]} during entry/ramp; '
                          f'internal raw TC{settings["feedback_channel"]} during boost/final hold; '
                          f'rear = raw TC{raw_channels[1]}. All recorded raw channels are shown.')
    else:
        source_summary = (f'Feedback = raw TC{raw_channels[0]}; rear = raw TC{raw_channels[1]}. '
                          'All recorded raw channels are shown.')
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
<p class="meta">Independent temperature axes. {source_summary}<br>
Manual preset {metadata['variac_voltage_V']:g} V (metadata, not measured); no voltage-based temperature scaling.</p>
{f'<p class="meta">Barrier: {html.escape(metadata["barrier"])}</p>' if metadata.get('barrier') else ''}
<div class="toolbar"><button id="reset">Fit full run</button>
<label><input type="checkbox" id="link-time" checked> Link time-axis zoom</label>
<button data-svg="tc1-graph">{'External feedback SVG' if exp8 else 'Heater SVG'}</button><button data-svg="tc2-graph">Rear SVG</button>
{f'<button data-svg="tc3-graph">Diagnostic SVG</button>' if len(channels) == 3 else ''}
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
const graphs = {json.dumps([f'tc{i + 1}-graph' for i in range(len(channels))])}.map(id => document.getElementById(id));
let synchronizing = false;
for (const graph of graphs) {{
  graph.on('plotly_relayout', async change => {{
    if (synchronizing || !document.getElementById('link-time').checked) return;
    const update = Object.fromEntries(Object.entries(change).filter(([key]) => key.startsWith('xaxis.range') || key === 'xaxis.autorange'));
    if (!Object.keys(update).length) return;
    synchronizing = true;
    try {{ await Promise.all(graphs.filter(other => other !== graph).map(other => Plotly.relayout(other, update))); }}
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
    parser.add_argument('--png', action='store_true',
                        help='Also write heater.png, rear.png and (when present) diagnostic.png (1400x700, needs kaleido)')
    args = parser.parse_args()
    while True:
        started = time.monotonic()
        figures = []
        body, count, digest = build_report(args.run, watch=args.watch, figures=figures)
        destination = args.run.resolve() / 'report.html'
        # The only written file is a derived report; input CSV/metadata are never changed.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                         prefix='.report-', suffix='.html', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
        temporary.replace(destination)
        print(f'{destination}\n{count} complete samples; CSV SHA-256 {digest}', flush=True)
        if args.png:
            for name, fig in zip(('heater.png', 'rear.png', 'diagnostic.png'), figures):
                fig.update_layout(height=None)
                fig.write_image(destination.parent / name, width=1400, height=700, scale=1)
        if not args.watch:
            break
        time.sleep(max(0, 15 - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
