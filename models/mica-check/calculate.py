#!/usr/bin/env python3
"""Conditional first-check calculations; no apparatus control or temperature forecast.

Run: python calculate.py [--inputs inputs.json] [--out OUTPUT_DIRECTORY]
All source values and analyst-selected scenarios are in the input JSON.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

HERE = Path(__file__).resolve().parent
COLORS = ("#2463a6", "#d87824", "#24877b")


def table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(map(str, row)) + " |" for row in rows),
    ])


def csv_file(path, headers, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=HERE / "inputs.json")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    config = json.loads(args.inputs.read_text())
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    specified = config["specified"]
    value = lambda name: float(specified[name]["value"])
    inch = value("inch_m")
    width = config["user_reported"]["sample_width_in"]["value"] * inch
    height = config["user_reported"]["sample_height_in"]["value"] * inch
    thickness = value("mica_thickness_in") * inch
    tolerance = value("mica_thickness_tolerance_in") * inch
    k = value("mica_k_w_mk")
    rated_v, rated_p = value("heater_voltage_v"), value("heater_power_w")
    if min(width, height, thickness, k, rated_v, rated_p) <= 0 or not 0 <= tolerance < thickness:
        raise ValueError("Positive dimensions, ratings and conductivity required; check thickness tolerance")
    resistance_electric = rated_v**2 / rated_p
    area = width * height
    cases = [
        ("Full 2 × 6 in face", area),
        ("Diameter × element envelope", value("heater_diameter_in") * value("heater_envelope_length_in") * inch**2),
        ("Diameter × heated length", value("heater_diameter_in") * value("heater_heated_length_in") * inch**2),
    ]
    scenarios = config["scenarios"]
    voltage_rows = [(float(v), v / resistance_electric, v**2 / resistance_electric) for v in scenarios["voltage_table_v"]]
    area_rows = [(label, a, thickness / (k * a)) for label, a in cases]
    heat_rows = [(label, q, q * thickness / (k * a)) for label, a in cases for q in scenarios["net_heat_table_w"]]
    conditional_rows = []
    for v, current, power in voltage_rows:
        for fraction in scenarios["heat_fraction_table"]:
            for label, a, r in area_rows:
                conditional_rows.append((v, power, fraction, label, a, power * fraction, power * fraction * r))
    electronics_per_channel = value("converter_gain_offset_limit_c") + value("converter_cjc_limit_c")
    electronics_difference = 2 * electronics_per_channel
    csv_file(out / "electrical.csv", ["voltage_rms_V", "nominal_current_A", "nominal_electrical_W"], voltage_rows)
    csv_file(out / "geometry.csv", ["scenario", "assumed_area_m2", "mica_R_K_per_W"], area_rows)
    csv_file(out / "conditional.csv", ["voltage_rms_V", "nominal_electrical_W", "assumed_heat_fraction", "area_scenario", "assumed_area_m2", "assumed_cross_mica_W", "predicted_mica_delta_C"], conditional_rows)
    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "inputs_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sources": config["sources"],
        "nominal_heater_resistance_ohm": resistance_electric,
        "mica_thickness_m": thickness,
        "mica_full_area_m2": area,
        "full_area_R_K_W": thickness / (k * area),
        "full_area_R_thickness_tolerance_only_K_W": [(thickness - tolerance) / (k * area), (thickness + tolerance) / (k * area)],
        "electronics_terms_per_channel_C": electronics_per_channel,
        "electronics_terms_difference_C": electronics_difference,
        "area_scenarios": [{"label": label, "area_m2": a, "R_K_W": r} for label, a, r in area_rows],
        "assumptions": scenarios["note"],
        "no_absolute_temperature_or_time_prediction": "Unknown true contact/spreading area, cross-sample heat fraction, contact drops, heat capacities and boundary losses prevent a defensible apparatus temperature/time forecast.",
    }
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "figure.facecolor": "white", "savefig.facecolor": "white"})

    def figure(title, subtitle):
        fig, ax = plt.subplots(figsize=(9.2, 5.4), layout="constrained")
        fig.suptitle(title, fontsize=15, fontweight="bold")
        ax.set_title(subtitle, fontsize=10, fontweight="normal", pad=12)
        ax.grid(alpha=.16)
        return fig, ax

    fig, ax = figure("Variac voltage is not heater power", "S1: 300 W at 120 V → constant nominal resistance model; NOT safe-setting guidance")
    voltages = np.linspace(0, rated_v, 301)
    ax.plot(voltages, voltages**2 / resistance_electric, color=COLORS[0], lw=2.5)
    ax.scatter([v for v, _, _ in voltage_rows], [p for _, _, p in voltage_rows], color=COLORS[0], s=25)
    ax.set(xlabel="Voltage across heater load (V RMS)", ylabel="Nominal electrical power (W)", xlim=(0, rated_v), ylim=(0, rated_p * 1.06))
    fig.savefig(out / "power.png", dpi=150)
    plt.close(fig)

    fig, ax = figure("Mica temperature drop depends strongly on assumed area", "S2 + S10: ΔT = Q L/(k A); steady, uniform 1D conduction\nProjection rectangles are illustrations, NOT measured contact areas or physical bounds.")
    heat = np.linspace(0, scenarios["plot_net_heat_max_w"], 150)
    for (label, a, r), color in zip(area_rows, COLORS):
        ax.plot(heat, heat * r, label=f"{label} · {r:.3f} K/W", color=color, lw=2.4)
    ax.set(xlabel="NET heat crossing mica (W) — not total heater input", ylabel="Conditional face-to-face difference (°C)", xlim=(0, heat[-1]), ylim=(0, None))
    ax.legend(frameon=False, loc="upper left", fontsize=10)
    fig.savefig(out / "area.png", dpi=150)
    plt.close(fig)

    fig, ax = figure("A catalog match can happen for the wrong reasons", "If k_app = P L/(A_full ΔT), then k_app/k_true = (A_effective/A_full)/η")
    ratios = np.geomspace(.01, 1, 151)
    fractions = np.geomspace(.01, 1, 151)
    x, y = np.meshgrid(ratios, fractions)
    image = ax.pcolormesh(x, y, np.log10(x / y), shading="auto", cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-2, vcenter=0, vmax=2), rasterized=True)
    ax.plot(ratios, ratios, "--", lw=2, color="#202020", label="Apparent catalog match: η = area ratio")
    ax.set(xscale="log", yscale="log", xlabel="Assumed effective area / full sheet area", ylabel="Assumed heat fraction η = Q_mica / P_electrical", xlim=(.01, 1), ylim=(.01, 1))
    bar = fig.colorbar(image, ax=ax, ticks=[-2, -1, 0, 1, 2])
    bar.ax.set_yticklabels(["0.01×", "0.1×", "1×", "10×", "100×"])
    bar.set_label("Apparent / true conductivity")
    ax.legend(frameon=True, facecolor="white", framealpha=.9, fontsize=9, loc="upper left")
    fig.savefig(out / "ambiguity.png", dpi=150)
    plt.close(fig)

    example_v = scenarios["example_voltage_v"]
    example_power = example_v**2 / resistance_electric
    selected = [row for row in conditional_rows if row[0] == example_v and row[2] in scenarios["heat_fraction_table"]]
    report = [
        "# Executed mica-check calculations",
        "Conditional scenarios only. No measured heating data were supplied; no power setting is approved here.",
        "## Reproduce / change assumptions",
        "`python models/mica-check/calculate.py` regenerates this report, CSVs, JSON and plots. Edit `inputs.json`, or use `--inputs PATH --out DIRECTORY`. Sources: [source index](../../docs/current-check-sources.md). All geometry projections and heat fractions below are assumptions, not fits.",
        "Dependencies are numpy and matplotlib. On NixOS: `nix-shell -p 'python3.withPackages (p: [p.numpy p.matplotlib])' --run 'python models/mica-check/calculate.py'`.",
        "## Electrical input — S1",
        f"From the heater rating, R_nom = V_rated²/P_rated = **{resistance_electric:g} Ω**. Constant R is an approximation, not a resistance measurement. Actual current and power depend on the real heater and source. Table voltages are load RMS voltages, not dial positions.",
        table(["V RMS", "Nominal A", "Nominal W"], [(f"{v:g}", f"{i:.4f}", f"{p:.4f}") for v, i, p in voltage_rows]),
        "![Electrical power](power.png)",
        "## Mica benchmark — S2 + user geometry S10",
        f"L = **{thickness * 1000:.4f} mm**, k = **{k:g} W/(m·K)**, full face A = **{area:.8f} m²**. The 1D full-face resistance is **{thickness / (k * area):.6f} K/W**. Thickness tolerance alone gives **{(thickness - tolerance) / (k * area):.6f}–{(thickness + tolerance) / (k * area):.6f} K/W**; this is not a full uncertainty interval.",
        table(["Assumed area scenario", "Area (m²)", "R (K/W)"], [(label, f"{a:.8f}", f"{r:.6f}") for label, a, r in area_rows]),
        "A cylinder touching a flat sheet does not make uniform contact across its diameter. Diameter × length is only a projection rectangle. Full face, envelope projection, and heated-length projection are NOT known bounds on the real plate/contact problem. Spreading/contact losses can invalidate each 1D approximation.",
        table(["Area scenario", "Net crossing heat (W)", "Conditional ΔT (°C)"], [(label, f"{q:g}", f"{delta:.4f}") for label, q, delta in heat_rows]),
        "![Area sensitivity](area.png)",
        f"## Example only: {example_v:g} V RMS → {example_power:.4f} W nominal electrical input",
        "η is an arbitrary illustration of the fraction crossing the mica. These rows are not a probable range, upper/lower experimental bound, recommended operating point or safe temperatures.",
        table(["Area scenario", "Assumed η", "Crossing W", "Conditional ΔT (°C)"], [(row[3], f"{row[2]:g}", f"{row[5]:.4f}", f"{row[6]:.4f}") for row in selected]),
        "Neither surface temperature follows from ΔT alone. A sheath-mounted hot TC also includes unknown heater-to-mica contact effects. No absolute surface, sheath or element temperature is predicted.",
        "## Why air versus sand cannot establish k by closeness alone",
        "Let Q_mica = ηP and let the true effective area be A_eff. Under the ideal 1D relation, ΔT = ηP L/(k_true A_eff). If electrical P and full sheet area are used to infer conductivity, k_app/k_true = A_eff/(η A_full). Many wrong area/heat-fraction pairs therefore give a catalog-looking result. Contact drops and multidimensional paths add further ambiguity. This is an algebraic sensitivity illustration, not an inverse fit to this apparatus. [Plane-wall relation](https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node118.html).",
        "![Catalog-match ambiguity](ambiguity.png)",
        "## Resolution versus partial error limits — S8",
        f"Output step: **{value('converter_resolution_c'):g}°C**. Adding the listed gain/offset and cold-junction terms conservatively gives **±{electronics_per_channel:g}°C per channel**, or **±{electronics_difference:g}°C for a difference of two channels** under the cited temperature conditions. This is a partial worst-case electronics budget, NOT a confidence interval or total probe accuracy. It excludes probe tolerance, mounting/contact offsets, thermocouple nonlinearity, spatial gradients and other effects. Correlated terms may cancel in a matched comparison, but that must not be assumed. Repeatability and a co-location/reference check can characterize observed mismatch; averaging does not remove systematic errors.",
        "## What is reasonable to look for in the first check?",
        "Look for saved, correctly labeled finite readings; stable reference/co-location behavior; the directly heated location responding when controlled input changes; a reproducible lag/difference at the other location; and continued logging through cooldown. A brief sign reversal during cooldown need not mean the channels are swapped. These are diagnostic patterns, not a numerical pass band. TCs can miss the hottest point, so their readings cannot guarantee heater safety.",
        "The code intentionally does NOT produce time-to-temperature or a target variac setting. Conductivity alone gives neither heat capacity nor boundary losses. True contact geometry, initial state, heat-flow partition, moisture, support conduction and surface/contact temperatures are missing. A fitted curve could describe a run, but would not independently validate k or sensor accuracy.",
        "## Saved evidence",
        "`electrical.csv`, `geometry.csv`, `conditional.csv`, `results.json`, `power.png`, `area.png`, `ambiguity.png`. JSON records executed script/input hashes and source URLs. Original source PDFs are indexed in `../../docs/current-check-sources.md`. These artifacts are calculations, not raw acquired runs.",
    ]
    text = "\n\n".join(report) + "\n"
    (out / "results.md").write_text(text)
    summary = f"Executed {Path(__file__).name}\nR_nom = {resistance_electric:g} ohm\nFull-face mica R = {thickness / (k * area):.9f} K/W\nPartial electronics difference bound = +/-{electronics_difference:g} C\nSources: " + "; ".join(f"{name}: {source['url']}" for name, source in config["sources"].items()) + f"\nOutputs: {out}\nNo absolute temperature/time forecast or safe setting inferred.\n"
    (out / "run.log").write_text(summary)
    print(summary, end="")


if __name__ == "__main__":
    main()
