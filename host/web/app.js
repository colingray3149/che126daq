'use strict';
const $ = id => document.getElementById(id);
let points = [], cursor = 0, run = null, historical = null, seconds = 120;
let history = [], historyIndex = 0, draft = '', polling = false, busy = false;
let liveSwapped = false, historicalSwapped = false, runMappings = {};
const displayedSwapped = () => historical ? historicalSwapped : liveSwapped;
try { history = JSON.parse(localStorage.getItem('daq-history') || '[]'); } catch (_) {}
historyIndex = history.length;
function log(text, error = false, prompt = false) {
  const row = document.createElement('div');
  row.className = 'entry' + (error ? ' error' : '') + (prompt ? ' prompt' : '');
  row.textContent = text;
  $('console').append(row);
  while ($('console').children.length > 250) $('console').firstChild.remove();
  $('console').scrollTop = $('console').scrollHeight;
}
const panels = [
  {id: 'heater-plot', title: 'heater-title', label: 'TC1 · HEATER', color: '#6ed7ed'},
  {id: 'rear-plot', title: 'rear-title', label: 'TC2 · REAR', color: '#ffba78'}
];
for (const panel of panels) {
  Plotly.newPlot(panel.id, [{
    name: panel.label, x: [], y: [], mode: 'lines', connectgaps: false,
    line: {color: panel.color, width: 2},
    hovertemplate: '%{x:.1f} s<br>%{y:.2f} °C<extra>%{fullData.name}</extra>'
  }], {
    paper_bgcolor: '#111820', plot_bgcolor: '#111820',
    font: {color: '#b9c8d6', size: 12},
    margin: {l: 58, r: 18, t: 12, b: 42}, showlegend: false, uirevision: 'hub',
    xaxis: {title: {text: 'Host elapsed time (s)'}, gridcolor: '#253340', zeroline: false},
    yaxis: {title: {text: 'Temperature (°C)'}, gridcolor: '#253340', zeroline: false}
  }, {responsive: true, displaylogo: false, scrollZoom: true,
    modeBarButtonsToRemove: ['select2d', 'lasso2d']});
  new ResizeObserver(() => Plotly.Plots.resize(panel.id)).observe($(panel.id));
}
function draw() {
  const end = points.length ? points[points.length - 1][1] : 0;
  const shown = seconds === null ? points : points.filter(p => p[1] >= end - seconds);
  const x = shown.map(p => p[1]);
  const swapped = displayedSwapped();
  panels.forEach((panel, i) => {
    const raw = swapped ? 2 - i : i + 1;
    const values = shown.map(p => p[raw + 1]);
    const latest = values.at(-1);
    const reading = latest === undefined ? 'no saved samples' : latest === null ? 'FAULT' : `${latest.toFixed(2)} °C`;
    const source = `raw TC${raw}`;
    $(panel.title).textContent = `${panel.label} · ${reading} · ${source}`;
    $(panel.id).dataset.rawChannel = raw;
    Plotly.restyle(panel.id, {x: [x], y: [values], name: [`${panel.label} (${source})`]});
  });
  $('sample-count').textContent = `${shown.length} retained points shown`;
}
function updateStatus(s) {
  $('recording').textContent = s.recording ? `● RECORDING ${s.run} · ${s.rows} rows` : '■ STOPPED · no samples being saved';
  $('connection').textContent = `${s.device} · ${s.age === null ? 'no complete samples yet' : `last sample ${s.age}s ago`} · epoch ${s.epoch} · malformed ${s.bad_rows}`;
  liveSwapped = s.display_swapped ?? runMappings[s.run]?.swap_inputs ?? false;
  const logicalValues = liveSwapped ? [s.values[1], s.values[0]] : s.values;
  $('sensors').replaceChildren(...logicalValues.map((v, i) => {
    const span = document.createElement('span'); span.className = `tc${i+1}`;
    span.textContent = `TC${i+1} (${i ? 'rear' : 'heater'}; raw TC${liveSwapped ? 2-i : i+1}) ${v === null ? 'FAULT / no reading' : v.toFixed(2) + ' °C'}`;
    return span;
  }));
  const c = s.controller;
  if (c) {
    const heat = c.heater_on === true ? 'ON' : c.heater_on === false ? 'OFF' : 'UNKNOWN';
    const cfg = c.settings;
    const hold = cfg && Number.isFinite(c.hold_s)
      ? (cfg.hold_s > 0 ? `${Math.floor(c.hold_s)} / ${cfg.hold_s} s in band` : 'timed hold disabled')
      : 'hold unavailable';
    $('control-settings').textContent = cfg
      ? `${c.request_id === 0 ? 'Inactive boot defaults — NOT the selected experiment settings' : 'Applied control'}: ${cfg.swap_inputs ? 'raw TC2 heater / raw TC1 rear' : 'raw TC1 feedback / raw TC2 cutoff'} · target ${cfg.target_C}°C · ON ≤${Number((cfg.target_C - cfg.hysteresis_C).toFixed(3))}°C · feedback trip ${cfg.tc1_cutoff_C}°C · other probe ${cfg.tc2_cutoff_enabled ? 'trip ' + cfg.tc2_cutoff_C + '°C' : 'cutoff disabled'} · OFF dwell ${cfg.min_off_s}s`
      : 'Applied settings unavailable';
    if (s.run && Number.isFinite(s.variac_voltage_V)) {
      $('control-settings').textContent += ` · manual preset ${s.variac_voltage_V}V RMS (not measured)`;
    }
    $('controller').textContent = `${c.request_id === 0 ? 'Controller' : (s.experiment || 'exp2').toUpperCase()} ${c.state || 'UNKNOWN'}${c.pending ? ' · command pending' : ''} · commanded heat ${heat} · ${hold}${c.reason ? ' · ' + c.reason : ''}${c.request_id === 0 ? ' · boot defaults; selected file applies on START' : ''}`;
    $('controller').classList.toggle('fault', ['TRIPPED', 'UNKNOWN'].includes(c.state) || c.heater_on === null);
    $('heater-settings').textContent = historical ? 'Saved temperatures; controller status above is LIVE.'
      : cfg ? `Target ${cfg.target_C}°C · heater cutoff ${cfg.tc1_cutoff_C}°C` : 'Control settings unavailable';
    $('rear-settings').textContent = historical ? 'Saved temperatures; independent temperature scale.'
      : cfg ? (cfg.tc2_cutoff_enabled ? `Rear cutoff ${cfg.tc2_cutoff_C}°C — not the heater cutoff` : 'Rear cutoff DISABLED') : 'Control settings unavailable';
  } else {
    $('controller').textContent = 'EXP2 unavailable — compatible firmware required; no automatic heating.';
    $('controller').classList.remove('fault');
    $('control-settings').textContent = '';
  }
  if (!c) {
    $('heater-settings').textContent = 'Control settings unavailable';
    $('rear-settings').textContent = 'Control settings unavailable';
  }
  const warnings = [];
  if (!s.connected) warnings.push('DISCONNECTED — reconnect after checking USB.');
  else if (s.age === null || s.age > 3) warnings.push('Waiting / stale serial data.');
  const controlSwapped = c?.settings?.swap_inputs ?? false;
  if (s.values[controlSwapped ? 1 : 0] === null) warnings.push('Control feedback missing: runtime shutdown; START itself is not blocked.');
  if (c?.settings?.tc2_cutoff_enabled === false) warnings.push('Rear cutoff disabled in applied settings.');
  else if (s.values[controlSwapped ? 0 : 1] === null) warnings.push(`Optional cutoff probe missing: ${c?.settings?.tc2_cutoff_C ?? 'configured'}°C protection unavailable.`);
  if (liveSwapped !== controlSwapped) warnings.push('Display follows the reported probe placement; START must apply the matching input mapping. Use EXP3 for the reversed probes.');
  $('channel-mapping').textContent = `Independent °C scales · ${displayedSwapped() ? 'swapped display: TC1 ← raw TC2; TC2 ← raw TC1' : 'display follows raw channel order'} · raw CSV unchanged; no voltage scaling.`;
  if (s.zero_count) warnings.push('All-zero stream is NOT proof of valid temperatures or working probes.');
  warnings.push('NC wiring: Arduino power loss can turn heat ON. Independent cutoff required.');
  if (historical) warnings.push('Sensor/status values above are LIVE; graph below is HISTORICAL.');
  $('warning').textContent = warnings.join(' ');
  $('view-label').textContent = historical ? `HISTORICAL · run ${historical}` : `LIVE · run ${s.run || '—'}${s.recording ? '' : ' · stopped'}`;
  $('view-label').className = historical ? 'historical' : '';
  $('storage').textContent = s.path ? `Saved location: ${s.path}` : 'No saved run yet';
  const event = s.events.at(-1);
  $('event').textContent = event ? `${event.utc} · ${event.text}` : '';
}
async function poll() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch(`/api/state?since=${cursor}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const {status, points: incoming} = await response.json();
    updateStatus(status);
    if (!historical) {
      if (run !== status.run) { run = status.run; points = []; }
      points.push(...incoming);
      if (points.length > status.plot_points) points.splice(0, points.length - status.plot_points);
      draw();
    }
    cursor = status.sequence;
  } catch (error) {
    $('connection').textContent = `Hub unreachable: ${error.message}. Browser closure does not stop acquisition; check server.`;
  } finally { polling = false; }
}
async function command(text) {
  log('› ' + text, false, true);
  try {
    const response = await fetch('/api/command', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({command: text})});
    const result = await response.json();
    if (result.effect === 'clear') { $('console').replaceChildren(); points = []; draw(); }
    if (result.effect === 'history') {
      historical = result.name;
      historicalSwapped = result.display_swapped ?? runMappings[result.name]?.swap_inputs ?? false;
      points = result.points; draw();
    }
    if (result.effect === 'live') { historical = null; points = []; cursor = 0; run = null; }
    if (result.effect === 'window') { seconds = result.seconds; draw(); }
    log(result.message, result.error);
    await poll();
  } catch (error) { log(`Command failed: ${error.message}`, true); }
}
$('command-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  const text = $('command').value.trim();
  if (!text) return;
  busy = true;
  $('command').value = '';
  history.push(text); history = history.slice(-100); historyIndex = history.length; draft = '';
  try { localStorage.setItem('daq-history', JSON.stringify(history)); } catch (_) {}
  try { await command(text); } finally { busy = false; }
});
$('command').addEventListener('keydown', event => {
  if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
  event.preventDefault();
  if (historyIndex === history.length) draft = $('command').value;
  historyIndex = Math.max(0, Math.min(history.length, historyIndex + (event.key === 'ArrowUp' ? -1 : 1)));
  $('command').value = historyIndex === history.length ? draft : history[historyIndex];
});
log('DAQ hub · durable temperature recording.\nNo automatic heating. With --wait-for-start, no recording until explicit START.\nSplit plots use independent °C scales; raw CSV is unchanged.\nstart exp2 / start exp3 load their respective saved profiles.\nstop exp2 / stop exp3: cut heat, keep cooldown logging.\nconfig: show edited and applied settings.\nNC wiring cannot fail OFF on Arduino power loss.\nType help for commands; ↑/↓ recalls history.');
async function initialize() {
  try {
    const response = await fetch('/static/run-mappings.json', {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    runMappings = await response.json();
  } catch (error) { log(`Saved channel corrections unavailable: ${error.message}`, true); }
  await poll();
  setInterval(poll, 500);
}
initialize();
