"""Score baseline KS lateral predictions and a ladder of improvements.

Primary metric: RMSE of yaw-rate prediction (rad/s) over all Ford segments,
weighted by sample count. Secondary: RMSE of lateral-accel prediction (m/s^2).

Attribution scheme: sequential ladder (cumulative). Each rung adds one change
on top of the previous. Reported delta = RMSE_prev - RMSE_this. Final-rung
"share of improvement" = delta / (RMSE_baseline - RMSE_final).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

# Wheelbases (from parameters.py) -- avoid importing code for cleanliness.
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}
# Steady-state single-track understeer params:
# K_us = (m / L) * (l_r / C_alpha_f - l_f / C_alpha_r)   [s^2/m]
ST_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": dict(
        m=2336.0, l_f=1.3130, l_r=1.671, C_f=286_551.0, C_r=355_912.0, L=2.984,
        kus_scale=0.5,
    ),
    "FORD_F_150_LIGHTNING_MK1": dict(
        m=3084.0, l_f=1.628, l_r=2.072, C_f=378_307.0, C_r=469_878.0, L=3.70,
        kus_scale=3.0,
    ),
}


def k_us(p: dict) -> float:
    return (p["m"] / p["L"]) * (p["l_r"] / p["C_f"] - p["l_f"] / p["C_r"])


def load_segment(csv_path: Path):
    rows = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    if rows.ndim == 1:
        return None
    if rows.shape[0] < 100:
        return None
    cols = {
        "t": rows[:, 0],
        "delta_road": rows[:, 2],
        "v": rows[:, 3],
        "a_lat_meas": rows[:, 5],
        "yaw_meas": rows[:, 6],
        "yaw_pred_base": rows[:, 14],
        "a_y_pred_base": rows[:, 15],
    }
    return cols


def iter_segments():
    for platform_dir in sorted(SIM.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name
        if platform not in L_BY_PLATFORM:
            continue
        for csv_path in sorted(platform_dir.rglob("sim.csv")):
            yield platform, csv_path


def yaw_pred(variant: str, c: dict, p: dict, bias_per_seg: float) -> np.ndarray:
    v = c["v"]
    delta = c["delta_road"]
    if variant == "baseline":
        # exactly the recorded baseline: (v / L) * tan(delta)
        return c["yaw_pred_base"]
    if variant == "v1_bias":
        delta_c = delta - bias_per_seg
        return (v / p["L"]) * np.tan(delta_c)
    if variant == "v2_understeer":
        delta_c = delta - bias_per_seg
        Kus = k_us(p)
        # steady-state bicycle: psi_dot = v * delta / (L + K_us * v^2)
        # use tan(delta) for large-angle consistency
        return (v * np.tan(delta_c)) / (p["L"] + Kus * v * v)
    if variant == "v3_lag":
        delta_c = delta - bias_per_seg
        # First-order steering lag, tau tuned by grid sweep (tools/tune.py).
        tau = 0.05  # s
        dt = np.median(np.diff(c["t"]))
        alpha = dt / (tau + dt)
        delta_eff = np.empty_like(delta_c)
        delta_eff[0] = delta_c[0]
        for k in range(1, len(delta_c)):
            delta_eff[k] = delta_eff[k - 1] + alpha * (delta_c[k] - delta_eff[k - 1])
        Kus = k_us(p)
        return (v * np.tan(delta_eff)) / (p["L"] + Kus * v * v)
    if variant == "v4_per_platform_kus":
        # Same as v3 but with platform-tuned K_us scale from grid search.
        # Mach-E: 0.5x carParams prior; F-150: 3.0x.  Tuned for yaw RMSE.
        delta_c = delta - bias_per_seg
        tau = 0.05
        dt = np.median(np.diff(c["t"]))
        alpha = dt / (tau + dt)
        delta_eff = np.empty_like(delta_c)
        delta_eff[0] = delta_c[0]
        for k in range(1, len(delta_c)):
            delta_eff[k] = delta_eff[k - 1] + alpha * (delta_c[k] - delta_eff[k - 1])
        scale = p.get("kus_scale", 1.0)
        Kus = scale * k_us(p)
        return (v * np.tan(delta_eff)) / (p["L"] + Kus * v * v)
    raise KeyError(variant)


def a_y_pred(variant: str, c: dict, p: dict, yaw_pred_arr: np.ndarray) -> np.ndarray:
    # KS-canonical: a_y = v * psi_dot. We let each variant inherit that.
    return c["v"] * yaw_pred_arr


def estimate_bias(c: dict) -> float:
    """Estimate steering-zero bias from straight-line driving.

    Use samples where |yaw_meas| < 0.02 rad/s and |a_lat_meas| < 0.3 m/s^2
    and v > 8 m/s as ~straight running; take median(delta_road).
    """
    v = c["v"]
    mask = (np.abs(c["yaw_meas"]) < 0.02) & (np.abs(c["a_lat_meas"]) < 0.3) & (v > 8.0)
    if mask.sum() < 50:
        return 0.0
    return float(np.median(c["delta_road"][mask]))


def main():
    variants = ["baseline", "v1_bias", "v2_understeer", "v3_lag", "v4_per_platform_kus"]
    # running sums of squared error and counts
    sse_yaw = {v: 0.0 for v in variants}
    sse_ay = {v: 0.0 for v in variants}
    n_tot = 0
    per_segment = []

    biases = []

    for platform, csv_path in iter_segments():
        c = load_segment(csv_path)
        if c is None:
            continue
        p = ST_BY_PLATFORM[platform]
        bias = estimate_bias(c)
        biases.append(bias)
        # In-motion mask: lateral dynamics only meaningful at non-trivial speed.
        # Below ~2 m/s the model's prediction is identically ~0 and the IMU
        # measurement is dominated by road grade / bumps -> dominates RMSE.
        mask = c["v"] > 2.0
        n_seg = int(mask.sum())
        if n_seg < 50:
            continue
        row = {"platform": platform, "csv": str(csv_path.relative_to(SIM)),
               "bias_rad": bias, "n_total": len(c["t"]), "n_used": n_seg}
        for v in variants:
            yp = yaw_pred(v, c, p, bias)
            ap = a_y_pred(v, c, p, yp)
            err_y = (yp - c["yaw_meas"])[mask]
            err_a = (ap - c["a_lat_meas"])[mask]
            sse_yaw[v] += float(np.sum(err_y * err_y))
            sse_ay[v] += float(np.sum(err_a * err_a))
            row[f"rmse_yaw_{v}"] = float(np.sqrt(np.mean(err_y * err_y)))
            row[f"rmse_ay_{v}"] = float(np.sqrt(np.mean(err_a * err_a)))
        n_tot += n_seg
        per_segment.append(row)

    summary = {
        "n_segments": len(per_segment),
        "n_samples": n_tot,
        "bias_stats_rad": {
            "median": float(np.median(biases)),
            "mean": float(np.mean(biases)),
            "p05": float(np.percentile(biases, 5)),
            "p95": float(np.percentile(biases, 95)),
        },
        "k_us_s2_per_m": {plat: k_us(p) for plat, p in ST_BY_PLATFORM.items()},
        "rmse_yaw_rads": {v: float(np.sqrt(sse_yaw[v] / n_tot)) for v in variants},
        "rmse_ay_mps2": {v: float(np.sqrt(sse_ay[v] / n_tot)) for v in variants},
    }
    # ladder deltas + share of total improvement
    base = summary["rmse_yaw_rads"]["baseline"]
    final = summary["rmse_yaw_rads"][variants[-1]]
    total_imp = base - final
    ladder = []
    prev = base
    for v in variants[1:]:
        cur = summary["rmse_yaw_rads"][v]
        delta = prev - cur
        share = (delta / total_imp) * 100.0 if total_imp != 0 else 0.0
        ladder.append({"variant": v, "rmse_after": cur, "delta": delta, "share_pct": share})
        prev = cur
    summary["yaw_attribution_ladder"] = ladder
    # same for a_y
    base_a = summary["rmse_ay_mps2"]["baseline"]
    final_a = summary["rmse_ay_mps2"][variants[-1]]
    total_a = base_a - final_a
    ladder_a = []
    prev = base_a
    for v in variants[1:]:
        cur = summary["rmse_ay_mps2"][v]
        delta = prev - cur
        share = (delta / total_a) * 100.0 if total_a != 0 else 0.0
        ladder_a.append({"variant": v, "rmse_after": cur, "delta": delta, "share_pct": share})
        prev = cur
    summary["ay_attribution_ladder"] = ladder_a

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    # per-segment csv
    fieldnames = list(per_segment[0].keys())
    with (OUT / "per_segment.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(per_segment)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
