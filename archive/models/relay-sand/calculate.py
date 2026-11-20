#!/usr/bin/env python3
"""Read-only experiment analysis and explicit sensitivities; NEVER controls hardware.

Standard library for all calculations. --plot additionally needs matplotlib.
No fitted hold voltage, unrecorded input transition, or sensor identity is invented.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def table(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def slope(points):
    xm = statistics.mean(x for x, _ in points)
    ym = statistics.mean(y for _, y in points)
    return sum((x - xm) * (y - ym) for x, y in points) / sum((x - xm) ** 2 for x, _ in points)


def channel_summary(rows, key):
    values = [(float(r['host_elapsed_s']), float(r[key])) for r in rows]
    good = [(t, y) for t, y in values if math.isfinite(y)]
    if not good:
        return {'finite': 0, 'faults': len(rows)}
    peak_t, peak_y = max(good, key=lambda pair: pair[1])
    # One epoch, >=9.3 s coverage, >=15 finite samples, no internal gap >1.3 s.
    # These are descriptive rolling regressions, NOT actuator step-response fits.
    windows = []
    for i, (start, _) in enumerate(good):
        points = []
        for point in good[i:]:
            if point[0] > start + 10:
                break
            points.append(point)
        if (len(points) >= 15 and points[-1][0] - start >= 9.3
                and max(b[0] - a[0] for a, b in zip(points, points[1:])) <= 1.3):
            windows.append((slope(points), start, points[-1][0]))
    result = {'finite': len(good), 'faults': len(rows) - len(good),
              'peak_C': peak_y, 'peak_host_s': peak_t,
              'first_C': good[0][1], 'last_C': good[-1][1]}
    if windows:
        rate, start, stop = max(windows)
        result['max_10s_OLS_C_s'] = rate
        result['max_10s_window_host_s'] = [start, stop]
    result['first_observed_crossing_host_s'] = {
        str(target): next((t for t, y in good if y >= target), None)
        for target in (50, 100, 150, 200, 250)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=HERE / 'inputs.json')
    parser.add_argument('--run', type=Path, default=ROOT / 'runs/006/data.csv')
    parser.add_argument('--out', type=Path, default=HERE)
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    cfg = json.loads(args.inputs.read_text())
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(args.run.open()))
    if not rows or len({r['epoch'] for r in rows}) != 1:
        raise ValueError('Select one nonempty acquisition epoch; never fit across resets')
    times = [float(r['host_elapsed_s']) for r in rows]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Host elapsed time must strictly increase')
    summaries = {key: channel_summary(rows, key) for key in ('tc1_C', 'tc2_C')}
    pairs = [(float(r['host_elapsed_s']), float(r['tc1_C']), float(r['tc2_C']))
             for r in rows if math.isfinite(float(r['tc1_C'])) and math.isfinite(float(r['tc2_C']))]
    maxdiff = max(pairs, key=lambda r: abs(r[2] - r[1]))
    both_fault = sum(not math.isfinite(float(r['tc1_C'])) and not math.isfinite(float(r['tc2_C'])) for r in rows)
    h, d, sand = cfg['heater'], cfg['design'], cfg['sand_sensitivity']
    resistance = h['rated_V'] ** 2 / h['rated_W']
    # Local terminal voltage, not the variac dial and never a safety voltage.
    electric = [{'load_RMS_V': v, 'nominal_W': v*v/resistance,
                 'nominal_A': v/resistance, 'fraction_of_rated_power': (v/h['rated_V'])**2}
                for v in cfg['electrical_examples_V']]
    table(out / 'electrical.csv', electric)
    mica = cfg['mica']
    areas = {'whole_sheet': mica['width_m']*mica['height_m'],
             'diameter_times_envelope_length': h['diameter_m']*h['envelope_length_m'],
             'diameter_times_heated_length': h['diameter_m']*h['heated_length_m']}
    mica_rows = [{'projection_NOT_contact_area': name, 'area_m2': area,
                  'ideal_R_K_W': mica['thickness_m']/(mica['k_W_mK']*area)} for name, area in areas.items()]
    table(out / 'mica.csv', mica_rows)
    radial = []
    radius = h['diameter_m']/2
    for length in [h['heated_length_m'], h['envelope_length_m']]:
        for outer in sand['outer_radius_m']:
            for k in sand['effective_k_W_mK']:
                # Constant-k annular conduction. Ambient boundary at r_o is ASSUMED.
                conductance = 2*math.pi*k*length/math.log(outer/radius)
                power = conductance*(d['target_C']-d['ambient_C'])
                radial.append({'assumed_length_m': length, 'assumed_outer_radius_m': outer,
                               'assumed_k_W_mK': k, 'radial_G_W_K': conductance,
                               'radial_only_W_at_target': power,
                               'continuous_equivalent_V': math.sqrt(power*resistance),
                               'duty_if_60V_available': power/(60**2/resistance)})
    table(out / 'sand_conduction.csv', radial)
    capacity = []
    for theta in sand['volumetric_water_fraction']:
        cv = sand['dry_bulk_density_kg_m3']*sand['solid_cp_J_kgK'] + theta*sand['water_density_kg_m3']*sand['water_cp_J_kgK']
        for k in sand['effective_k_W_mK']:
            alpha = k/cv
            capacity.append({'assumed_water_volume_fraction': theta, 'assumed_k_W_mK': k,
                             'room_temp_Cv_J_m3K': cv, 'alpha_m2_s': alpha,
                             'sqrt_alpha_t_at_hold_m': math.sqrt(alpha*d['hold_s'])})
    table(out / 'sand_capacity.csv', capacity)
    evaporation = []
    for mass in sand['water_examples_kg']:
        sensible = mass*sand['water_cp_J_kgK']*(sand['boiling_C_at_1atm']-d['ambient_C'])
        latent = mass*sand['latent_J_kg_at_1atm']
        evaporation.append({'assumed_local_water_kg': mass, 'water_sensible_J': sensible,
                            'water_latent_J': latent, 'water_total_J': sensible+latent,
                            'equivalent_average_W_over_hold': (sensible+latent)/d['hold_s'],
                            'water_only_loss_free_time_at_60V_s': (sensible+latent)/(60**2/resistance)})
    table(out / 'evaporation.csv', evaporation)
    sw = cfg['switching_sensitivity']
    pulse = [{'on_V': v, 'pulse_s': seconds, 'assumed_C_J_K': c,
              'pulse_J': v*v/resistance*seconds, 'adiabatic_rise_C': v*v/resistance*seconds/c}
             for v in sw['on_voltage_V'] for seconds in sw['pulse_s'] for c in sw['assumed_capacity_J_K']]
    table(out / 'pulse_sensitivity.csv', pulse)
    rate = max(s['max_10s_OLS_C_s'] for s in summaries.values() if 'max_10s_OLS_C_s' in s)
    ramp_scaling = [{'V': v, 'conditional_scaled_C_s': rate*(v/sw['reference_ramp_scenario_voltage_V'])**2}
                    for v in cfg['electrical_examples_V']]
    # Only an illustration: user reported full voltage; actual run voltage was not logged.
    table(out / 'ramp_scaling_NOT_prediction.csv', ramp_scaling)
    cycles = [{'cycle_period_s': period, 'cycles_per_hold': d['hold_s']/period,
               'contact_transitions_per_hold': 2*d['hold_s']/period} for period in sw['cycle_period_s']]
    table(out / 'relay_cycles.csv', cycles)
    driver = cfg['relay_driver']
    worst_coil = driver['coil_V']/(driver['coil_R_ohm']*(1-driver['coil_R_tolerance_fraction']))
    base_resistor_current = (driver['assumed_gpio_high_V']-driver['assumed_VBE_max_V'])/driver['base_R_ohm']
    base_current = base_resistor_current-driver['assumed_VBE_max_V']/driver['base_pulldown_R_ohm']
    driver_result = {'nominal_coil_A': driver['coil_V']/driver['coil_R_ohm'],
                     'nominal_coil_W': driver['coil_V']**2/driver['coil_R_ohm'],
                     'low_resistance_coil_A_ignoring_transistor_drop': worst_coil,
                     'base_resistor_current_A_at_assumed_GPIO_V': base_resistor_current,
                     'base_current_A_after_pulldown': base_current,
                     'required_base_A_at_forced_beta': worst_coil/driver['forced_beta']}
    # Independent identities guard units and generated electrical/driver recommendations.
    assert math.isclose(resistance, 48.0)
    assert all(math.isclose(r['nominal_W'], r['load_RMS_V']*r['nominal_A']) for r in electric)
    assert base_current >= worst_coil/driver['forced_beta']
    assert base_resistor_current < 0.020
    result = {'executed_utc': datetime.now(timezone.utc).isoformat(),
              'source_run': str(args.run.resolve()),
              'run_sha256': hashlib.sha256(args.run.read_bytes()).hexdigest(),
              'inputs_sha256': hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'samples': len(rows), 'both_fault_samples': both_fault,
              'both_fault_percent': 100*both_fault/len(rows), 'channel_summary': summaries,
              'max_absolute_channel_difference': {'host_s': maxdiff[0], 'tc1_C': maxdiff[1], 'tc2_C': maxdiff[2], 'difference_C': abs(maxdiff[2]-maxdiff[1])},
              'nominal_R_ohm': resistance, 'relay_driver': driver_result,
              'design': d, 'actual_run_input_voltage_V': None,
              'actual_power_off_time_s': None, 'identified_hold_power_W': None,
              'identified_PI_gains': None,
              'assumptions': cfg, 'electrical': electric,
              'sand_radial_sensitivities': radial, 'water_sensitivities': evaporation,
              'conditional_ramp_scaling': ramp_scaling, 'switching_cycles': cycles}
    (out / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('assumptions', 'sand_radial_sensitivities')}, indent=2, allow_nan=False))
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(11, 8), layout='constrained', sharex=True,
                                 gridspec_kw={'height_ratios': [3, 1]})
        for key, label in [('tc1_C', 'TC1 — physical location unverified'), ('tc2_C', 'TC2 — physical location unverified')]:
            axes[0].plot(times, [float(r[key]) for r in rows], label=label, linewidth=1.6)
        axes[0].set(ylabel='Measured thermocouple reading (°C)', title='Run 006: measured mica-check trace, not a sand-packed model')
        axes[0].legend()
        axes[0].text(.99, .97, 'Input voltage and OFF timestamp absent\nNaNs preserved as gaps; channel location not inferred',
                     transform=axes[0].transAxes, ha='right', va='top', fontsize=9)
        faults = [float(r['host_elapsed_s']) for r in rows if not math.isfinite(float(r['tc1_C'])) or not math.isfinite(float(r['tc2_C']))]
        axes[1].vlines(faults, 0, 1, color='firebrick', linewidth=.8)
        axes[1].set(xlabel='Host elapsed time since recording start (s)', ylabel='Any TC fault', yticks=[0, 1], xlim=(0, times[-1]))
        for ax in axes:
            ax.grid(alpha=.2)
        fig.savefig(out / 'run006.png', dpi=150)
        plt.close(fig)
        print('Measured plot:', out / 'run006.png')


if __name__ == '__main__':
    main()
