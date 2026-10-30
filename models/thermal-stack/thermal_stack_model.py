#!/usr/bin/env python3
"""
Mica + basalt insulation, with/without a 0.225 mm 3003-H14 Al backer.

Produces plots, calculated transient predictions, and a measurement CSV template.
Model: steady 1D thermal resistances and transient through-layer RC,
         coupled across aluminum laterally using a vertical 1D stripe mesh;
         independent illustrative steady aluminum heat-spreading model.
Dependencies: numpy, scipy, matplotlib (all available via pip).

Run:
    python thermal_stack_model.py
    python thermal_stack_model.py --power 20 --coupling 0.30 --h 15 \
        --heater-width-in 2 --heater-height-in 3 --target 100
    python thermal_stack_model.py --measurements measurements_template.csv

IMPORTANT: These are conditional modeling predictions, NOT calibration curves.
Unknown source-to-sample coupling, air gaps, contact pressure, emissivity,
heater contact dimensions, and thermocouple installation can dominate error.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.linalg import eigh
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve
from scipy.integrate import solve_ivp
from scipy.sparse import lil_matrix

INCH = 0.0254
BTU_IN_HR_FT2_F_TO_W_MK = 1055.05585262 * INCH / (3600 * INCH**2 * 144 * (5 / 9))

@dataclass(frozen=True)
class Material:
    name: str
    thickness: float  # m
    k: float          # W / (m K)
    rho: float        # kg / m3
    cp: float         # J / (kg K)

# Mica and basalt thickness/k/density from the user's McMaster-Carr PDFs.
# Basalt's k is specified at 900 F. Mica's k is listed as 0.3 W/(m K).
# 3003-H14 aluminum k/rho/cp from alloy property references.
# Both mica and basalt cp values are ASSUMED; the product PDFs do not give cp.
MICA = Material("Mica", 0.032 * INCH, 0.300,
                0.2 * 0.45359237 / INCH**3, 840.0)
BASALT = Material("Basalt", (3 / 64) * INCH,
                  2.44 * BTU_IN_HR_FT2_F_TO_W_MK,
                  1.75 * 0.45359237 / (12 * INCH)**3, 840.0)
ALUMINUM = Material("Aluminum 3003-H14", 0.225e-3, 159.0, 2730.0, 893.0)
BARE = [MICA, BASALT]
WITH_AL = [MICA, BASALT, ALUMINUM]

HEIGHT_IN, WIDTH_IN = 6.0, 2.0
FULL_AREA = HEIGHT_IN * WIDTH_IN * INCH**2


def layer_resistance(material, area):
    return material.thickness / (material.k * area)


def stack_resistance(layers, area, added_contact_rpp=0.0):
    """added_contact_rpp is area-specific interface R'' in m2 K/W."""
    return sum(layer_resistance(m, area) for m in layers) + added_contact_rpp / area


def effective_k(layers, area):
    return sum(m.thickness for m in layers) / (stack_resistance(layers, area) * area)


def transient(layers, time_s, source_power_W, area, h_W_m2K=15.0,
              ambient_C=25.0, added_contact_rpp=0.0, mica_density_scale=1.0):
    """Rear surface T for heat flux delivered into hot face, convective rear loss.

    One isothermal-capacitance node per layer. Between centers, series half-layer
    resistances; at rear, a half-layer resistance + 1/(hA). No direct front-face
    loss (it is rolled into the input power coupling). No radiation separately;
    h is an EFFECTIVE rear heat transfer coefficient.

    Exact linear ODE step response via real symmetric eigendecomposition, avoiding
    numerical instability from the small basalt heat capacity.
    """
    n = len(layers)
    heat_cap = np.array([m.rho * m.cp * m.thickness * area *
                         (mica_density_scale if m.name == "Mica" else 1.0)
                         for m in layers])
    K = np.zeros((n, n))
    for j in range(n - 1):
        res = (layers[j].thickness / (2 * layers[j].k * area) +
               layers[j + 1].thickness / (2 * layers[j + 1].k * area))
        if j == len(layers) - 2 and len(layers) == 3:
            res += added_contact_rpp / area  # basalt-to-aluminum interface
        g = 1 / res
        K[j, j] += g
        K[j + 1, j + 1] += g
        K[j, j + 1] -= g
        K[j + 1, j] -= g
    rear_res = (layers[-1].thickness / (2 * layers[-1].k * area)
                + 1 / (h_W_m2K * area))
    K[-1, -1] += 1 / rear_res
    injected = np.zeros(n)
    injected[0] = source_power_W
    steady = np.linalg.solve(K, injected)
    invsqrt = np.diag(1 / np.sqrt(heat_cap))
    sqrt = np.diag(np.sqrt(heat_cap))
    eigenvals, V = eigh(invsqrt @ K @ invsqrt)
    weights = V.T @ sqrt @ steady
    exps = np.exp(-eigenvals[:, None] * np.asarray(time_s)[None, :])
    decay = invsqrt @ V @ (weights[:, None] * exps)
    # Thermocouple is at the external rear surface, not layer center.
    convection_R = 1/(h_W_m2K*area)
    rear_surface_fraction = convection_R / rear_res
    return ambient_C + (steady[-1] - decay[-1, :])*rear_surface_fraction


def lateral_transient(layers, time_s, source_power_W, plate_height_in=6,
                      plate_width_in=2, heated_height_in=3,
                      h_W_m2K=15., ambient_C=25., added_contact_rpp=0.,
                      mica_density_scale=1., n_stripes=60):
    """Coupled through-thickness layer + in-plane aluminum dynamic RC model.

    6-inch height divided into n_stripes parallel heated columns. Each column
    has a through-thickness thermal RC network. Adjacent columns connect through
    the aluminum sheet ONLY (because its in-plane k*t dwarfs fabric/mica).
    The heater supplies constant flux to a centered 3-inch patch across full
    plate width. Side edges are adiabatic, the back convects uniformly.
    This captures approximate *position-dependent rear thermocouple temperature*
    and is preferable to the isolated-heated-area transient when aluminum
    is used as a spreader.
    """
    nlayer = len(layers)
    n = n_stripes
    dx = plate_height_in * INCH / n
    W = plate_width_in * INCH
    area = dx * W
    N = n * nlayer
    x = (np.arange(n) + 0.5) * dx
    active = np.abs(x - plate_height_in * INCH / 2) < heated_height_in * INCH / 2
    Q = np.zeros(N)
    Q[np.flatnonzero(active) * nlayer] = source_power_W / active.sum()
    C = np.zeros(N)
    K = lil_matrix((N, N), dtype=float)

    def connect(i, j, conductance):
        K[i, i] += conductance
        K[j, j] += conductance
        K[i, j] -= conductance
        K[j, i] -= conductance

    for strip in range(n):
        base = strip * nlayer
        for j, m in enumerate(layers):
            C[base + j] = m.rho * m.cp * m.thickness * area * (
                mica_density_scale if m.name == 'Mica' else 1.0)
        for j in range(nlayer - 1):
            rr = (layers[j].thickness / (2 * layers[j].k * area) +
                  layers[j+1].thickness / (2 * layers[j+1].k * area))
            if nlayer == 3 and j == 1:
                rr += added_contact_rpp / area
            connect(base + j, base + j + 1, 1/rr)
        rback = (layers[-1].thickness / (2*layers[-1].k*area)
                 + 1 / (h_W_m2K * area))
        K[base + nlayer - 1, base + nlayer - 1] += 1 / rback
        # Aluminum's in-plane coupling between columns
        if nlayer == 3 and strip < n-1:
            g_lateral = ALUMINUM.k * ALUMINUM.thickness * W / dx
            connect(base + 2, base + nlayer + 2, g_lateral)
    K = K.tocsc()
    M = -diags(1/C, format='csc') @ K
    drive = Q / C
    sol = solve_ivp(lambda tt,y: M @ y + drive,
                    (float(time_s[0]), float(time_s[-1])),
                    np.zeros(N), t_eval=time_s, method='BDF',
                    jac=M, rtol=3e-7, atol=1e-8)
    if not sol.success:
        raise RuntimeError('RC simulation failed: '+sol.message)
    mid_strip = n // 2
    convection_R = 1/(h_W_m2K*area)
    rear_surface_fraction = convection_R / (convection_R +
                              layers[-1].thickness / (2 * layers[-1].k*area))
    return ambient_C + sol.y[mid_strip*nlayer+nlayer-1, :] * rear_surface_fraction


def first_crossing(times, curve, target):
    if target <= curve[0]:
        return 0.0
    idx = np.flatnonzero(curve >= target)
    if not len(idx):
        return float('nan')
    i = int(idx[0])
    if i == 0:
        return float(times[i])
    return float(np.interp(target, curve[i - 1:i + 1], times[i - 1:i + 1]))


def lateral_aluminum_profile(power_into_stack_W, h, heated_height_in=3,
                             plate_height_in=6, plate_width_in=2, n=401,
                             ambient_C=25):
    """ILLUSTRATIVE spatial 1D aluminum spreading model.
    Steady-state: -k_Al*t_Al*d2T/dx2 + h*(T-Ta) = q''(x)
    On a 6-in-tall vertical strip; insulated top/bottom, full width heated across
    centered heated-height window, convective losses rear. Ignores mica/basalt
    in-plane conduction, variable through-layer driving temperature and side losses.
    The no-Al reference assumes zero in-plane spreading (limiting case).
    """
    H, W = plate_height_in * INCH, plate_width_in * INCH
    dx = H / n
    x = (np.arange(n) + 0.5) * dx
    heated_h = heated_height_in * INCH
    active = np.abs(x - H / 2) < heated_h / 2
    qpp = np.zeros(n)
    qpp[active] = power_into_stack_W / (active.sum() * dx * W)
    bare = ambient_C + qpp / h

    inplane = ALUMINUM.k * ALUMINUM.thickness
    d = np.full(n, h + 2 * inplane / dx**2)
    d[0] = d[-1] = h + inplane / dx**2  # no-flux outer edges
    off = np.full(n - 1, -inplane / dx**2)
    D = diags([off, d, off], [-1, 0, 1], format='csc')
    aluminum = ambient_C + spsolve(D, qpp)
    return x / INCH, bare, aluminum


def load_measurements(filename):
    if not filename or not Path(filename).exists():
        return []
    out = []
    with open(filename, newline='', encoding='utf8') as f:
        for r in csv.DictReader(f):
            if (r.get('TC_C', '').strip() and r.get('time_s', '').strip()
                    and r.get('config', '').strip()):
                try:
                    out.append(dict(run=r.get('run', ''),
                                    config=r['config'].strip().lower(),
                                    time_s=float(r['time_s']),
                                    TC_C=float(r['TC_C']),
                                    power_W=float(r.get('power_W', '20') or 20)))
                except ValueError:
                    pass
    return out


def make_figures(out_dir, power=20, coupling=0.30, h=15.0,
                 heater_width_in=2.0, heater_height_in=3.0,
                 target=100.0, ambient=25.0, contact_rpp=0.0,
                 mica_density_scale=1.0, measurements=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    active_area = heater_width_in * heater_height_in * INCH**2
    t = np.arange(0.0, 1800.1, 2.0)
    measurements = measurements or []

    # Figure 1 — resistance, and the difference between R and effective k.
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.2), constrained_layout=True)
    r = [layer_resistance(m, FULL_AREA) for m in WITH_AL]
    for i, (material, val) in enumerate(zip(WITH_AL, r)):
        axes[0].barh(material.name, val)
        axes[0].text(val + 0.014, i, f'{val:.6f}', va='center', fontsize=9)
    axes[0].set_xlim(0, max(r) * 1.4)
    axes[0].set_xlabel('Individual through-thickness resistance (K/W)')
    axes[0].set_title('6 × 2 in plate: individual material resistances')
    names = ['Mica + basalt', 'Mica + basalt + Al']
    vals = [effective_k(BARE, FULL_AREA), effective_k(WITH_AL, FULL_AREA)]
    axes[1].bar(names, vals)
    for i, v in enumerate(vals):
        axes[1].text(i, v + 0.005, f'{v:.5f}', ha='center')
    axes[1].set_ylim(0, 0.44)
    axes[1].set_ylabel('Effective k of the stack (W/m/K)')
    axes[1].set_title('Effective k rises because the stack becomes thicker')
    fig.suptitle('Aluminum adds just 0.0232% to ideal total conduction resistance')
    fig.savefig(out_dir / '01_conduction_comparison.png', dpi=175)
    plt.close(fig)

    # Precompute center thermocouple response per watt of heat INTO stack.
    # These 2D RC results allow lateral heat spreading in aluminum.
    base_b = lateral_transient(BARE, t, 1.0, HEIGHT_IN, WIDTH_IN,
                               heater_height_in, h, 0., mica_density_scale=mica_density_scale)
    base_a = lateral_transient(WITH_AL, t, 1.0, HEIGHT_IN, WIDTH_IN,
                               heater_height_in, h, 0., contact_rpp,
                               mica_density_scale=mica_density_scale)
    # Also compute idealized 1D result to expose the area-uniformity assumption.
    base_a_1d = transient(WITH_AL, t, 1.0, active_area, h, 0.,
                          added_contact_rpp=contact_rpp,
                          mica_density_scale=mica_density_scale)

    # Figure 2 — baseline 20 W plus multiple power scenarios.
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 5), constrained_layout=True)
    basic_power = [5, 10, 20, 40]
    for p in basic_power:
        bare_trace = ambient + coupling * p * base_b
        al_trace = ambient + coupling * p * base_a
        line, = ax1.plot(t / 60, bare_trace, label=f'{p:g} W (no Al)')
        ax1.plot(t / 60, al_trace, linestyle='--', color=line.get_color(),
                 label=f'{p:g} W (+ Al)')
    ax1.set_xlabel('Time after turning heater on (min)')
    ax1.set_ylabel('Predicted rear thermocouple temperature (°C)')
    ax1.set_title('Rear thermocouple temperature by electrical power')
    ax1.legend(fontsize=8, ncol=2)
    ax1.grid(alpha=0.25)

    b = ambient + coupling * power * base_b
    a = ambient + coupling * power * base_a
    ax2.plot(t / 60, b, label='No aluminum')
    ax2.plot(t / 60, a, label='+ Al (with lateral spreading)')
    ax2.plot(t / 60, ambient + coupling*power*base_a_1d, ':',
             label='+ Al (uniform 1D only)')
    if target > ambient:
        ax2.axhline(target, ls=':', label=f'Target {target:g}°C')
    for cfg, trace in [('bare', b), ('aluminum', a)]:
        time_hit = first_crossing(t, trace, target)
        print(f'  {cfg:8}: first reach {target:g} C = '
              f'{time_hit/60:.2f} min' if np.isfinite(time_hit) else
              f'  {cfg:8}: target not reached within 30 min')
    for config, label in [('bare', 'Measured, no Al'),
                          ('aluminum', 'Measured, with Al')]:
        subset = [z for z in measurements if z['config'] == config
                  and np.isclose(z['power_W'], power)]
        if subset:
            ax2.scatter([z['time_s']/60 for z in subset],
                        [z['TC_C'] for z in subset], s=15, alpha=0.8,
                        label=label)
    ax2.set_xlabel('Time after turning heater on (min)')
    ax2.set_ylabel('Predicted or measured thermocouple temperature (°C)')
    ax2.set_title(f'{power:g} W electrical; {100*coupling:.0f}% assumed enters sample')
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle(f'Coupled through-layer + aluminum spreading RC | heated patch = {heater_height_in:g} × '
                 f'{heater_width_in:g} in | h = {h:g} W/m²K | ambient = {ambient:g}°C')
    fig.savefig(out_dir / '02_thermocouple_vs_time.png', dpi=175)
    plt.close(fig)

    # Figure 3 — time to reach targets as a function of heater power.
    powers = np.arange(3, 61, 1)
    targets = [50, 100, 150]
    fig, ax = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    for Ttarget in targets:
        results_b = [first_crossing(t, ambient + coupling * p * base_b, Ttarget) / 60
                     for p in powers]
        results_a = [first_crossing(t, ambient + coupling * p * base_a, Ttarget) / 60
                     for p in powers]
        line, = ax.plot(powers, results_b, label=f'{Ttarget}°C target — no Al')
        ax.plot(powers, results_a, '--', color=line.get_color(),
                label=f'{Ttarget}°C target — with Al')
    ax.set_xlabel('Electrical cartridge heater power (W)')
    ax.set_ylabel('Time to reach target (min)')
    ax.set_ylim(0, 30)
    ax.set_xlim(3, 60)
    ax.set_title('Time to rear thermocouple threshold | NaN = not reached within 30 min')
    ax.grid(alpha=0.25)
    ax.legend(ncol=2, fontsize=8)
    fig.savefig(out_dir / '03_time_to_targets.png', dpi=175)
    plt.close(fig)

    # Figure 4 — illustrative 6in x 2in rear-surface lateral spreading.
    x, no_spread, spread = lateral_aluminum_profile(
        power * coupling, h, heater_height_in, HEIGHT_IN, WIDTH_IN, ambient_C=ambient)
    fig, ax = plt.subplots(figsize=(10, 4.7), constrained_layout=True)
    ax.plot(x, no_spread, '--', label='Without Al: no lateral spreading (limit)')
    ax.plot(x, spread, label='With Al: 1D sheet-spreading approximation')
    center = HEIGHT_IN / 2
    ax.axvspan(center - heater_height_in/2, center + heater_height_in/2,
               alpha=0.12, label='3-in heater footprint (centered)')
    ax.set_xlabel('Position along 6-inch plate height (in)')
    ax.set_ylabel('Predicted steady rear-surface temperature (°C)')
    ax.set_title('Aluminum can alter local thermocouple temperature despite tiny through-thickness R')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    fig.savefig(out_dir / '04_aluminum_spreading_illustration.png', dpi=175)
    plt.close(fig)
    print(f'  Spreading model at {power:g}W: center T w/o Al = '
          f'{no_spread[len(x)//2]:.1f} C; w Al = {spread[len(x)//2]:.1f} C')

    # Figure 5 — interface contact can swamp aluminum's own R.
    rpp = np.linspace(0, .0008, 201)
    rbase = stack_resistance(BARE, FULL_AREA)
    pct = 100 * ((stack_resistance(WITH_AL, FULL_AREA) + rpp / FULL_AREA) / rbase - 1)
    fig, ax = plt.subplots(figsize=(9.6, 4.5), constrained_layout=True)
    ax.plot(rpp * 1e4, pct, label='Extra interface + aluminum')
    ax.axhline(100*(stack_resistance(WITH_AL, FULL_AREA)/rbase-1), ls='--',
               label='Aluminum itself, ideal interface (0.0232%)')
    ax.set_xlabel('Added aluminum-interface area-specific resistance (×10⁻⁴ m² K/W)')
    ax.set_ylabel('Increase in stack thermal resistance (%)')
    ax.set_title('Small contact resistance matters far more than aluminum bulk resistance')
    ax.legend()
    ax.grid(alpha=.25)
    fig.savefig(out_dir / '05_interface_contact_sensitivity.png', dpi=175)
    plt.close(fig)

    # Machine-readable model results.
    with open(out_dir / 'thermal_predictions.csv', 'w', newline='', encoding='utf8') as f:
        w = csv.writer(f)
        w.writerow(['time_s', 'electrical_power_W', 'effective_power_W',
                    'bare_TC_C', 'aluminum_TC_C', 'ambient_C', 'heated_area_m2',
                    'h_W_m2K', 'assumed_coupling_fraction'])
        for p in [5, 10, 20, 40, 60]:
            bb = ambient + coupling * p * base_b
            aa = ambient + coupling * p * base_a
            for i in range(0, len(t), 5):
                w.writerow([f'{t[i]:.0f}', p, f'{coupling*p:.4f}',
                            f'{bb[i]:.5f}', f'{aa[i]:.5f}', ambient,
                            f'{active_area:.7f}', h, coupling])

    template = out_dir / 'measurements_template.csv'
    if not template.exists():
        with open(template, 'w', newline='', encoding='utf8') as f:
            w = csv.writer(f)
            w.writerow(['run', 'config', 'time_s', 'power_W', 'TC_C', 'ambient_C'])
            for config in ('bare', 'aluminum'):
                for run in (1, 2, 3):
                    for tm in range(0, 1801, 30):
                        w.writerow([run, config, tm, power, '', ambient])

    if measurements:
        print('\nMeasurement comparison at exactly the configured power:')
        for cfg, model_trace in [('bare', b), ('aluminum', a)]:
            grouped = {}
            for m in measurements:
                if m['config'] == cfg and np.isclose(m['power_W'], power):
                    grouped.setdefault(m['run'], []).append(m)
            for run, values in grouped.items():
                observed = np.array([z['TC_C'] for z in values])
                predicted = np.interp([z['time_s'] for z in values], t, model_trace)
                rmse = np.sqrt(np.mean((observed-predicted)**2))
                print(f'  {cfg:8} run {run}: {len(values)} points, RMSE {rmse:.2f} C')


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--power', type=float, default=20., help='electrical heater power (W)')
    p.add_argument('--coupling', type=float, default=0.30,
                   help='fraction of electrical power conducted INTO sample (0..1)')
    p.add_argument('--h', type=float, default=15.,
                   help='effective rear heat-transfer coefficient W/m²K')
    p.add_argument('--ambient', type=float, default=25., help='initial and ambient temp C')
    p.add_argument('--heater-width-in', type=float, default=2.,
                   help='assumed heater contact footprint width (in), UNKNOWN in experiment')
    p.add_argument('--heater-height-in', type=float, default=3.,
                   help='assumed heated footprint height (in)')
    p.add_argument('--target', type=float, default=100., help='thermocouple target C')
    p.add_argument('--contact-rpp', type=float, default=0.,
                   help='area-specific resistance at basalt/aluminum interface (m² K/W)')
    p.add_argument('--mica-density-scale', type=float, default=1.,
                   help='1=McMaster listed 0.2 lb/in³; 0.5 ≈ natural mica density')
    p.add_argument('--measurements', type=str, default='',
                   help='optional CSV with TC_C filled to overlay and assess RMSE')
    p.add_argument('--out', type=Path, default=Path(__file__).resolve().parent,
                   help='output folder')
    args = p.parse_args()
    assert 0 < args.coupling <= 1
    assert args.h > 0 and args.power > 0
    assert 0 < args.heater_width_in <= WIDTH_IN
    assert 0 < args.heater_height_in <= HEIGHT_IN
    if not np.isclose(args.heater_width_in, WIDTH_IN):
        p.error('Current vertical-stripe simulation requires full 2-inch heater width; '
                'a narrower cartridge contact needs a full 2D in-plane model.')
    print('SOURCE DIMENSIONS AND 1D RESISTANCES')
    print(f'  full area = {FULL_AREA:.8f} m², heated area assumed = '
          f'{args.heater_width_in*args.heater_height_in*INCH**2:.8f} m²')
    for mat in WITH_AL:
        print(f'  {mat.name:18}: t = {mat.thickness*1000:.6f} mm; '
              f'k = {mat.k:.6g} W/mK; R = {layer_resistance(mat,FULL_AREA):.9f} K/W; '
              f'C_full = {mat.rho*mat.cp*mat.thickness*FULL_AREA:.3f} J/K')
    R0, R1 = stack_resistance(BARE, FULL_AREA), stack_resistance(WITH_AL,FULL_AREA)
    print(f'  bare R = {R0:.9f} K/W; Al R = {R1:.9f} K/W')
    print(f'  increase = {100*(R1/R0-1):.6f}%; '
          f'k_eff bare = {effective_k(BARE,FULL_AREA):.7f}, '
          f'with Al = {effective_k(WITH_AL,FULL_AREA):.7f} W/mK')
    print('\nTRANSIENT FORECAST (ASSUMPTIONS, NOT MEASURED)')
    make_figures(args.out, args.power, args.coupling, args.h,
                 args.heater_width_in, args.heater_height_in,
                 args.target, args.ambient, args.contact_rpp,
                 args.mica_density_scale, load_measurements(args.measurements))
    print(f'\nFiles saved to: {args.out}')

if __name__ == '__main__':
    main()
