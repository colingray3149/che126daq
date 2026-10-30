'use strict';
const $ = id => document.getElementById(id);
let points = [], cursor = 0, run = null, historical = null, seconds = 120;
let history = [], historyIndex = 0, draft = '', polling = false, busy = false;
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
const traces = ['TC1', 'TC2'].map((name, i) => ({name, x: [], y: [], mode: 'lines', connectgaps: false,
  line: {color: i ? '#ffba78' : '#6ed7ed', width: 2, dash: i ? 'dash' : 'solid'}}));
const layout = {
  paper_bgcolor: '#111820', plot_bgcolor: '#111820', font: {color: '#b9c8d6', size: 12},
  margin: {l: 64, r: 18, t: 35, b: 58}, hovermode: 'x unified', uirevision: 'hub',
  legend: {orientation: 'h', x: 0, y: 1.12},
  xaxis: {title: {text: 'Host elapsed time (s)'}, gridcolor: '#253340', zeroline: false},
  yaxis: {title: {text: 'Temperature (°C)'}, gridcolor: '#253340', zerolinecolor: '#415262'},
};
Plotly.newPlot('plot', traces, layout, {responsive: true, displaylogo: false, scrollZoom: true,
  modeBarButtonsToRemove: ['select2d', 'lasso2d']});
new ResizeObserver(() => Plotly.Plots.resize('plot')).observe($('plot'));
function draw() {
  const end = points.length ? points[points.length - 1][1] : 0;
  const shown = seconds === null ? points : points.filter(p => p[1] >= end - seconds);
  const x = shown.map(p => p[1]);
  Plotly.restyle('plot', {x: [x, x], y: [shown.map(p => p[2]), shown.map(p => p[3])]});
  $('sample-count').textContent = `${shown.length} retained points shown`;
}
function updateStatus(s) {
  $('recording').textContent = s.recording ? `● RECORDING ${s.run} · ${s.rows} rows` : '■ STOPPED · no samples being saved';
  $('connection').textContent = `${s.device} · ${s.age === null ? 'no complete samples yet' : `last sample ${s.age}s ago`} · epoch ${s.epoch} · malformed ${s.bad_rows}`;
  $('sensors').replaceChildren(...s.values.map((v, i) => {
    const span = document.createElement('span'); span.className = `tc${i+1}`;
    span.textContent = `TC${i+1} ${v === null ? 'FAULT / no reading' : v.toFixed(2) + ' °C'}`;
    return span;
  }));
  const warnings = [];
  if (!s.connected) warnings.push('DISCONNECTED — reconnect after checking USB.');
  else if (s.age === null || s.age > 3) warnings.push('Waiting / stale serial data.');
  if (s.values.includes(null)) warnings.push('Missing/NaN readings are gaps, not zeros.');
  if (s.zero_count) warnings.push('All-zero stream is NOT proof of valid temperatures or working probes.');
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
    if (!historical) {
      if (run !== status.run) { run = status.run; points = []; }
      points.push(...incoming);
      if (points.length > status.plot_points) points.splice(0, points.length - status.plot_points);
      if (incoming.length || !points.length) draw();
    }
    cursor = status.sequence;
    updateStatus(status);
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
    if (result.effect === 'history') { historical = result.name; points = result.points; draw(); }
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
log('DAQ hub · read-only serial, durable recording.\nFirst hardware connection auto-starts a saved run.\nType help for commands; ↑/↓ recalls history.\nProbe attachment and valid temperatures are not assumed.');
poll();
setInterval(poll, 500);
