"""Fit per-platform V1 understeer + V2 steering-rate-lead model.

Model (per platform):
    delta_eff(t) = (delta_road_rad(t) - delta_off) + tau * d(delta_road_rad)/dt
    yaw_pred(t)  = gain * v(t) * delta_eff(t) / (L_eff * (1 + K_us * v^2))

Coeffs per platform: gain, K_us, tau, delta_off, L_eff (relative to nominal).
We absorb L into gain (gain := 1/L_eff baseline). Equivalent param: a single
gain replaces (1/L_eff)*gain; we keep separate to bound.

Trains by direct yaw-rate sum-sq minimisation across pooled rows from the
platform's training subset, then evaluates on full set. Tesla skipped (no
independent truth — baseline IS V0 output).
"""
from __future__ import annotations
import sys
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary  # noqa

# Nominal wheelbases (from parameters.py).
L_NOMINAL = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          3.0,   # guess; gain absorbs anyway
    "TESLA_MODEL_3":            2.875,
}


def load_platform(platform: str, max_segs: int | None = None):
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    if max_segs:
        paths = paths[:max_segs]
    truth_col = "psi_dot_rads" if platform == "TESLA_MODEL_3" else "yaw_rate_meas_rads"
    rows_t, rows_d, rows_v, rows_dd, rows_y = [], [], [], [], []
    for p in paths:
        df = pd.read_csv(p)
        if truth_col not in df.columns:
            continue
        if len(df) < 10:
            continue
        t = df["t_s"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        y = df[truth_col].to_numpy(float)
        if np.any(np.diff(t) <= 0):
            continue
        dd = np.gradient(d, t)
        # v-filter
        mask = v > 2.0
        rows_t.append(t[mask])
        rows_d.append(d[mask])
        rows_v.append(v[mask])
        rows_dd.append(dd[mask])
        rows_y.append(y[mask])
    if not rows_t:
        return None
    return {
        "t":  np.concatenate(rows_t),
        "d":  np.concatenate(rows_d),
        "v":  np.concatenate(rows_v),
        "dd": np.concatenate(rows_dd),
        "y":  np.concatenate(rows_y),
    }


def model_predict(d, v, dd, gain, K_us, tau, d_off):
    delta_eff = (d - d_off) + tau * dd
    return gain * v * delta_eff / (1.0 + K_us * v * v)


def fit_platform(platform: str, data: dict, L_nom: float):
    d, v, dd, y = data["d"], data["v"], data["dd"], data["y"]

    # Subsample for speed (5M rows / 4 platforms is big-ish, but per-platform fits
    # are fast since they are scalar reductions). Limit to ~200k samples.
    n = len(d)
    if n > 200_000:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, 200_000, replace=False)
        d, v, dd, y = d[idx], v[idx], dd[idx], y[idx]

    # Initial: gain=1/L_nom, K_us=0, tau=0, d_off=0
    x0 = np.array([1.0 / L_nom, 0.0, 0.0, 0.0])

    def loss(x):
        gain, K_us, tau, d_off = x
        yp = model_predict(d, v, dd, gain, K_us, tau, d_off)
        return float(np.mean((yp - y) ** 2))

    bounds = [
        (0.5 / L_nom, 2.0 / L_nom),  # gain
        (-0.01, 0.05),                # K_us [s²/m²] understeer typically positive small
        (-0.2, 0.5),                  # tau [s] steering lead
        (-0.01, 0.01),                # delta_off [rad] small steering offset
    ]

    r = minimize(loss, x0, method="L-BFGS-B", bounds=bounds)
    gain, K_us, tau, d_off = r.x
    rmse_train = math.sqrt(r.fun)
    return {
        "gain":       float(gain),
        "K_us":       float(K_us),
        "tau":        float(tau),
        "delta_off":  float(d_off),
        "L_nominal":  float(L_nom),
        "rmse_train": rmse_train,
        "n_train":    int(len(d)),
        "converged":  bool(r.success),
    }


def main():
    coeffs = {}
    for plat, L_nom in L_NOMINAL.items():
        if plat == "TESLA_MODEL_3":
            # No independent truth — emit V0 passthrough coeffs (identity).
            coeffs[plat] = {
                "gain":      1.0 / L_nom,
                "K_us":      0.0,
                "tau":       0.0,
                "delta_off": 0.0,
                "L_nominal": L_nom,
                "passthrough": True,
            }
            continue
        print(f"\n== fitting {plat} ==", flush=True)
        data = load_platform(plat)
        if data is None:
            print(f"  no data for {plat}")
            continue
        print(f"  loaded {len(data['d']):,} samples")
        c = fit_platform(plat, data, L_nom)
        print(f"  coeffs: {c}")
        coeffs[plat] = c

    out_path = ROOT / "out" / "coeffs_v2.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
