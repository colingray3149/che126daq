'use strict';
const $ = id => document.getElementById(id);
let points = [], cursor = 0, run = null, historical = null, seconds = 120;
let history = [], historyIndex = 0, draft = '', polling = false, busy = false;
let liveMapping = {feedback: 2, rear: 1, external: 2}, historicalMapping = null;
let liveExperiment = 'exp8', historicalExperiment = null, phaseFeedback = null;
const inactiveBoot = controller => controller?.request_id === 0 || controller?.state === 'IDLE';
const displayedMapping = () => historical ? historicalMapping : liveMapping;
const remainingChannel = mapping => [1, 2, 3].find(raw => raw !== mapping.feedback && raw !== mapping.rear);
const externalChannel = mapping => mapping.external ?? remainingChannel(mapping);
const mappingFrom = data => ({feedback: data.display_feedback_channel, rear: data.display_rear_channel,
                              external: data.display_external_channel ?? null});
const viewingExp7 = () => (historical ? historicalExperiment : liveExperiment) === 'exp7';
const viewingExp8 = () => (historical ? historicalExperiment : liveExperiment) === 'exp8';
function phaseFeedbackChannel(controller) {
  if (!['exp7', 'exp8'].includes(controller?.program)) return null;
  if (Number.isInteger(controller.phase_feedback_channel)
      && controller.phase_feedback_channel >= 1 && controller.phase_feedback_channel <= 3) {
    return controller.phase_feedback_channel;
  }
  const settings = controller.settings;
  if (controller.program === 'exp8') return settings?.feedback_channel ?? null;
  if (['HEAT_100', 'HOLD_100', 'RAMP_200'].includes(controller.phase)
      && Number.isInteger(settings?.external_channel)) return settings.external_channel;
  if (['BOOST_FINAL', 'HOLD_FINAL'].includes(controller.phase)) return settings?.feedback_channel ?? null;
  return null;
}
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
  {id: 'heater-plot', title: 'heater-title', label: 'CONTROL FEEDBACK', role: 'feedback', color: '#6ed7ed'},
  {id: 'rear-plot', title: 'rear-title', label: 'REAR', role: 'rear', color: '#ffba78'},
  {id: 'external-plot', title: 'external-title', label: 'DIAGNOSTIC', role: 'external', color: '#a9d58b'}
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
  const mapping = displayedMapping();
  const exp7 = viewingExp7() && (!historical || mapping.external != null);
  const exp8 = viewingExp8();
  $('external-plot').closest('.plot-panel').hidden = exp8;
  panels.forEach(panel => {
    const raw = panel.role === 'external' ? externalChannel(mapping) : mapping[panel.role];
    const values = shown.map(p => p[raw + 1]);
    const latest = values.at(-1);
    const reading = latest === undefined ? 'no saved samples' : latest === null ? 'FAULT' : `${latest.toFixed(2)} °C`;
    const source = `raw TC${raw}`;
    let label = panel.label;
    if (exp8 && panel.role === 'feedback') label = 'EXTERNAL / CONTROL FEEDBACK';
    if (exp7 && panel.role === 'feedback') label = 'INTERNAL / FINAL FEEDBACK';
    if (exp7 && panel.role === 'external') {
      label = !historical && phaseFeedback === raw ? 'EXTERNAL / PHASE FEEDBACK'
        : !historical && phaseFeedback === mapping.feedback ? 'EXTERNAL / DIAGNOSTIC'
        : 'EXTERNAL / ENTRY + RAMP';
    }
    $(panel.title).textContent = `${label} · ${reading} · ${source}`;
    $(panel.id).dataset.rawChannel = raw;
    Plotly.restyle(panel.id, {x: [x], y: [values], name: [`${label} (${source})`]});
  });
  $('sample-count').textContent = `${shown.length} retained points shown`;
}
function updateStatus(s) {
  $('recording').textContent = s.recording ? `● RECORDING ${s.run} · ${s.rows} rows` : '■ STOPPED · no samples being saved';
  $('connection').textContent = `${s.device} · ${s.age === null ? 'no complete samples yet' : `last sample ${s.age}s ago`} · epoch ${s.epoch} · malformed ${s.bad_rows}`;
  liveMapping = mappingFrom(s);
  liveExperiment = s.experiment || 'exp2';
  const c = s.controller;
  if (['exp7', 'exp8'].includes(c?.program)) liveExperiment = c.program;
  if (!c || inactiveBoot(c)) {
    liveExperiment = 'exp8';
    liveMapping = {feedback: 2, rear: 1, external: 2};
  }
  phaseFeedback = phaseFeedbackChannel(c);
  const exp7 = liveExperiment === 'exp7';
  const exp8 = liveExperiment === 'exp8';
  const external = externalChannel(liveMapping);
  const roles = exp8
    ? [['external control feedback', liveMapping.feedback], ['rear', liveMapping.rear]]
    : exp7
      ? [['internal final', liveMapping.feedback], ['rear', liveMapping.rear],
         ['external entry/ramp', external]]
      : [['feedback', liveMapping.feedback], ['rear', liveMapping.rear],
         ['diagnostic', external]];
  $('sensors').replaceChildren(...roles.map(([role, raw], i) => {
    const v = s.values[raw - 1];
    const span = document.createElement('span'); span.className = `tc${i+1}`;
    const activeSource = !historical && raw === phaseFeedback ? ' · PHASE FEEDBACK' : '';
    span.textContent = `${role} (raw TC${raw})${activeSource} ${v == null ? 'FAULT / no reading' : v.toFixed(2) + ' °C'}`;
    return span;
  }));
  if (c) {
    const heat = c.heater_on === true ? 'ON' : c.heater_on === false ? 'OFF' : 'UNKNOWN';
    const cfg = c.settings;
    const staged = ['exp4', 'exp5', 'exp6', 'exp7'].includes(c.program);
    const exp8Control = c.program === 'exp8';
    const setpoint = staged ? c.setpoint_C : cfg?.target_C;
    const hold = inactiveBoot(c) ? 'no experiment timer active' : cfg && Number.isFinite(c.hold_s)
      ? (exp8Control
         ? (c.phase === 'HOLD_FINAL'
            ? `${Math.floor(c.hold_s)} / ${cfg.hold_s} s since operator NEXT confirmation`
            : `${cfg.hold_s}s final hold starts on NEXT in BOOST_FINAL`)
         : ['exp5', 'exp6', 'exp7'].includes(c.program) && c.phase === 'HOLD_FINAL'
           ? `${Math.floor(c.hold_s)} / ${cfg.hold_s} s since measured target`
           : cfg.hold_s > 0 ? `${Math.floor(c.hold_s)} / ${cfg.hold_s} s in band` : 'timed hold disabled')
      : 'hold unavailable';
    $('control-settings').textContent = inactiveBoot(c)
      ? 'No experiment applied · inactive boot defaults; selected file settings are not active and apply only on START.'
      : !cfg ? 'Applied settings unavailable'
      : exp8Control
        ? `Applied EXP8 control: EXTERNAL raw TC${cfg.feedback_channel} feedback / REAR raw TC${cfg.rear_channel} · continuous heat permission to ${cfg.preheat_target_C}°C → latched OFF/wait NEXT (early advance allowed) → ${cfg.ramp_s}s on/off reference ramp to ${cfg.ramp_target_C}°C → BOOST_FINAL at measured TC${cfg.feedback_channel} ≥ ${cfg.ramp_target_C}°C · TC513 manual setpoint ${cfg.target_C}°C (metadata, NOT a DAQ measurement; read PV on TC513) · NEXT at PV ${cfg.target_C}°C starts ${cfg.hold_s}s hold · external-only high cutoff ${cfg.feedback_cutoff_C}°C · rear ${cfg.rear_cutoff_enabled ? 'trip ' + cfg.rear_cutoff_C + '°C' : 'cutoff disabled'} · OFF dwell ${cfg.min_off_s}s`
        : c.program === 'exp7'
          ? `Applied control: EXTERNAL raw TC${cfg.external_channel ?? remainingChannel(cfg)} entry/ramp / INTERNAL raw TC${cfg.feedback_channel} boost/final / REAR raw TC${cfg.rear_channel} · preheat ${cfg.preheat_target_C}°C → ramp ${cfg.ramp_target_C}°C over ${cfg.ramp_s}s · final ${cfg.target_C}°C for ${cfg.hold_s}s · internal high cutoff ${cfg.feedback_cutoff_C}°C · rear ${cfg.rear_cutoff_enabled ? 'trip ' + cfg.rear_cutoff_C + '°C' : 'cutoff disabled'} · OFF dwell ${cfg.min_off_s}s`
          : `Applied control: raw TC${cfg.feedback_channel} feedback / raw TC${cfg.rear_channel} rear · ${staged ? 'phase setpoint' : 'target'} ${setpoint}°C${staged ? ' · final target ' + cfg.target_C + '°C' : ''} · feedback trip ${cfg.feedback_cutoff_C}°C · rear ${cfg.rear_cutoff_enabled ? 'trip ' + cfg.rear_cutoff_C + '°C' : 'cutoff disabled'} · OFF dwell ${cfg.min_off_s}s`;
    if (!inactiveBoot(c) && s.run && Number.isFinite(s.variac_voltage_V)) {
      $('control-settings').textContent += ` · manual preset ${s.variac_voltage_V}V RMS (not measured)`;
    }
    const heatLabel = exp8Control ? 'commanded heat permission (NOT actual heater state)' : 'commanded heat';
    $('controller').textContent = `${inactiveBoot(c) ? 'Controller' : (c.program || s.experiment || 'exp2').toUpperCase()} ${c.state || 'UNKNOWN'}${c.pending ? ' · command pending' : ''} · ${heatLabel} ${heat} · ${hold}${c.reason ? ' · ' + c.reason : ''}${inactiveBoot(c) ? ' · no experiment applied; selected settings are not active' : ''}`;
    if (exp8Control) {
      $('controller').textContent += ` · ${c.phase}`;
      if (phaseFeedback) $('controller').textContent += ` · phase feedback EXTERNAL raw TC${phaseFeedback}`;
      if (c.phase === 'RAMP_200') $('controller').textContent += ` · on/off reference slope ${Number(c.slope_C_per_s).toFixed(2)}°C/s`;
      if (['HEAT_100', 'HOLD_100'].includes(c.phase) && c.active) $('controller').textContent += ' · NEXT advances to the reference ramp early';
      if (c.phase === 'BOOST_FINAL' && c.active) $('controller').textContent += ` · when TC513 front-panel PV reaches ${cfg?.target_C ?? 650}°C, enter NEXT to start the ${cfg?.hold_s ?? 90}s hold`;
      if (c.phase === 'HOLD_FINAL' && c.active) $('controller').textContent += ' · timer started by operator NEXT; another NEXT is ACK/no-op and never resets it';
    } else if (staged) {
      $('controller').textContent += ` · ${c.phase} · slope ${Number(c.slope_C_per_s).toFixed(2)}°C/s`;
      if (c.program === 'exp7' && phaseFeedback) {
        const role = phaseFeedback === cfg?.feedback_channel ? 'INTERNAL' : 'EXTERNAL';
        $('controller').textContent += ` · phase feedback ${role} raw TC${phaseFeedback}`;
      }
      if (c.phase === 'HOLD_100' && c.active) $('controller').textContent += ' · waiting for explicit next';
    }
    $('controller').classList.toggle('fault', ['TRIPPED', 'UNKNOWN'].includes(c.state) || c.heater_on === null);
    $('heater-settings').textContent = historical ? 'Saved temperatures; controller status above is LIVE.'
      : inactiveBoot(c) ? 'No experiment applied · inactive boot defaults; selected settings are not active.'
      : cfg ? (exp8Control
        ? `EXTERNAL raw TC${cfg.feedback_channel}: all-stage monitoring; lower-stage control · external-only high cutoff ${cfg.feedback_cutoff_C}°C · TC513 manual setpoint ${cfg.target_C}°C is NOT a DAQ measurement · D33 is heat permission, not actual heater state`
        : c.program === 'exp7'
          ? `INTERNAL raw TC${cfg.feedback_channel}: boost/final feedback and all-stage high cutoff ${cfg.feedback_cutoff_C}°C · final ${cfg.target_C}°C / ${cfg.hold_s}s`
          : `${staged ? 'Phase setpoint' : 'Target'} ${setpoint}°C · feedback cutoff ${cfg.feedback_cutoff_C}°C`) : 'Control settings unavailable';
    $('rear-settings').textContent = historical ? 'Saved temperatures; independent temperature scale.'
      : inactiveBoot(c) ? 'No experiment applied · inactive boot defaults; selected settings are not active.'
      : cfg ? (cfg.rear_cutoff_enabled ? `Rear cutoff ${cfg.rear_cutoff_C}°C — independent protection` : 'Rear cutoff DISABLED') : 'Control settings unavailable';
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
  const controlMapping = c?.settings
    ? {feedback: c.settings.feedback_channel, rear: c.settings.rear_channel,
       external: c.settings.external_channel ?? null} : liveMapping;
  const controlExternal = externalChannel(controlMapping);
  if (c?.program === 'exp8') {
    if (s.values[controlMapping.feedback - 1] == null) warnings.push(`External raw TC${controlMapping.feedback} control feedback/high-cutoff missing: runtime shutdown; no fallback.`);
  } else if (c?.program === 'exp7') {
    if (s.values[controlMapping.feedback - 1] == null) warnings.push(`Internal raw TC${controlMapping.feedback} high-cutoff/final feedback missing: runtime shutdown; no fallback.`);
    if (phaseFeedback === controlExternal && s.values[controlExternal - 1] == null) warnings.push(`External raw TC${controlExternal} phase feedback missing: runtime shutdown; no fallback.`);
  } else if (s.values[controlMapping.feedback - 1] == null) warnings.push('Control feedback missing: runtime shutdown; no fallback to another probe.');
  if (c?.settings?.rear_cutoff_enabled === false) warnings.push('Rear cutoff disabled in applied settings.');
  else if (s.values[controlMapping.rear - 1] == null) warnings.push(c?.rear_required
    ? `Required rear probe missing: ${(c.program || 'staged').toUpperCase()} commands heat OFF.`
    : `Optional rear probe missing: ${c?.settings?.rear_cutoff_C ?? 'configured'}°C protection unavailable.`);
  if (liveMapping.feedback !== controlMapping.feedback || liveMapping.rear !== controlMapping.rear
      || (['exp7', 'exp8'].includes(c?.program) && externalChannel(liveMapping) !== controlExternal)) warnings.push('Display and applied control source mappings differ; selected config applies on START.');
  if (['exp4', 'exp5', 'exp6', 'exp7', 'exp8'].includes(c?.program)) warnings.push(`${c.program.toUpperCase()} high-temperature program: software thresholds do not establish hardware suitability.`);
  if (c?.program === 'exp8') warnings.push('TC513 setpoint and PV are external to the DAQ; heat permission is not actual heater power/state.');
  if (c?.protocol !== 'exp2-v6') warnings.push('Three-channel control requires v6 host and firmware; this board is not reporting v6.');
  const mapping = displayedMapping();
  const displayExp7 = viewingExp7() && (!historical || mapping.external != null);
  const displayExp8 = viewingExp8();
  const displayExternal = externalChannel(mapping);
  $('channel-mapping').textContent = displayExp8
    ? `Independent °C scales · external control feedback ← raw TC${mapping.feedback}; rear ← raw TC${mapping.rear} · TC513 setpoint/PV is not measured or plotted by the DAQ · raw TC3 remains in CSV but its unused EXP8 panel is hidden; no voltage scaling.`
    : displayExp7
      ? `Independent °C scales · internal/final ← raw TC${mapping.feedback}; external/entry+ramp ← raw TC${displayExternal}; rear ← raw TC${mapping.rear}${!historical && phaseFeedback ? ` · current phase feedback ← raw TC${phaseFeedback}` : ''} · all raw channels shown; raw CSV unchanged.`
      : `Independent °C scales · feedback ← raw TC${mapping.feedback}; rear ← raw TC${mapping.rear}; diagnostic ← raw TC${displayExternal} · raw CSV unchanged; no voltage scaling.`;
  $('external-settings').textContent = displayExp8 ? ''
    : !historical && inactiveBoot(c) ? 'No experiment applied · inactive boot defaults; selected settings are not active.'
    : displayExp7
      ? (historical ? `EXTERNAL raw TC${displayExternal}: entry/ramp controller; INTERNAL raw TC${mapping.feedback} controls boost/final hold.`
         : phaseFeedback === displayExternal ? `EXTERNAL phase feedback: ${c?.settings?.preheat_target_C ?? 100}°C entry/latch and ${c?.settings?.ramp_s ?? 90}s ramp to ${c?.settings?.ramp_target_C ?? 200}°C; required source, never a fallback.`
         : phaseFeedback === mapping.feedback ? 'EXTERNAL diagnostic after boost switch; raw channel remains visible. INTERNAL is now phase feedback.'
         : 'EXTERNAL controls entry/ramp; INTERNAL controls boost/final hold. No source fallback.')
      : 'Diagnostic only; never substitutes for failed feedback. Missing historical TC3 remains a gap.';
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
      historicalExperiment = result.experiment;
      historicalMapping = mappingFrom(result);
      points = result.points; draw();
    }
    if (result.effect === 'live') { historical = null; historicalExperiment = null; points = []; cursor = 0; run = null; }
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
log('DAQ hub · durable three-channel temperature recording.\nNo automatic heating. With --wait-for-start, no recording until explicit START.\nEXP8: EXTERNAL TC2 is the only control feedback; REAR TC1 protects; unused TC3 is hidden here but retained in CSV. TC513 independently regulates its manual 650°C setpoint; its setpoint/PV is NOT measured by the DAQ. D33 is heat permission, not actual heater state.\nstart exp8 loads experiment8.toml; v6 firmware required. TC2 permission heats to 100°C, latches OFF, then NEXT starts a 90s on/off reference ramp to 200°C; early NEXT is allowed. Measured TC2 ≥ 200°C enters BOOST_FINAL with continuous permission.\nEXP8 BOOST_FINAL: when the TC513 front-panel PV reaches 650°C, enter NEXT to start HOLD_FINAL. The 90s timer starts at that operator confirmation; NEXT during HOLD_FINAL is ACK/no-op and never resets it. Expiry commands permission OFF.\nEXP7 remains distinct: EXTERNAL TC2 entry/ramp, INTERNAL TC3 boost/650°C/90s final hold, REAR TC1 protection. start exp7 loads experiment7.toml.\nEXP7 NEXT during HEAT_100/HOLD_100 starts the ramp early; other valid NEXT commands are ACK/no-op. NEXT never bypasses a trip or starts/re-arms control.\nstop exp7 / stop exp8: command heat or heat permission OFF, retain cooldown logging. Commands remain available in every state; the controller validates each command.\nEXP2–6 retain their original sensor selections. config: show edited and applied source mappings/settings.\nNC wiring cannot fail OFF on Arduino power loss.\nType help for commands; ↑/↓ recalls history.');
async function initialize() {
  await poll();
  setInterval(poll, 500);
}
initialize();
