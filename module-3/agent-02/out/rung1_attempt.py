"""Rung 1 — Linear dynamic single-track with slip angles. Minimum viable.

Fixed mass/Iz/a/b/C_ar from carParams; fit C_af per platform on yaw RMSE.
Quick test on Mach-E only (fastest signal). Logs result.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02")
sys.path.insert(0, str(ROOT / "out"))
from fit_v2 import load_segments, split_by_route  # noqa: E402

# carParams from code/parameters.py
CAR_PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "L": 2.984, "m": 2336.0, "Iz": 4879.05, "a": 1.3130, "b": 1.671,
        "C_af": 286_551.0, "C_ar": 355_912.0,
    },
    "FORD_F_150_LIGHTNING_MK1": {
        "L": 3.70, "m": 3084.0, "Iz": 9903.37, "a": 1.628, "b": 2.072,
        "C_af": 378_307.0, "C_ar": 469_878.0,
    },
    "HYUNDAI_IONIQ_5": {
        # Approx — IONIQ-5 not in parameters.py. Use Mach-E-like values scaled.
        "L": 3.0, "m": 2200.0, "Iz": 4500.0, "a": 1.45, "b": 1.55,
        "C_af": 250_000.0, "C_ar": 320_000.0,
    },
}


def rung1_predict(sim_df, p, delta0=0.0, g=1.0):
    delta_in = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
    vx = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    vx_safe = np.maximum(vx, 1.0)
    dt = np.diff(t, prepend=t[0])
    C_af, C_ar = p["C_af"], p["C_ar"]
    m, Iz = p["m"], p["Iz"]
    a, b = p["a"], p["b"]
    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    # Sub-step at 1 kHz for stability (50 Hz Euler explodes with stiff tyres).
    SUBSTEPS = 20
    for i in range(len(vx)):
        h = dt[i] / SUBSTEPS
        vxi = vx_safe[i]
        for _ in range(SUBSTEPS):
            alpha_f = delta_in[i] - (vy + a * yr) / vxi
            alpha_r = -(vy - b * yr) / vxi
            F_yf = C_af * alpha_f
            F_yr = C_ar * alpha_r
            vy_dot = (F_yf + F_yr) / m - vx[i] * yr
            yr_dot = (a * F_yf - b * F_yr) / Iz
            vy += vy_dot * h
            yr += yr_dot * h
        out[i] = yr
    return out


def pooled_rmse(segs, p_base, C_af, v_thresh=2.0):
    sum_sq = 0.0
    n = 0
    p = dict(p_base)
    p["C_af"] = C_af
    for _, _, df in segs:
        v = df["v_mps"].to_numpy()
        mask = v > v_thresh
        if not mask.any():
            continue
        yr_pred = rung1_predict(df, p)
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        r = (yr_pred - yr_truth)[mask]
        if not np.isfinite(r).all():
            return float("inf")
        sum_sq += float(np.sum(r * r))
        n += int(mask.sum())
    return float(np.sqrt(sum_sq / n)) if n > 0 else float("inf")


def attempt(platform):
    print(f"\n== rung-1 attempt on {platform} ==")
    segs = load_segments(platform)
    train, dev = split_by_route(segs)
    print(f"  train={len(train)}, dev={len(dev)}")
    p_base = CAR_PARAMS[platform]
    # Limit to first 30 train segments for speed
    train_small = train[:15]
    init_rmse = pooled_rmse(train_small, p_base, p_base["C_af"])
    print(f"  carParams C_af={p_base['C_af']:.0f}, train(small) rmse={init_rmse:.6f}")
    res = minimize_scalar(
        lambda c: pooled_rmse(train_small, p_base, c),
        bounds=(40_000, 600_000), method="bounded",
        options={"xatol": 5000.0, "maxiter": 20},
    )
    C_af_fit = float(res.x)
    print(f"  fit C_af={C_af_fit:.0f}, train(small) rmse={res.fun:.6f}")
    full_rmse = pooled_rmse(train, p_base, C_af_fit)
    dev_rmse = pooled_rmse(dev, p_base, C_af_fit) if dev else float("nan")
    print(f"  fit on full train: train_rmse={full_rmse:.6f}, dev_rmse={dev_rmse:.6f}")
    return {"platform": platform, "C_af_fit": C_af_fit,
            "train_rmse": full_rmse, "dev_rmse": dev_rmse}


if __name__ == "__main__":
    # Just Mach-E for the rung-1 attempt (time budget)
    r = attempt("FORD_MUSTANG_MACH_E_MK1")
    print("\nResult:", r)
