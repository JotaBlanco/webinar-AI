"""Fit per-platform coefficients {g, L_eff, K_us, tau, delta0/delta0_fallback}.

Objective: pooled yaw_rate_rmse on that platform (v > 2 mps mask).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09")
sys.path.insert(0, str(ROOT / "final-model"))

# Reuse the predict's helpers but operate offline.

def per_seg_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict_yaw(sim_df, g, L_eff, K_us, tau, delta0):
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def load_platform(platform, max_segs=None):
    root = ROOT / "data" / "sim" / "segments" / platform
    segs = sorted(p for p in root.glob("**/sim.csv") if p.is_file())
    if max_segs:
        segs = segs[:max_segs]
    out = []
    for p in segs:
        df = pd.read_csv(p, usecols=[
            "t_s", "delta_road_rad", "v_mps", "yaw_rate_pred_rads", "yaw_rate_meas_rads"
        ])
        out.append(df)
    return out


def objective(theta, segments, per_segment_delta0, fallback_idx=None, fixed=None):
    g, L_eff, K_us, tau = theta[0], theta[1], theta[2], theta[3]
    if per_segment_delta0:
        delta0_fb = theta[4]
    else:
        delta0 = theta[4]
    sse = 0.0
    n = 0
    for df in segments:
        if per_segment_delta0:
            d0 = per_seg_delta0(df, fallback=delta0_fb)
        else:
            d0 = delta0
        yr = predict_yaw(df, g, L_eff, K_us, tau, d0)
        y_true = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > 2.0
        r = yr[mask] - y_true[mask]
        sse += float(np.sum(r * r))
        n += int(mask.sum())
    return sse / max(n, 1)


def fit_platform(platform, per_segment_delta0, x0, bounds):
    print(f"\n=== Fitting {platform} (per_seg_delta0={per_segment_delta0}) ===")
    t0 = time.time()
    segs = load_platform(platform)
    print(f"  loaded {len(segs)} segments in {time.time()-t0:.1f}s")

    def f(theta):
        return objective(theta, segs, per_segment_delta0)

    val0 = f(x0)
    print(f"  start theta={x0} rmse={np.sqrt(val0):.6f}")
    res = minimize(f, x0, method="Powell",
                   bounds=bounds,
                   options={"xtol": 1e-7, "ftol": 1e-11, "maxiter": 2000})
    print(f"  final theta={res.x} rmse={np.sqrt(res.fun):.6f} iters={res.nit}")
    return res.x


if __name__ == "__main__":
    out = {}

    # Lightning — global delta0
    # theta = [g, L_eff, K_us, tau, delta0]
    x = fit_platform(
        "FORD_F_150_LIGHTNING_MK1",
        per_segment_delta0=False,
        x0=[0.863, 3.26, 0.00350, 0.060, 0.00133],
        bounds=[(0.5, 1.5), (1.5, 6.0), (-0.005, 0.02), (0.0, 0.4), (-0.02, 0.02)],
    )
    out["FORD_F_150_LIGHTNING_MK1"] = {
        "use_per_segment_delta0": False,
        "g": float(x[0]),
        "L_eff": float(x[1]),
        "K_us": float(x[2]),
        "tau": float(x[3]),
        "delta0": float(x[4]),
    }

    # Mach-E — per-segment delta0. Constrain L_eff close to wheelbase prior
    # (2.984 m) to break g↔L_eff scale invariance.
    x = fit_platform(
        "FORD_MUSTANG_MACH_E_MK1",
        per_segment_delta0=True,
        x0=[0.891, 2.984, 0.00150, 0.069, -0.0001],
        bounds=[(0.5, 1.5), (2.5, 3.5), (-0.005, 0.02), (0.0, 0.4), (-0.02, 0.02)],
    )
    out["FORD_MUSTANG_MACH_E_MK1"] = {
        "use_per_segment_delta0": True,
        "g": float(x[0]),
        "L_eff": float(x[1]),
        "K_us": float(x[2]),
        "tau": float(x[3]),
        "delta0_fallback": float(x[4]),
    }

    # IONIQ-5 — per-segment delta0
    x = fit_platform(
        "HYUNDAI_IONIQ_5",
        per_segment_delta0=True,
        x0=[0.938, 2.887, 0.00289, 0.062, 0.0],
        bounds=[(0.5, 1.5), (1.5, 6.0), (-0.005, 0.02), (0.0, 0.4), (-0.02, 0.02)],
    )
    out["HYUNDAI_IONIQ_5"] = {
        "use_per_segment_delta0": True,
        "g": float(x[0]),
        "L_eff": float(x[1]),
        "K_us": float(x[2]),
        "tau": float(x[3]),
        "delta0_fallback": float(x[4]),
    }

    print("\n=== Fitted coeffs ===")
    print(json.dumps(out, indent=2))
    with open(ROOT / "out" / "fitted_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved → {ROOT / 'out' / 'fitted_coeffs.json'}")
