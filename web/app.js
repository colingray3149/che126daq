"use strict";
// CHE 126 DAQ page. Talks to daq.py: /api/stream (live), /api/* (commands, runs, settings).

const $ = (s, root) => (root || document).querySelector(s);
const $$ = (s, root) => Array.from((root || document).querySelectorAll(s));
const COLORS = ["#e8590c", "#1c7ed6", "#2f9e44"];
const COMPARE_COLORS = ["#e8590c", "#1c7ed6", "#2f9e44", "#ae3ec9", "#f59f00", "#0c8599", "#c2255c", "#495057"];

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "style") e.style.cssText = v;
    else if (v === true) e.setAttribute(k, "");
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(kid));
  return e;
}

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok) throw new Error((data && data.error) || r.statusText);
  return data;
}

function fmtT(v, d = 1) { return v === null || v === undefined || !isFinite(v) ? "—" : v.toFixed(d); }
function fmtDur(s) {
  if (s === null || s === undefined || !isFinite(s)) return "—";
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0");
}
function toast(msg, bad) {
  const b = $("#banner");
  b.className = "banner" + (bad ? "" : " warn");
  b.textContent = msg;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { if (!S || !S.board.tripped) b.classList.add("hidden"); }, 5000);
}
async function act(fn) {
  try { return await fn(); } catch (e) { toast(e.message, true); }
}

let S = null; // last server state
const live = { origin: 0, t: [], tc: [[], [], []], heat: [], sp: [], sptc: [], runId: null };
let liveCharts = [];
let windowMin = Number(localStorage.getItem("windowMin") || 30);
let programs = [];
let editing = null;

// ------------------------------------------------------------------ tabs
function showTab(name) {
  $$("nav button").forEach(b => b.classList.toggle("on", b.dataset.tab === name));
  $$(".tab").forEach(t => t.classList.toggle("on", t.id === "tab-" + name));
  localStorage.setItem("tab", name);
  if (name === "runs") loadRuns();
  if (name === "settings") renderSettings();
  if (name === "findings") loadFindings();
  if (name === "program") renderProgramList();
  setTimeout(resizeCharts, 0);
}
$$("nav button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ------------------------------------------------------------------ charts
function heatBandsPlugin(getHeat) {
  return {
    hooks: {
      drawClear: [u => {
        const heat = getHeat();
        const xs = u.data[0];
        if (!heat || !xs.length) return;
        const { ctx } = u;
        const top = u.bbox.top, h = u.bbox.height;
        ctx.save();
        ctx.fillStyle = "rgba(255, 146, 43, 0.15)";
        let start = null;
        for (let i = 0; i <= xs.length; i++) {
          const on = i < xs.length && heat[i];
          if (on && start === null) start = xs[i];
          if (!on && start !== null) {
            const end = i < xs.length ? xs[i] : xs[xs.length - 1];
            const x0 = u.valToPos(start, "x", true), x1 = u.valToPos(end, "x", true);
            const l = Math.max(x0, u.bbox.left), r = Math.min(x1, u.bbox.left + u.bbox.width);
            if (r > l) ctx.fillRect(l, top, Math.max(1, r - l), h);
            start = null;
          }
        }
        ctx.restore();
      }],
    },
  };
}

function fmtMin(v) {
  if (v === null || v === undefined) return "";
  const neg = v < 0;
  const t = Math.round(Math.abs(v) * 60);
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return (neg ? "−" : "") + (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(sec).padStart(2, "0");
}

function minSpan(lo, hi) {
  if (lo === null || hi === null) return [0, 50];
  const span = hi - lo;
  if (span < 10) { const mid = (lo + hi) / 2; return [mid - 5, mid + 5]; }
  const pad = span * 0.05;
  return [lo - pad, hi + pad];
}

function makeChart(host, title, color, getHeat, extraSeries, opts2) {
  opts2 = opts2 || {};
  const box = el("div", { class: "chart", style: "--c:" + color },
    el("h3", {}, el("i"), title, el("span", { class: "now" })));
  const plot = el("div", { class: "plot" });
  box.append(plot);
  host.append(box);
  const series = [
    { label: "time", value: (u, v) => v === null ? "—" : fmtMin(v) },
    ...(extraSeries || [
      { label: "°C", stroke: color, width: 2, spanGaps: false, points: { show: false }, value: (u, v) => v === null ? "—" : v.toFixed(1) },
      { label: "setpoint", stroke: color, dash: [6, 5], width: 1.5, points: { show: false }, value: (u, v) => v === null ? "—" : v.toFixed(1) },
      { label: "predicted", stroke: "#adb5bd", dash: [3, 4], width: 1.5, points: { show: false }, value: (u, v) => v === null ? "—" : v.toFixed(1) },
    ]),
  ];
  series.slice(1).forEach(x => { if (!x.points) x.points = { show: false }; });
  const opts = {
    width: 400, height: 150,
    series,
    scales: { x: { time: false }, y: { range: (u, lo, hi) => minSpan(lo, hi) } },
    axes: [
      { label: opts2.xLabel || "time since start (m:ss)", size: 34, labelSize: 14, grid: { stroke: "#eef0f3" },
        incrs: [1 / 60, 5 / 60, 10 / 60, 15 / 60, 30 / 60, 1, 2, 5, 10, 15, 30, 60, 120],
        values: (u, vals) => vals.map(v => fmtMin(v)) },
      { label: "°C", size: 52, labelSize: 14, grid: { stroke: "#eef0f3" } },
    ],
    cursor: { drag: { x: true, y: false }, sync: { key: "sync-" + host.id } },
    legend: { show: !!opts2.legend, live: true },
    plugins: getHeat ? [heatBandsPlugin(getHeat)] : [],
  };
  const u = new uPlot(opts, [[], ...series.slice(1).map(() => [])], plot);
  u._box = box;
  return u;
}

function sizeChart(u) {
  const box = u._box;
  const w = box.clientWidth - 12;
  const legend = box.querySelector(".u-legend");
  const h = box.clientHeight - 24 - (legend ? legend.offsetHeight : 0) - 6;
  if (w > 50 && h > 60) u.setSize({ width: w, height: h });
}
function resizeCharts() { liveCharts.forEach(sizeChart); runCharts.forEach(sizeChart); if (pvChart) sizeChart(pvChart); }
window.addEventListener("resize", () => { clearTimeout(resizeCharts.t); resizeCharts.t = setTimeout(resizeCharts, 100); });

function interp(ts, vs, t) {
  if (!ts.length || t < ts[0] || t > ts[ts.length - 1]) return null;
  let lo = 0, hi = ts.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (ts[m] <= t) lo = m; else hi = m; }
  const f = ts[hi] === ts[lo] ? 0 : (t - ts[lo]) / (ts[hi] - ts[lo]);
  return vs[lo] + (vs[hi] - vs[lo]) * f;
}

function visibleTcs() {
  if (!S) return [0, 1];
  return S.settings.tcs.map((t, i) => (t.show ? i : -1)).filter(i => i >= 0);
}

function buildLiveCharts() {
  const host = $("#live-charts");
  host.innerHTML = "";
  liveCharts = visibleTcs().map(i => {
    const t = S.settings.tcs[i];
    const u = makeChart(host, "TC" + (i + 1) + " · " + t.name, COLORS[i], () => live._heatView);
    u._tc = i;
    return u;
  });
  liveCharts.sig = JSON.stringify(S.settings.tcs);
  setTimeout(() => { resizeCharts(); drawLive(true); }, 0);
}

let drawPending = false;
function drawLive(force) {
  if (drawPending && !force) return;
  drawPending = true;
  requestAnimationFrame(() => {
    drawPending = false;
    if (!liveCharts.length) return;
    const n = live.t.length;
    let i0 = 0;
    if (windowMin > 0 && n) {
      const cutoff = live.t[n - 1] - windowMin * 60;
      while (i0 < n && live.t[i0] < cutoff) i0++;
    }
    let xs = live.t.slice(i0).map(t => (t - live.origin) / 60);
    live._heatView = live.heat.slice(i0);
    const pred = live.runId && live.predicted ? live.predicted : null;
    let px = [], extra = 0;
    if (pred) {
      // Predicted curve: interpolate onto live times, then extend into the future.
      const lastX = xs.length ? xs[xs.length - 1] : 0;
      px = pred.t.map(t => t / 60).filter(x => x > lastX);
      extra = px.length;
    }
    const xsAll = xs.concat(px);
    for (const u of liveCharts) {
      const i = u._tc;
      const pad = new Array(extra).fill(null);
      const ys = live.tc[i].slice(i0).concat(pad);
      const sp = live.sp.slice(i0).map((v, k) => (live.sptc[i0 + k] === i + 1 ? v : null)).concat(pad);
      let pr = new Array(xsAll.length).fill(null);
      if (pred && (i === 0 || i === 1)) pr = xsAll.map(x => interp(pred.t, pred["tc" + (i + 1)], x * 60));
      u.setData([xsAll, ys, sp, pr]);
      const last = ys.length ? ys[ys.length - 1] : null;
      u._box.querySelector(".now").textContent = last === null || last === undefined ? "" : last.toFixed(1) + " °C";
    }
    $("#chart-caption").textContent = live.runId ? "Run " + live.runId + (pred ? " · grey dashes: predicted run" : "") + " · shaded: heater on" : "Not recording · shaded: heater on";
  });
}

$$("#window button").forEach(b => {
  b.classList.toggle("on", Number(b.dataset.min) === windowMin);
  b.addEventListener("click", () => {
    windowMin = Number(b.dataset.min);
    localStorage.setItem("windowMin", windowMin);
    $$("#window button").forEach(x => x.classList.toggle("on", x === b));
    drawLive(true);
  });
});

async function loadLive() {
  const d = await api("/api/live");
  live.t = []; live.tc = [[], [], []]; live.heat = []; live.sp = []; live.sptc = [];
  live.runId = S && S.run ? S.run.id : null;
  live.predicted = d.predicted || null;
  const start = d.run_start;
  live.origin = start !== null && start !== undefined ? start : (d.t.length ? d.t[0] : 0);
  for (let k = 0; k < d.t.length; k++) {
    if (start !== null && start !== undefined && d.t[k] < start) continue;
    live.t.push(d.t[k]);
    live.tc[0].push(d.tc1[k]); live.tc[1].push(d.tc2[k]); live.tc[2].push(d.tc3[k]);
    live.heat.push(d.heat[k]); live.sp.push(d.sp[k]); live.sptc.push(d.sp_tc[k]);
  }
  renderEvents(d.events);
  drawLive(true);
}

function addSample(s) {
  const runId = S && S.run ? S.run.id : null;
  if (runId !== live.runId) { loadLive(); return; }
  live.t.push(s.t);
  for (let i = 0; i < 3; i++) live.tc[i].push(s.tc[i]);
  live.heat.push(s.heat); live.sp.push(s.sp); live.sptc.push(s.sp_tc);
  const max = 4 * 3600 * 4;
  if (live.t.length > max) {
    const cut = live.t.length - max;
    live.t.splice(0, cut); live.heat.splice(0, cut); live.sp.splice(0, cut); live.sptc.splice(0, cut);
    live.tc.forEach(a => a.splice(0, cut));
  }
  renderReadouts(s);
  updateDuty();
  $("#core").textContent = s.core === null || s.core === undefined ? "—" : "≈ " + Math.round(s.core) + " °C";
  drawLive();
}

// ------------------------------------------------------------------ live panel
const rates = [[], [], []];
function renderReadouts(sample) {
  if (!S) return;
  const host = $("#readouts");
  const vis = visibleTcs();
  if (host.childElementCount !== vis.length || host.dataset.sig !== JSON.stringify(S.settings.tcs)) {
    host.innerHTML = "";
    host.dataset.sig = JSON.stringify(S.settings.tcs);
    for (const i of vis) {
      host.append(el("div", { class: "readout", id: "ro" + i, style: "--c:" + COLORS[i] },
        el("div", {}, el("div", { class: "name", html: "<b>TC" + (i + 1) + "</b>" + escapeHtml(S.settings.tcs[i].name) }), el("div", { class: "rate" })),
        el("div", { class: "val" })));
    }
  }
  const temps = sample ? sample.tc : S.temps;
  const faults = sample ? sample.faults : S.faults;
  const now = sample ? sample.t : 0;
  for (const i of vis) {
    const box = $("#ro" + i);
    if (!box) continue;
    const v = temps[i];
    const f = faults ? faults[i] : 0;
    box.classList.toggle("fault", v === null || v === undefined);
    $(".val", box).innerHTML = v === null || v === undefined ? faultText(f) : v.toFixed(1) + "<small>°C</small>";
    if (sample && v !== null && v !== undefined) {
      const r = rates[i];
      r.push([now, v]);
      while (r.length && now - r[0][0] > 10) r.shift();
      if (r.length > 4) {
        const dt = r[r.length - 1][0] - r[0][0];
        const slope = dt > 0 ? (r[r.length - 1][1] - r[0][1]) / dt : 0;
        $(".rate", box).textContent = (slope >= 0 ? "+" : "") + slope.toFixed(2) + " °C/s";
      }
    }
  }
  const heat = sample ? sample.heat : S.board.heat;
  const hp = $("#heat");
  hp.textContent = heat ? "ON" : "OFF";
  hp.className = "heatpill " + (heat ? "on" : "off");
}
function faultText(f) {
  if (f & 8) return "no amplifier";
  if (f & 1) return "open TC";
  if (f & 2) return "short to GND";
  if (f & 4) return "short to VCC";
  return "no reading";
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

function renderState() {
  if (!S) return;
  const b = S.board;
  const conn = $("#conn");
  let text, cls;
  if (b.status === "connected") {
    text = (b.sim ? "PRACTICE · simulated rig" : "Board " + b.port) + (b.stale ? " · no data" : "");
    cls = b.stale ? "bad" : (b.sim ? "sim" : "ok");
  } else if (b.status === "connecting") { text = "Connecting " + (b.detail || ""); cls = "bad"; }
  else if (b.status === "wrong_firmware") { text = "Old firmware on board"; cls = "bad"; }
  else if (b.status === "no_response") { text = "Board not answering"; cls = "bad"; }
  else { text = "No board" + (b.detail ? " · " + b.detail : ""); cls = "bad"; }
  conn.textContent = text;
  conn.title = b.detail || "";
  conn.className = "pill " + cls;

  const rec = $("#rec");
  if (S.run) { rec.textContent = "Run " + S.run.id + " · " + fmtDur(S.run.elapsed); rec.className = "pill rec"; }
  else rec.className = "pill hidden";

  const banner = $("#banner");
  if (b.tripped) {
    banner.className = "banner";
    banner.innerHTML = "";
    banner.append(el("span", { text: (b.trip || "Cutoff tripped") + " — heat is off." }),
      el("button", { onclick: () => act(() => api("/api/cmd", { cmd: "clear" })) }, "Clear cutoff"));
  } else if (banner.querySelector("button")) banner.classList.add("hidden");

  // heater card
  const pw = S.full_power_W;
  $("#power").textContent = S.settings.variac_V + " V · " + pw + " W full";
  const p = S.program;
  const spTxt = p && p.setpoint !== null && p.setpoint !== undefined && (p.state === "running" || p.state === "waiting") ? "setpoint " + p.setpoint.toFixed(1) + " °C" :
    (S.manual && S.manual.mode === "hold" ? "hold TC" + S.manual.tc + " " + S.manual.temp + " °C" : (S.manual && S.manual.mode === "on" ? "manual full power" : ""));
  $("#setpoint").textContent = spTxt;
  updateDuty();
  if (!liveCharts.length || liveCharts.sig !== JSON.stringify(S.settings.tcs)) buildLiveCharts();
  renderReadouts(null);

  // run card / start card
  $("#start-card").classList.toggle("hidden", !!S.run);
  $("#run-card").classList.toggle("hidden", !S.run);
  if (S.run) {
    $("#run-title").textContent = "Run " + S.run.id + " · " + S.run.title;
    $("#run-clock").textContent = fmtDur(S.run.elapsed);
    const ol = $("#steps");
    const steps = p.steps || [];
    const sig = JSON.stringify(steps) + p.index + p.state;
    if (ol.dataset.sig !== sig) {
      ol.dataset.sig = sig;
      ol.innerHTML = "";
      steps.forEach((txt, i) => ol.append(el("li", { class: i < p.index || p.state === "done" ? "done" : (i === p.index && (p.state === "running" || p.state === "waiting") ? "cur" : "") }, txt)));
    }
    let st = "";
    if (!steps.length) st = S.manual ? "Manual control" : "Recording only";
    else if (p.state === "running" && p.steps[p.index] && p.steps[p.index].startsWith("Hold") && p.step_time !== null && p.hold_elapsed === null) st = "Step " + (p.index + 1) + " · approaching the hold temperature · " + fmtDur(p.step_elapsed);
    else if (p.state === "running" && p.hold_elapsed !== null) st = "Step " + (p.index + 1) + " · holding " + fmtDur(p.hold_elapsed) + (p.step_time ? " / " + fmtDur(p.step_time) : "");
    else if (p.state === "running") st = "Step " + (p.index + 1) + " · " + fmtDur(p.step_elapsed) + (p.step_time ? " / " + fmtDur(p.step_time) : "");
    else if (p.state === "waiting") st = "Step " + (p.index + 1) + " done · press NEXT to continue";
    else if (p.state === "done") st = "Program finished · heat off · still recording";
    else if (p.state === "stopped") st = "Stopped · heat off · still recording";
    else if (p.state === "tripped") st = (p.message || "Cutoff") + " · heat off · still recording";
    $("#step-status").textContent = st;
    $("#btn-next").classList.toggle("pulse", p.state === "waiting");
  }
  const ps = $("#start-program");
  if (document.activeElement !== $("#start-volts") && !$("#start-volts").value) $("#start-volts").value = S.settings.variac_V;
  if (!ps.options.length) fillProgramSelect();
  const hs = $("#hold-tc");
  if (hs.dataset.sig !== JSON.stringify(S.settings.tcs)) {
    hs.dataset.sig = JSON.stringify(S.settings.tcs);
    hs.innerHTML = "";
    S.settings.tcs.forEach((t, i) => hs.append(el("option", { value: i + 1 }, "TC" + (i + 1))));
  }
}

// Share of the last 30 s the relay was on (what the bar under "Heater" shows).
function updateDuty() {
  const n = live.t.length;
  if (!n) { $("#duty-bar").style.width = "0%"; return; }
  const tEnd = live.t[n - 1];
  let on = 0, tot = 0;
  for (let i = n - 1; i > 0 && tEnd - live.t[i] < 30; i--) {
    const dt = live.t[i] - live.t[i - 1];
    tot += dt;
    if (live.heat[i - 1]) on += dt;
  }
  const f = tot > 0 ? on / tot : 0;
  $("#duty-bar").style.width = Math.round(f * 100) + "%";
  $("#duty-bar").parentElement.title = "Heater on " + Math.round(f * 100) + "% of the last 30 s";
}

function renderEvents(events) {
  const ul = $("#events");
  ul.innerHTML = "";
  (events || []).slice(-150).forEach(addEventRow);
}
function addEventRow(e) {
  const ul = $("#events");
  const time = e.utc ? new Date(e.utc).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  ul.prepend(el("li", {}, el("time", {}, time), el("span", {}, e.text)));
  while (ul.childElementCount > 150) ul.lastChild.remove();
}

// live buttons
$("#btn-start").addEventListener("click", () => act(async () => {
  const sel = $("#start-program").value;
  const prog = sel === "" ? null : programs[Number(sel)].program;
  const r = await api("/api/cmd", {
    cmd: "start", program: prog, title: $("#start-title").value.trim(),
    setup: $("#start-setup").value.trim(), variac_V: $("#start-volts").value,
  });
  $("#start-title").value = "";
  toast("Run " + r.run + " started");
}));
$("#btn-next").addEventListener("click", () => act(() => api("/api/cmd", { cmd: "next" })));
$("#btn-stop").addEventListener("click", () => act(() => api("/api/cmd", { cmd: "stop" })));
$("#btn-end").addEventListener("click", () => act(async () => {
  const rid = S && S.run ? S.run.id : null;
  await api("/api/cmd", { cmd: "end" });
  if (rid) setTimeout(() => renderRunPng(rid), 800);
}));
$("#btn-on").addEventListener("click", () => act(() => api("/api/cmd", { cmd: "heat_on" })));
$("#btn-off").addEventListener("click", () => act(() => api("/api/cmd", { cmd: "heat_off" })));
$("#btn-hold").addEventListener("click", () => act(() => {
  const t = $("#hold-temp").value;
  if (t === "") throw new Error("Type a hold temperature");
  return api("/api/cmd", { cmd: "hold", tc: Number($("#hold-tc").value), temp: Number(t) });
}));
function addNote() {
  return act(async () => {
    const t = $("#note").value.trim();
    if (!t) return;
    await api("/api/cmd", { cmd: "note", text: t });
    $("#note").value = "";
  });
}
$("#btn-note").addEventListener("click", addNote);
$("#note").addEventListener("keydown", e => { if (e.key === "Enter") addNote(); });
$("#btn-reconnect").addEventListener("click", () => act(() => api("/api/cmd", { cmd: "reconnect" })));
$("#btn-restart").addEventListener("click", () => act(async () => {
  await api("/api/cmd", { cmd: "restart" });
  programs = []; await loadPrograms();
  loadLive();
}));
document.addEventListener("keydown", e => {
  if (e.target.matches("input, textarea, select")) return;
  if ((e.key === "n" || e.key === "N") && S && S.run && $("#tab-live").classList.contains("on")) $("#btn-next").click();
});

// ------------------------------------------------------------------ stream
let es = null, lastMsg = 0;
function connect() {
  if (es) es.close();
  es = new EventSource("/api/stream");
  es.addEventListener("open", () => { $("#offline").classList.add("hidden"); lastMsg = Date.now(); loadLive().catch(() => {}); });
  es.addEventListener("state", ev => {
    lastMsg = Date.now();
    const prevRun = S && S.run ? S.run.id : null;
    S = JSON.parse(ev.data);
    renderState();
    const nowRun = S.run ? S.run.id : null;
    if (prevRun !== nowRun) { loadLive(); if (!nowRun) loadRunsQuiet(); }
  });
  es.addEventListener("sample", ev => { lastMsg = Date.now(); addSample(JSON.parse(ev.data)); });
  es.addEventListener("event", ev => { lastMsg = Date.now(); addEventRow(JSON.parse(ev.data)); });
  es.addEventListener("error", () => { $("#offline").classList.remove("hidden"); });
}
setInterval(() => {
  if (Date.now() - lastMsg > 15000) { $("#offline").classList.remove("hidden"); connect(); lastMsg = Date.now(); }
}, 3000);

// ------------------------------------------------------------------ programs
const ACTIONS = [["full", "Full power"], ["ramp", "Ramp"], ["hold", "Hold"], ["off", "Off"]];

async function loadPrograms() {
  const d = await api("/api/programs");
  programs = d.programs;
  fillProgramSelect();
  renderProgramList();
}
function fillProgramSelect() {
  const ps = $("#start-program");
  const keep = ps.value;
  ps.innerHTML = "";
  ps.append(el("option", { value: "" }, "None — record only"));
  programs.forEach((p, i) => ps.append(el("option", { value: i }, p.program.name)));
  const last = localStorage.getItem("startProgram");
  const want = keep !== "" ? keep : (last !== null ? last : (programs.length ? "0" : ""));
  if ([...ps.options].some(o => o.value === want)) ps.value = want;
}
$("#start-program").addEventListener("change", e => localStorage.setItem("startProgram", e.target.value));

function renderProgramList() {
  const ul = $("#program-list");
  ul.innerHTML = "";
  programs.forEach((p, i) => ul.append(el("li", { class: editing && editing.file === p.file ? "on" : "", onclick: () => editProgram(i) }, p.program.name)));
  if (!editing && programs.length) editProgram(0);
  else if (!editing) newProgram();
}
function blankProgram() {
  return { name: "New program", steps: [{ type: "full", tc: 1, temp: 100, time: null, wait: true }], end_when: [], cutoffs: { "1": 730, "2": 120, "3": null }, end_run: false };
}
function newProgram() { editing = { file: null, program: blankProgram() }; renderEditor(); renderProgramListMarks(); }
function editProgram(i) { editing = { file: programs[i].file, program: JSON.parse(JSON.stringify(programs[i].program)) }; renderEditor(); renderProgramListMarks(); }
function renderProgramListMarks() { $$("#program-list li").forEach((li, i) => li.classList.toggle("on", !!editing && programs[i] && programs[i].file === editing.file)); }
$("#btn-new-program").addEventListener("click", newProgram);

function numInput(value, onchange, placeholder) {
  return el("input", { type: "number", step: "any", value: value === null || value === undefined ? "" : value, placeholder: placeholder || "", oninput: e => onchange(e.target.value === "" ? null : Number(e.target.value)) });
}
function stepText(s) {
  const tc = "TC" + s.tc, t = s.temp, tm = s.time;
  const dur = tm !== null && tm !== undefined ? tm + " s" : "";
  let txt;
  if (s.type === "full") txt = t !== null && t !== undefined ? "Full power until " + tc + " ≥ " + t + " °C" + (tm ? " (max " + dur + ")" : "") : "Full power " + (dur ? "for " + dur : "until NEXT");
  else if (s.type === "ramp") txt = "Ramp " + tc + " from its current reading to " + (t ?? "?") + " °C over " + (dur || "? s");
  else if (s.type === "hold") txt = "Hold " + tc + " at " + (t ?? "?") + " °C " + (dur ? "for " + dur + " (timer starts at " + (t ?? "?") + " °C)" : "until NEXT");
  else txt = t !== null && t !== undefined ? "Heat off until " + tc + " ≤ " + t + " °C" : "Heat off " + (dur ? "for " + dur : "until NEXT");
  if (s.wait) txt += ", then wait for NEXT";
  return txt;
}
function renderEditor() {
  const p = editing.program;
  $("#prog-name").value = p.name;
  const tb = $("#step-rows");
  tb.innerHTML = "";
  p.steps.forEach((s, i) => {
    const desc = el("td", { colspan: 7, class: "desc" }, stepText(s));
    const update = () => { desc.textContent = stepText(s); schedulePreview(); };
    const act = el("select", { class: "act", onchange: e => { s.type = e.target.value; update(); } }, ACTIONS.map(([v, l]) => el("option", { value: v, selected: s.type === v }, l)));
    const tc = el("select", { class: "tc", onchange: e => { s.tc = Number(e.target.value); update(); } }, [1, 2, 3].map(n => el("option", { value: n, selected: s.tc === n }, "TC" + n)));
    const temp = el("span", { class: "unit-input num" }, numInput(s.temp, v => { s.temp = v; update(); }), el("i", {}, "°C"));
    const time = el("span", { class: "unit-input num" }, numInput(s.time, v => { s.time = v; update(); }), el("i", {}, "s"));
    const wait = el("input", { type: "checkbox", checked: !!s.wait, onchange: e => { s.wait = e.target.checked; update(); } });
    const ops = el("td", { class: "ops" },
      el("button", { title: "Move up", onclick: () => { if (i > 0) { p.steps.splice(i - 1, 0, p.steps.splice(i, 1)[0]); renderEditor(); } } }, "↑"),
      el("button", { title: "Move down", onclick: () => { if (i < p.steps.length - 1) { p.steps.splice(i + 1, 0, p.steps.splice(i, 1)[0]); renderEditor(); } } }, "↓"),
      el("button", { title: "Duplicate", onclick: () => { p.steps.splice(i + 1, 0, JSON.parse(JSON.stringify(s))); renderEditor(); } }, "⧉"),
      el("button", { title: "Delete", onclick: () => { p.steps.splice(i, 1); renderEditor(); } }, "✕"));
    tb.append(el("tr", {}, el("td", { class: "n" }, String(i + 1)), el("td", {}, act), el("td", {}, tc), el("td", {}, temp), el("td", {}, time), el("td", {}, wait), ops));
    tb.append(el("tr", {}, desc));
  });
  const cut = $("#cutoffs");
  cut.innerHTML = "";
  p.cutoffs = p.cutoffs || {};
  ["1", "2", "3"].forEach(k => cut.append(el("label", {}, "TC" + k, el("span", { class: "unit-input" }, numInput(p.cutoffs[k], v => { p.cutoffs[k] = v; schedulePreview(); }, "none"), el("i", {}, "°C")))));
  const ends = $("#end-rows");
  ends.innerHTML = "";
  (p.end_when = p.end_when || []).forEach((e, i) => {
    ends.append(el("div", { class: "end-row" },
      el("select", { onchange: ev => { e.tc = Number(ev.target.value); schedulePreview(); } }, [1, 2, 3].map(n => el("option", { value: n, selected: e.tc === n }, "TC" + n))),
      el("select", { onchange: ev => { e.op = ev.target.value; schedulePreview(); } }, [">=", "<="].map(o => el("option", { value: o, selected: e.op === o }, o === ">=" ? "≥" : "≤"))),
      el("span", { class: "unit-input" }, numInput(e.temp, v => { e.temp = v; schedulePreview(); }), el("i", {}, "°C")),
      el("button", { class: "ghost", onclick: () => { p.end_when.splice(i, 1); renderEditor(); } }, "✕")));
  });
  if (!p.end_when.length) ends.append(el("div", { class: "small muted" }, "None"));
  $("#prog-end-run").checked = !!p.end_run;
  $("#prog-msg").textContent = "";
  schedulePreview();
}
$("#prog-name").addEventListener("input", e => { editing.program.name = e.target.value; });
$("#btn-use-program").addEventListener("click", () => act(async () => {
  const file = await saveEditing();
  const idx = programs.findIndex(p => p.file === file);
  $("#start-program").value = String(idx);
  localStorage.setItem("startProgram", String(idx));
  showTab("live");
}));
$("#pv-next").addEventListener("input", () => schedulePreview());
let pvChart = null, pvTimer = null, pvSeq = 0;
function schedulePreview() { clearTimeout(pvTimer); pvTimer = setTimeout(runPreview, 350); }
async function runPreview() {
  if (!editing) return;
  const seq = ++pvSeq;
  const warn = $("#pv-warn"), stats = $("#pv-stats"), host = $("#pv-chart");
  $("#pv-volts").textContent = S ? S.settings.variac_V + " V, " + S.full_power_W + " W" : "";
  let pv;
  try {
    pv = await api("/api/preview", { program: editing.program, next_after_s: Number($("#pv-next").value || 0) });
  } catch (e) {
    if (seq !== pvSeq) return;
    warn.innerHTML = ""; warn.append(el("li", { class: "bad" }, e.message));
    stats.innerHTML = "";
    if (pvChart) { pvChart.destroy(); pvChart = null; }
    host.innerHTML = "";
    return;
  }
  if (seq !== pvSeq) return;
  stats.innerHTML = "";
  stats.append(statBox("Program length", fmtDur(pv.program_s)));
  stats.append(statBox("TC1 peak", fmtT(pv.peak_tc1, 0) + " °C"));
  stats.append(statBox("TC2 peak", fmtT(pv.peak_tc2, 0) + " °C"));
  stats.append(statBox("Core peak (model)", fmtT(pv.peak_core, 0) + " °C", "Model estimate of the inside of the cartridge. Rating: " + (S ? S.settings.heater_max_C : 760) + " °C."));
  stats.append(statBox("Heater on", fmtDur(pv.heat_on_s)));
  stats.append(statBox("Energy in", pv.energy_kJ + " kJ"));
  warn.innerHTML = "";
  pv.warnings.forEach(w => warn.append(el("li", {}, w)));
  if (!pv.warnings.length) warn.append(el("li", { class: "ok" }, "No problems predicted."));
  if (pvChart) { pvChart.destroy(); pvChart = null; }
  host.innerHTML = "";
  const series = [
    { label: "TC1", stroke: COLORS[0], width: 2 },
    { label: "TC2", stroke: COLORS[1], width: 2 },
    { label: "core (model)", stroke: "#adb5bd", width: 1.5, dash: [3, 4] },
    { label: "setpoint", stroke: COLORS[0], width: 1.2, dash: [6, 5] },
  ].map(x => Object.assign(x, { value: (u, v) => v === null ? "—" : v.toFixed(0) }));
  pvChart = makeChart(host, "Predicted", "#495057", () => pv.heat, series, { legend: true });
  pvChart._box.style.flex = "none"; pvChart._box.style.height = "320px";
  pvChart.setData([pv.t.map(t => t / 60), pv.tc1, pv.tc2, pv.core, pv.sp]);
  // Step boundaries as labels under the chart.
  const marks = el("div", { class: "pv-steps small muted" });
  pv.steps.forEach(m => { if (m.index < editing.program.steps.length) marks.append(el("span", {}, "Step " + (m.index + 1) + " at " + fmtDur(m.t))); });
  host.append(marks);
  setTimeout(() => sizeChart(pvChart), 0);
}
$("#prog-end-run").addEventListener("change", e => { editing.program.end_run = e.target.checked; });
$("#btn-add-step").addEventListener("click", () => {
  const steps = editing.program.steps;
  const last = steps[steps.length - 1];
  steps.push({ type: "hold", tc: last ? last.tc : 1, temp: last && last.temp !== null ? last.temp : 100, time: 60, wait: false });
  renderEditor();
});
$("#btn-add-end").addEventListener("click", () => { editing.program.end_when.push({ tc: 2, op: ">=", temp: 85 }); renderEditor(); });
// Saving under a new name makes a new program; the original stays (Delete removes it).
async function saveEditing() {
  const before = editing.file;
  const r = await api("/api/programs", editing.program);
  editing.file = r.file;
  await loadPrograms();
  renderProgramListMarks();
  const msg = $("#prog-msg");
  msg.className = "small msg-ok";
  msg.textContent = before && before !== r.file ? "Saved as a new program, “" + editing.program.name + "”. The original is unchanged." : "Saved.";
  return r.file;
}
$("#btn-save-program").addEventListener("click", () => act(saveEditing));
$("#btn-delete-program").addEventListener("click", () => act(async () => {
  if (!editing.file) { newProgram(); return; }
  if (!confirm("Delete program “" + editing.program.name + "”?")) return;
  await api("/api/programs/delete", { file: editing.file });
  editing = null;
  await loadPrograms();
}));

// ------------------------------------------------------------------ runs
let runs = [], runCharts = [], currentRun = null;
const compareSet = new Set();

async function loadRuns() {
  const d = await api("/api/runs");
  runs = d.runs.reverse();
  renderRunList();
  if (!currentRun) {
    const first = runs.find(r => r.category === "test") || runs[0];
    if (first) openRun(first.id);
  }
}
function loadRunsQuiet() { if ($("#tab-runs").classList.contains("on")) loadRuns(); }
function renderRunList() {
  const q = $("#run-search").value.trim().toLowerCase();
  const filter = $("#run-filter").value;
  const ul = $("#run-list");
  ul.innerHTML = "";
  for (const r of runs) {
    const hay = (r.id + " " + r.title + " " + r.setup + " " + r.category).toLowerCase();
    if (q && !hay.includes(q)) continue;
    if (filter === "key" && !(r.category === "test" || r.category === "partial" || r.new)) continue;
    const date = r.started ? new Date(r.started).toLocaleDateString([], { month: "short", day: "numeric" }) : "";
    const cb = el("input", { type: "checkbox", checked: compareSet.has(r.id), onclick: e => { e.stopPropagation(); e.target.checked ? compareSet.add(r.id) : compareSet.delete(r.id); } });
    ul.append(el("li", { class: currentRun === r.id ? "on" : "", "data-id": r.id, onclick: () => openRun(r.id) },
      cb,
      el("div", { class: "grow" }, el("span", { class: "rid" }, r.id), " ", el("span", { class: "small muted" }, date), el("span", { class: "rtitle" }, r.title || "—")),
      el("span", { class: "chip " + (r.recording ? "recording" : r.category) }, r.recording ? "rec" : r.category)));
  }
  if (!ul.childElementCount) ul.append(el("li", { class: "muted" }, "No runs match"));
}
$("#run-search").addEventListener("input", renderRunList);
$("#run-filter").addEventListener("change", renderRunList);

function statBox(label, value, help) {
  return el("div", { class: "stat" + (help ? " has-help" : ""), title: help || "" }, el("b", {}, value), el("span", {}, label));
}

async function openRun(id) {
  currentRun = id;
  if (window.innerWidth <= 700) $("#run-view").scrollIntoView({ behavior: "smooth" });
  $$("#run-list li").forEach(li => li.classList.toggle("on", li.dataset.id === id));
  const view = $("#run-view");
  view.innerHTML = "";
  view.append(el("div", { class: "muted" }, "Loading run " + id + "…"));
  const [d, data] = await Promise.all([api("/api/runs/" + id), api("/api/runs/" + id + "/data")]);
  if (currentRun !== id) return;
  view.innerHTML = "";
  const sm = d.summary, a = d.analysis || {};
  const names = d.tc_names || [];
  const isNew = !!(d.meta && d.meta.run);

  const head = el("div", {}, el("h2", {}, "Run " + id + (sm.title ? " — " + sm.title : "")),
    el("div", { class: "sub" }, [sm.started ? new Date(sm.started).toLocaleString() : "", sm.voltage ? sm.voltage + " V" : "", a.duration_s ? fmtDur(a.duration_s) + " long" : ""].filter(Boolean).join(" · ")));
  view.append(head);
  if (sm.setup) view.append(el("div", {}, el("b", {}, "Setup: "), sm.setup));
  if (d.review) view.append(el("div", { class: "review" }, d.review));

  const H = d.metric_help || {};
  const stats = el("div", { class: "stats" });
  for (const k of ["tc1", "tc2", "tc3"]) {
    if (!a[k]) continue;
    const i = Number(k[2]) - 1;
    stats.append(statBox("TC" + (i + 1) + " peak, at " + fmtDur(a[k].peak_t), fmtT(a[k].peak) + " °C", H.peak));
  }
  if (a.tc1_reach) for (const [lvl, t] of Object.entries(a.tc1_reach)) stats.append(statBox("TC1 to " + lvl + " °C", fmtDur(t), H.reach));
  if (a.tc1_max_rate) stats.append(statBox("TC1 fastest rise", a.tc1_max_rate.toFixed(2) + " °C/s", H.max_rate));
  if (a.tc1_dwell700_s) stats.append(statBox("TC1 at ≥ 700 °C", fmtDur(a.tc1_dwell700_s), H.dwell700));
  if (a.tc2_rise !== undefined) stats.append(statBox("TC2 rise", fmtT(a.tc2_rise) + " °C", H.tc2_rise));
  if (a.tc2_delay_s !== undefined && a.tc2_rise > 5) stats.append(statBox("TC2 peak after TC1 peak", (a.tc2_delay_s < 0 ? "−" : "") + fmtDur(Math.abs(a.tc2_delay_s)), H.tc2_delay));
  if (a.barrier) stats.append(statBox("Barrier rear gain (±" + a.barrier.rmse_C + " °C)", a.barrier.rear_gain.toFixed(2), H.rear_gain));
  if (a.heat_on_s) stats.append(statBox("Relay on", fmtDur(a.heat_on_s), H.heat_on));
  if (a.energy_kJ) stats.append(statBox("Energy in, ≤ (" + a.power_W + " W)", a.energy_kJ + " kJ", H.energy));
  if (stats.childElementCount) view.append(stats);

  const host = el("div", { class: "charts", id: "run-charts" });
  view.append(host);
  runCharts.forEach(u => u.destroy());
  runCharts = [];
  const xs = data.t.map(t => t / 60);
  const shown = d.meta && d.meta.tc_shown;
  const tcsWithData = [0, 1, 2].filter(i => (data["tc" + (i + 1)] || []).some(v => v !== null) && (!shown || shown[i]));
  for (const i of tcsWithData) {
    const u = makeChart(host, "TC" + (i + 1) + " · " + (names[i] || ""), COLORS[i], () => data.heat, null, { legend: true });
    u._tc = i;
    u._box.style.minHeight = "220px";
    u._box.style.flex = "none";
    u._box.style.height = "260px";
    const sp = (data.sp || []).map((v, k) => (data.sp_tc && data.sp_tc[k] === i + 1 ? v : null));
    const pred = d.meta && d.meta.predicted;
    const pr = pred && i < 2 ? data.t.map(t => interp(pred.t, pred["tc" + (i + 1)], t)) : data.t.map(() => null);
    u.setData([xs, data["tc" + (i + 1)], sp, pr]);
    runCharts.push(u);
  }
  if (!tcsWithData.length) host.append(el("div", { class: "muted" }, "No valid temperature readings in this run."));
  setTimeout(resizeCharts, 0);

  if (d.images && d.images.length) {
    view.append(el("div", { class: "label" }, "Images"));
    view.append(el("div", { class: "thumbs" }, d.images.map(f => el("img", { src: "/runs/" + id + "/" + encodeURIComponent(f) + "?v=" + Date.now(), title: f, onclick: e => openLightbox(e.target.src) }))));
  }

  const notes = el("textarea", { rows: 5 });
  notes.value = d.notes || "";
  const saveMsg = el("span", { class: "small muted" });
  view.append(el("div", { class: "card" },
    el("div", { class: "row between" }, el("span", { class: "label" }, "Notes"), saveMsg),
    notes,
    el("div", { class: "row gap" }, el("button", { class: "primary", onclick: () => act(async () => { await api("/api/runs/" + id + "/notes", { text: notes.value }); saveMsg.textContent = "Saved to runs/" + id + "/notes.md"; }) }, "Save notes"))));
  if (isNew) {
    const title = el("input", { type: "text", value: d.meta.title || "" });
    const setup = el("textarea", { rows: 2 });
    setup.value = d.meta.setup || "";
    const msg = el("span", { class: "small muted" });
    view.append(el("div", { class: "card" }, el("div", { class: "row between" }, el("span", { class: "label" }, "Details"), msg),
      el("label", {}, "Title", title), el("label", {}, "Setup", setup),
      el("div", {}, el("button", { onclick: () => act(async () => { await api("/api/runs/" + id + "/meta", { title: title.value, setup: setup.value }); msg.textContent = "Saved"; loadRuns(); }) }, "Save details"))));
  }
  const gh = (S && S.settings.github) || "";
  view.append(el("div", { class: "card files" },
    el("div", { class: "row between" }, el("span", { class: "label" }, "Files"),
      el("span", { class: "small muted" }, "Folder: ", el("code", {}, "runs/" + id + "/"), gh ? el("a", { href: gh + "/tree/main/runs/" + id, target: "_blank" }, " · on GitHub") : null)),
    el("div", { class: "row gap wrap" }, (d.files || []).map(f => el("a", { href: "/runs/" + id + "/" + encodeURIComponent(f) + "?dl=1" }, f)))));
  if (d.events && d.events.length) {
    const tb = el("table", { class: "ev-table" });
    d.events.forEach(e => tb.append(el("tr", {}, el("td", {}, e.t === null ? "" : fmtDur(e.t)), el("td", {}, e.text))));
    view.append(el("details", {}, el("summary", {}, "Events (" + d.events.length + ")"), tb));
  }
  if (isNew && !sm.recording && !d.images.includes("plot.png") && data.t.length > 10) setTimeout(() => uploadPng(id, runCharts, names), 500);
}

function openLightbox(src) { const lb = $("#lightbox"); $("img", lb).src = src; lb.classList.remove("hidden"); }
$("#lightbox").addEventListener("click", () => $("#lightbox").classList.add("hidden"));

// Combine chart canvases into runs/<id>/plot.png so the run has a picture on GitHub too.
async function uploadPng(id, charts, names) {
  if (!charts.length) return;
  const w = 1200, ph = 300, pad = 30;
  const c = document.createElement("canvas");
  c.width = w; c.height = charts.length * (ph + pad) + 10;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
  charts.forEach((u, k) => {
    const src = u.ctx.canvas;
    ctx.fillStyle = "#1d2228"; ctx.font = "bold 16px sans-serif";
    ctx.fillText("Run " + id + " · TC" + (u._tc !== undefined ? u._tc + 1 : k + 1) + " " + (u._box.querySelector("h3").childNodes[1].textContent || ""), 10, k * (ph + pad) + 20);
    ctx.drawImage(src, 0, k * (ph + pad) + pad - 4, w, ph);
  });
  const blob = await new Promise(r => c.toBlob(r, "image/png"));
  await fetch("/api/runs/" + id + "/png/plot", { method: "POST", body: blob });
}

async function renderRunPng(id) {
  try {
    const data = await api("/api/runs/" + id + "/data");
    const d = await api("/api/runs/" + id);
    const host = el("div", { id: "png-host", style: "position:fixed;left:-3000px;top:0;width:1200px" });
    document.body.append(host);
    const charts = [];
    [0, 1, 2].forEach(i => {
      if (!(data["tc" + (i + 1)] || []).some(v => v !== null)) return;
      const u = makeChart(host, "TC" + (i + 1) + " · " + (d.tc_names[i] || ""), COLORS[i], () => data.heat);
      u._tc = i;
      u.setSize({ width: 1200, height: 300 });
      const sp = data.sp.map((v, k) => (data.sp_tc[k] === i + 1 ? v : null));
      u.setData([data.t.map(t => t / 60), data["tc" + (i + 1)], sp, data.t.map(() => null)]);
      charts.push(u);
    });
    await uploadPng(id, charts);
    charts.forEach(u => u.destroy());
    host.remove();
  } catch (e) { /* the Runs tab renders it later */ }
}

// Compare: overlay ticked runs, aligned at heater start.
$("#btn-compare").addEventListener("click", () => act(async () => {
  const ids = [...compareSet].sort();
  if (ids.length < 2) throw new Error("Tick two or more runs in the list to compare");
  currentRun = null;
  $$("#run-list li").forEach(li => li.classList.remove("on"));
  const view = $("#run-view");
  view.innerHTML = "";
  view.append(el("h2", {}, "Compare " + ids.join(", ")));
  const alignSel = el("select", {}, el("option", { value: "heat" }, "Align at heater start"), el("option", { value: "start" }, "Align at run start"), el("option", { value: "peak" }, "Align at TC1 peak"));
  view.append(el("div", { class: "row gap" }, el("span", { class: "small muted" }, "Alignment"), alignSel));
  const datas = await Promise.all(ids.map(id => api("/api/runs/" + id + "/data")));
  const details = await Promise.all(ids.map(id => api("/api/runs/" + id)));
  const table = el("table", { class: "ev-table" });
  table.append(el("tr", {}, ["Run", "Setup", "TC1 peak", "TC2 peak", "TC2 rise", "TC1 → 700 °C", "Heater on"].map(h => el("td", { style: "font-weight:600;color:#1d2228" }, h))));
  details.forEach((d, k) => {
    const a = d.analysis || {};
    table.append(el("tr", {},
      el("td", {}, el("span", { style: "color:" + COMPARE_COLORS[k % 8] + ";font-weight:700" }, ids[k])),
      el("td", {}, d.summary.setup || d.summary.title || ""),
      el("td", {}, a.tc1 ? fmtT(a.tc1.peak) + " °C" : "—"),
      el("td", {}, a.tc2 ? fmtT(a.tc2.peak) + " °C" : "—"),
      el("td", {}, a.tc2_rise !== undefined ? fmtT(a.tc2_rise) + " °C" : "—"),
      el("td", {}, a.tc1_reach && a.tc1_reach["700"] !== undefined ? fmtDur(a.tc1_reach["700"]) : "—"),
      el("td", {}, a.heat_on_s ? fmtDur(a.heat_on_s) : "—")));
  });
  view.append(table);
  const host = el("div", { class: "charts", id: "cmp-charts" });
  view.append(host);
  function draw() {
    runCharts.forEach(u => u.destroy());
    runCharts = [];
    host.innerHTML = "";
    const offsets = datas.map((d, k) => {
      if (alignSel.value === "start") return d.t[0] || 0;
      if (alignSel.value === "peak") { let best = -1, bt = 0; d.t.forEach((t, j) => { const v = d.tc1[j]; if (v !== null && v > best) { best = v; bt = t; } }); return bt; }
      const a = details[k].analysis || {};
      return a.heat_start_s !== null && a.heat_start_s !== undefined ? a.heat_start_s : (d.t[0] || 0);
    });
    for (const i of [0, 1]) {
      // Merge all runs on one x axis (minutes), one series per run.
      const series = ids.map((id, k) => ({ label: id, stroke: COMPARE_COLORS[k % 8], width: 2, spanGaps: true, value: (u, v) => v === null ? "—" : v.toFixed(1) }));
      const xsAll = new Set();
      const maps = datas.map((d, k) => { const m = new Map(); d.t.forEach((t, j) => { const x = Math.round((t - offsets[k]) / 60 * 200) / 200; m.set(x, d["tc" + (i + 1)][j]); xsAll.add(x); }); return m; });
      const xs = [...xsAll].sort((a, b) => a - b);
      const u = makeChart(host, "TC" + (i + 1) + " · " + (i === 0 ? "heater side" : "barrier rear"), COLORS[i], null, series, { legend: true, xLabel: "time from the alignment point (m:ss)" });
      u._box.style.flex = "none"; u._box.style.height = "300px";
      u.setData([xs, ...maps.map(m => xs.map(x => (m.has(x) ? m.get(x) : null)))]);
      runCharts.push(u);
    }
    setTimeout(resizeCharts, 0);
  }
  alignSel.addEventListener("change", draw);
  draw();
}));

// ------------------------------------------------------------------ findings
// analysis/README.md rendered with a small Markdown subset (headings, lists, tables, images, bold, code, links).
async function loadFindings() {
  const box = $("#findings");
  if (box.dataset.loaded) return;
  const r = await fetch("/analysis/README.md");
  if (!r.ok) { box.textContent = "analysis/README.md not found"; return; }
  box.innerHTML = renderMarkdown(await r.text(), "/analysis/");
  box.querySelectorAll("img").forEach(img => img.addEventListener("click", () => openLightbox(img.src)));
  box.querySelectorAll("a[href^='runs/'], a[href^='../runs/']").forEach(a => a.addEventListener("click", e => { e.preventDefault(); }));
  box.dataset.loaded = "1";
}
function inlineMd(t, base) {
  t = escapeHtml(t);
  t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (m, alt, src) => '<img alt="' + alt + '" src="' + (src.startsWith("http") ? src : base + src) + '">');
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, txt, href) => '<a href="' + (href.startsWith("http") ? href : base + href) + '" target="_blank">' + txt + "</a>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>").replace(/`([^`]+)`/g, "<code>$1</code>");
  return t;
}
function renderMarkdown(md, base) {
  const lines = md.split("\n");
  let html = "", i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^#{1,4} /.test(l)) { const n = l.match(/^#+/)[0].length; html += "<h" + n + ">" + inlineMd(l.slice(n + 1), base) + "</h" + n + ">"; i++; continue; }
    if (/^\|/.test(l)) {
      const rows = [];
      while (i < lines.length && /^\|/.test(lines[i])) { rows.push(lines[i]); i++; }
      const cells = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      html += "<table><thead><tr>" + cells(rows[0]).map(c => "<th>" + inlineMd(c, base) + "</th>").join("") + "</tr></thead><tbody>";
      rows.slice(2).forEach(r => { html += "<tr>" + cells(r).map(c => "<td>" + inlineMd(c, base) + "</td>").join("") + "</tr>"; });
      html += "</tbody></table>"; continue;
    }
    if (/^(\d+\.|\*|-) /.test(l)) {
      const ordered = /^\d+\./.test(l);
      html += ordered ? "<ol>" : "<ul>";
      while (i < lines.length && /^(\d+\.|\*|-) /.test(lines[i])) {
        let item = lines[i].replace(/^(\d+\.|\*|-) /, ""); i++;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) { item += " " + lines[i].trim(); i++; }
        html += "<li>" + inlineMd(item, base) + "</li>";
      }
      html += ordered ? "</ol>" : "</ul>"; continue;
    }
    if (!l.trim()) { i++; continue; }
    let para = l; i++;
    while (i < lines.length && lines[i].trim() && !/^(#|\||\d+\.|\* |- )/.test(lines[i])) { para += " " + lines[i].trim(); i++; }
    html += "<p>" + inlineMd(para, base) + "</p>";
  }
  return html;
}

// ------------------------------------------------------------------ settings
function renderSettings() {
  if (!S) return;
  const s = JSON.parse(JSON.stringify(S.settings));
  const f = $("#settings-form");
  f.innerHTML = "";
  const num = (obj, key, label, unit, hint, step) => el("label", {}, label,
    el("span", { class: "unit-input" }, el("input", { type: "number", step: step || "any", value: obj[key], oninput: e => { obj[key] = e.target.value === "" ? null : Number(e.target.value); refreshPower(); } }), unit ? el("i", {}, unit) : null),
    hint ? el("span", { class: "hint" }, hint) : null);
  const powerLine = el("div", { class: "hint" });
  function refreshPower() {
    const w = s.heater_W * Math.pow(s.variac_V / s.heater_rated_V, 2);
    powerLine.textContent = "Full power = " + s.heater_W + " W × (" + s.variac_V + " V / " + s.heater_rated_V + " V)² = " + Math.round(w) + " W. Saved settings: heater side can reach about " + (S ? S.max_surface_C : "?") + " °C at full power.";
  }
  refreshPower();

  f.append(el("div", { class: "card" }, el("div", { class: "label" }, "Variac and heater"),
    num(s, "variac_V", "Variac voltage", "V", "Set this to what the variac outputs. Control gain scales with voltage squared."),
    el("div", { class: "two" }, num(s, "heater_W", "Heater rating", "W"), num(s, "heater_rated_V", "at", "V")),
    powerLine));

  const tcCard = el("div", { class: "card" }, el("div", { class: "label" }, "Thermocouples"),
    el("div", { class: "hint" }, "Amplifier = which MAX31855 board the TC is wired to (1: pins 22/24/26, 2: 28/30/32, 3: 34/36/38)."));
  s.tcs.forEach((t, i) => {
    tcCard.append(el("div", { class: "tcrow" }, el("b", { style: "color:" + COLORS[i] }, "TC" + (i + 1)),
      el("input", { type: "text", value: t.name, oninput: e => { t.name = e.target.value; } }),
      el("select", { onchange: e => { t.amp = Number(e.target.value); } }, [1, 2, 3].map(a => el("option", { value: a, selected: Number(t.amp) === a }, "Amp " + a))),
      el("label", { class: "check" }, el("input", { type: "checkbox", checked: !!t.show, onchange: e => { t.show = e.target.checked; } }), "show")));
  });
  f.append(tcCard);

  const c = s.control;
  const modeSel = el("select", { onchange: e => { c.mode = e.target.value; } },
    el("option", { value: "predictive", selected: c.mode !== "onoff" }, "Predictive (model look-ahead) — recommended"),
    el("option", { value: "onoff", selected: c.mode === "onoff" }, "On/off with slope look-ahead"));
  f.append(el("div", { class: "card" }, el("div", { class: "label" }, "Temperature control (Ramp and Hold steps)"),
    el("label", {}, "Method", modeSel),
    el("div", { class: "hint" }, "Predictive: heat only while the model says the TC would stay below the setpoint if the heater switched off now. This allows for the heat stored in the cartridge (switching off at 100 °C used to coast to ~185 °C)."),
    el("div", { class: "hint" }, "On/off: heat while (reading + slope × look-ahead) is below the setpoint. Needs no model; 30 s look-ahead holds within about 5 °C in simulation."),
    el("div", { class: "two" },
      num(c, "hysteresis_C", "Switching band", "°C", "Wider = fewer relay clicks"),
      num(c, "min_pulse_s", "Shortest on/off", "s", "Protects the relay"),
      num(c, "lead_s", "On/off look-ahead", "s"))));

  const m = s.model;
  const mrow = (key, label, unit, hint) => num(m, key, label, unit, hint);
  f.append(el("div", { class: "card" }, el("div", { class: "label" }, "Thermal model"),
    el("div", { class: "hint" }, "Used by Predictive control, the Predicted run and the practice rig. Heater numbers fitted to run068 (fits within 3 °C up to 187 °C and 11 °C up to 425 °C); barrier numbers are the median of runs 026, 028, 036, 040."),
    el("div", { class: "two" },
      mrow("core_J_per_K", "Core heat capacity", "J/K"),
      mrow("surface_J_per_K", "Heater-side heat capacity", "J/K"),
      mrow("core_to_surface_K_per_W", "Core → TC1 resistance", "K/W"),
      mrow("loss_W_per_K", "Loss to sand/air", "W/K"),
      mrow("radiation_W_per_K4", "Radiation coefficient", "W/K⁴"),
      mrow("barrier_a1_per_s", "Barrier in-rate a1", "1/s"),
      mrow("barrier_a2_per_s", "Barrier through-rate a2", "1/s"),
      mrow("rear_loss_per_s", "Rear loss rate b", "1/s")),
    el("div", { class: "two" },
      num(s, "room_C", "Room temperature", "°C"),
      num(s, "heater_max_C", "Cartridge rating", "°C", "8440T32: 760 °C (1400 °F)")),
    el("label", { class: "check" }, el("input", { type: "checkbox", checked: !!s.tc3_is_core, onchange: e => { s.tc3_is_core = e.target.checked; } }), "TC3 is the cartridge's internal TC (corrects the core estimate)")));

  const portSel = el("select", { onchange: e => { s.port = e.target.value; } }, el("option", { value: "" }, "Automatic (first Arduino)"));
  api("/api/ports").then(d => {
    d.ports.forEach(p => portSel.append(el("option", { value: p.device, selected: s.port === p.device }, p.device + " — " + p.description)));
    if (s.port && ![...portSel.options].some(o => o.value === s.port)) portSel.append(el("option", { value: s.port, selected: true }, s.port + " (not present)"));
  });
  const relaySel = el("select", { onchange: e => { s.relay = e.target.value; } },
    el("option", { value: "NC", selected: s.relay !== "NO" }, "COM–NC (heat flows when relay is unpowered)"),
    el("option", { value: "NO", selected: s.relay === "NO" }, "COM–NO (heat only when relay is energized)"));
  const fwMsg = el("span", { class: "hint" });
  f.append(el("div", { class: "card" }, el("div", { class: "label" }, "Board"),
    el("label", {}, "Serial port", portSel),
    el("label", {}, "Relay wiring", relaySel),
    el("div", { class: "two" },
      num(s, "sample_ms", "Sample every", "ms", null, "50"),
      num(s, "fault_trip_s", "Cut heat if a cutoff TC fails for", "s", "0 = never"),
      num(s, "lease_ms", "Heat lease", "ms", "Board turns heat off if this computer goes quiet this long")),
    el("div", { class: "row gap" }, el("button", { onclick: () => act(async () => {
      if (!confirm("Upload the che126-daq firmware to the board on " + (s.port || (S.board.port || "the selected port")) + "?")) return;
      fwMsg.textContent = "Uploading… keep the USB cable in.";
      await api("/api/firmware", { port: s.port || S.board.port });
      fwMsg.textContent = "Firmware uploaded.";
    }) }, "Upload firmware"), fwMsg),
    el("div", { class: "hint" }, "Board: " + (S.board.firmware ? "che126-daq firmware " + S.board.firmware + ", relay " + S.board.relay : S.board.status))));

  f.append(el("div", { class: "card" }, el("div", { class: "label" }, "Files"),
    el("label", {}, "Runs folder", el("input", { type: "text", value: s.runs_dir, oninput: e => { s.runs_dir = e.target.value; } })),
    el("label", {}, "GitHub repository", el("input", { type: "text", value: s.github || "", oninput: e => { s.github = e.target.value; } })),
    el("div", { class: "hint" }, "Settings are saved in settings.json beside daq.py.")));

  const msg = el("span", { class: "small" });
  f.append(el("div", { class: "actions" },
    el("button", { class: "primary", onclick: () => act(async () => {
      S.settings = await api("/api/settings", s);
      msg.className = "small msg-ok"; msg.textContent = "Saved and applied.";
      liveCharts = []; renderState();
      $("#start-volts").value = S.settings.variac_V;
    }) }, "Save settings"),
    el("button", { class: "ghost", onclick: renderSettings }, "Undo changes"),
    msg));
}

// ------------------------------------------------------------------ boot
(async function boot() {
  try {
    S = await api("/api/state");
    renderState();
    await loadPrograms();
  } catch (e) { $("#offline").classList.remove("hidden"); }
  connect();
  showTab(localStorage.getItem("tab") || "live");
})();
