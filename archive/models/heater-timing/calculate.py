#!/usr/bin/env python3
"""Calculate nominal 100 V power and explicit hypothetical thermal sensitivities.

No hardware access. No fit or prediction for an unmeasured apparatus.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent


def crossing_time(power, capacity, loss, initial, target):
    if capacity <= 0 or loss < 0 or power <= 0:
        raise ValueError("Require positive capacity/power and nonnegative loss")
    rise = target - initial
    if rise <= 0:
        return 0.0
    if loss == 0:
        return capacity * rise / power
    if power <= loss * rise:
        return None  # equality is asymptotic: no finite crossing
    return -(capacity / loss) * math.log1p(-loss * rise / power)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=HERE / "inputs.json")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    cfg = json.loads(args.inputs.read_text())
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    heater, example = cfg["sources"]["heater"], cfg["illustration"]
    resistance = heater["rated_voltage_V"] ** 2 / heater["rated_power_W"]
    voltage, target = cfg["requested_voltage_V"], cfg["requested_target_C"]
    power = voltage ** 2 / resistance
    initial = example["initial_and_ambient_C"]
    rise = target - initial
    if resistance <= 0 or rise <= 0:
        raise ValueError("This report requires a positive resistance and target above assumed initial temperature")
    coefficient = rise / power
    critical_loss = power / rise
    rows = []
    for capacity in example["effective_capacity_J_K"]:
        for loss in example["effective_linear_loss_W_K"]:
            seconds = crossing_time(power, capacity, loss, initial, target)
            rows.append({"assumed_capacity_J_K": capacity, "assumed_linear_loss_W_K": loss,
                         "assumed_loss_at_target_W": loss * rise,
                         "model_equilibrium_C": None if loss == 0 else initial + power / loss,
                         "model_time_to_target_s": seconds,
                         "reaches_in_finite_time": seconds is not None})
    with (out / "sensitivity.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inputs_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
        "nominal_R_ohm": resistance, "nominal_P_W": power,
        "nominal_I_A": voltage / resistance,
        "assumed_initial_C": initial, "requested_target_C": target,
        "adiabatic_seconds_per_J_per_K_capacity": coefficient,
        "linear_G_for_asymptotic_target_W_K": critical_loss,
        "real_apparatus_time_s": None,
        "reason_no_real_prediction": cfg["unknown_for_real_prediction"],
        "scenario_note": example["note"], "sources": cfg["sources"], "scenarios": rows,
    }
    (out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white"})
    fig, ax = plt.subplots(figsize=(9.2, 5.6), layout="constrained")
    fig.suptitle("100 V: hypothetical sensitivities, NOT a measured warm-up forecast", fontsize=14, fontweight="bold")
    capacity = example["plot_capacity_J_K"]
    ax.set_title(f"Assumed initial = {initial:g}°C; C_eff = {capacity:g} J/K; constant nominal input = {power:.2f} W", fontsize=10, pad=12)
    times = np.linspace(0, example["plot_horizon_s"], 1201)
    colors = ["#2463a6", "#d87824", "#24877b", "#a35188", "#66717d"]
    trace_rows = []
    for loss, color in zip(example["effective_linear_loss_W_K"], colors):
        temp = initial + (power * times / capacity if loss == 0 else (power / loss) * (-np.expm1(-loss * times / capacity)))
        ax.plot(times / 60, temp, color=color, lw=2.2, label=f"Assumed G = {loss:g} W/K")
        trace_rows.extend((t, loss, temperature) for t, temperature in zip(times, temp))
    ax.axhline(target, color="#333333", ls="--", lw=1.3, label=f"Requested {target:g}°C — not an approved setpoint")
    ax.set(xlabel="Illustrative model time (min)", ylabel="Lumped model temperature (°C)", xlim=(0, times[-1] / 60), ylim=(initial - 10, target * 1.25))
    ax.grid(alpha=.16)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.savefig(out / "sensitivity.png", dpi=150)
    plt.close(fig)
    with (out / "traces.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["model_time_s", "assumed_loss_W_K", "hypothetical_temperature_C"])
        writer.writerows(trace_rows)
    lines = [
        "# 100 V → 500°C: calculation record",
        "**No defensible apparatus time is available yet.** The table/figure below is a sensitivity illustration, not a probable range, measured trace, safe operating instruction or approved 500°C run.",
        "## Nominal electrical input",
        f"[Heater rating]({heater['url']}): {heater['rated_power_W']:g} W at {heater['rated_voltage_V']:g} V. R_nom = V_rated²/P_rated = **{resistance:g} Ω**. At **{voltage:g} V RMS**, nominal **P = {power:.6f} W**, **I = {voltage / resistance:.6f} A**, assuming constant resistance. Actual input must be measured.",
        "## Missing thermal information",
        "A lumped illustration is `C_eff dT/dt = P − G(T − T_ambient)`. Here C_eff and G are unmeasured. With initial temperature equal to ambient and constant inputs, `T(t) = T0 + (P/G)(1 − exp(−Gt/C_eff))`. For G=0, `T(t)=T0+Pt/C_eff`. [Energy-balance source](https://apmonitor.com/pdc/index.php/Main/PhysicsBasedModels); [first-order response source](https://apmonitor.com/pdc/index.php/Main/FirstOrderSystems).",
        f"For an **assumed {initial:g}°C start**, the loss-free expression is `t = {coefficient:.6f} × C_eff` seconds when C_eff is entered in J/K. This is only a no-loss result for that assumed lumped capacity, NOT a known minimum for your unmeasured TC location or fixture.",
        f"For the same assumed ambient, linear **G = {critical_loss:.6f} W/K** makes the equilibrium exactly {target:g}°C, approached only asymptotically. Higher G never reaches the target in this model. This illustrates that a time can be finite or nonexistent; it does not identify the actual loss.",
        "For temperature-dependent properties the corresponding energy-balance expression is `t = integral[C_eff(T)/(P(T) − Q_loss(T)) dT]`, provided net heating stays positive. Unknown radiation, conduction, moisture and sensor dynamics cannot be replaced by an invented constant G.",
        "## Arbitrary scenarios — NOT estimates of actual parameters",
        example["note"],
        "| Assumed C_eff (J/K) | Assumed G (W/K) | Loss at target (W) | Model time to target (s) |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        seconds = row["model_time_to_target_s"]
        lines.append(f"| {row['assumed_capacity_J_K']:g} | {row['assumed_linear_loss_W_K']:g} | {row['assumed_loss_at_target_W']:.3f} | {'Never' if seconds is None else f'{seconds:.3f}'} |")
    lines.extend([
        "\n![Clearly labeled hypothetical time traces](sensitivity.png)",
        "## Reproduce / records",
        "`python models/heater-timing/calculate.py` with numpy/matplotlib installed. NixOS: `nix-shell -p 'python3.withPackages (p: [p.numpy p.matplotlib])' --run 'python models/heater-timing/calculate.py'`. Edit `inputs.json`; `--inputs PATH --out DIRECTORY` is supported.",
        "Saved: `inputs.json`, `calculate.py`, `results.json`, `sensitivity.csv`, `traces.csv`, `sensitivity.png`, `run.log`. JSON records executed code/input hashes and source URLs. No raw experiment data, fitted model or actual controller tuning parameters are fabricated.",
        "Run plan and manual-versus-automatic control distinction: [heater-control-plan.md](../../docs/heater-control-plan.md).",
    ])
    table_start = next(i for i, line in enumerate(lines) if line.startswith("|"))
    table_end = table_start + 2 + len(rows)
    paragraphs = lines[:table_start] + ["\n".join(lines[table_start:table_end])] + lines[table_end:]
    (out / "results.md").write_text("\n\n".join(paragraphs) + "\n")
    log = (f"Executed at {result['executed_utc']}\nNominal R={resistance:g} ohm; V={voltage:g} V; P={power:.9f} W; I={voltage / resistance:.9f} A\n"
           f"Assumed T0={initial:g} C; target={target:g} C; no-loss t/C={coefficient:.9f} s/(J/K); critical linear G={critical_loss:.9f} W/K\n"
           "Actual apparatus time: NOT IDENTIFIABLE FROM AVAILABLE DATA\n"
           + "\n".join(f"Source {name}: {entry['url']}" for name, entry in cfg["sources"].items()) + "\n")
    (out / "run.log").write_text(log)
    print(log, end="")


if __name__ == "__main__":
    main()
