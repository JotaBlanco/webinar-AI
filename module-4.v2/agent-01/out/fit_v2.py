"""Fit per-platform V2 coefficients via least-squares.

Model (still steady-state understeer + first-order lag):
    delta_eff = (delta_road - delta0) * g
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)
    yr[t+1]   = yr[t] + alpha * (yr_ss - yr[t])   with alpha = dt/(tau + dt)

We also try a "linear-in-curvature" alt:
    yr_ss = v * (a0 + a1 * (delta_road - delta0)) / (1 + b * v^2)

Optimise (delta0, g, L_eff, K_us, tau) per platform on yaw RMSE pooled.

Use train subset to fit, then re-score on full dev for honesty.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))


def load_platform_segments(platform: str, max_segments: int | None = None):
    root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(root.glob("**/sim.csv"))
    if max_segments:
        # Deterministic stride sampling
        step = max(1, len(paths) // max_segments)
        paths = paths[::step][:max_segments]
    return paths


def _per_segment_delta0(delta_road, v, yr_v0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return None
    return float(np.median(delta_road[mask]))


def predict_yr(sim_df, params, use_per_seg_delta0):
    delta_road = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy() if "yaw_rate_pred_rads" in sim_df.columns else np.zeros_like(v)
    if use_per_seg_delta0:
        d0 = _per_segment_delta0(delta_road, v, yr_v0)
        if d0 is None:
            d0 = params["delta0_fallback"]
    else:
        d0 = params["delta0"]
    delta = (delta_road - d0) * params["g"]
    yr_ss = v * delta / (params["L_eff"] + params["K_us"] * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (params["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def collect_data(paths, max_seg=None):
    if max_seg is not None:
        # stride
        step = max(1, len(paths) // max_seg)
        paths = paths[::step][:max_seg]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps", "yaw_rate_pred_rads", "yaw_rate_meas_rads"])
        except Exception:
            continue
        if len(df) < 100:
            continue
        segs.append(df)
    return segs


def fit_platform(segs, use_per_seg_delta0, init):
    """Minimise yaw_rmse over segs (pooled, v>2 mask)."""
    def loss(theta):
        if use_per_seg_delta0:
            g, L_eff, K_us, tau, d0_fb = theta
            params = dict(g=g, L_eff=L_eff, K_us=K_us, tau=max(tau, 1e-4), delta0_fallback=d0_fb)
        else:
            g, L_eff, K_us, tau, d0 = theta
            params = dict(g=g, L_eff=L_eff, K_us=K_us, tau=max(tau, 1e-4), delta0=d0)
        if K_us < 0 or L_eff <= 0.5 or g <= 0:
            return 1e9
        sum_sq = 0.0
        n = 0
        for df in segs:
            yr = predict_yr(df, params, use_per_seg_delta0)
            v = df["v_mps"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            mask = v > 2.0
            r = yr[mask] - truth[mask]
            sum_sq += float(np.sum(r * r))
            n += int(mask.sum())
        return np.sqrt(sum_sq / n)
    res = minimize(loss, init, method="Nelder-Mead", options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 800})
    return res


PLATFORMS = {
    "FORD_F_150_LIGHTNING_MK1": dict(use=False, init=[0.863, 3.26, 0.00350, 0.060, 0.00133]),
    "FORD_MUSTANG_MACH_E_MK1":  dict(use=True,  init=[0.891, 2.22, 0.00150, 0.069, -0.0001]),
    "HYUNDAI_IONIQ_5":          dict(use=True,  init=[0.938, 2.887, 0.00289, 0.062, 0.0]),
}


def main():
    out = {}
    for plat, cfg in PLATFORMS.items():
        print(f"\n=== Fitting {plat} ===")
        paths = load_platform_segments(plat)
        # Subsample to ~80 segments for speed
        segs = collect_data(paths, max_seg=80)
        print(f"  using {len(segs)} segments")
        res = fit_platform(segs, cfg["use"], cfg["init"])
        keys = (["g", "L_eff", "K_us", "tau", "delta0_fallback" if cfg["use"] else "delta0"])
        params = dict(zip(keys, res.x.tolist()))
        params["use_per_segment_delta0"] = cfg["use"]
        if cfg["use"]:
            params["delta0"] = 0.0
        else:
            params["delta0_fallback"] = 0.0
        print(f"  loss (train yaw RMSE): {res.fun:.6f}")
        print(f"  params: {params}")
        out[plat] = params

    with open(HERE / "v2_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {HERE / 'v2_coeffs.json'}")


if __name__ == "__main__":
    main()
