"""Fit per-platform coefficients (g, L_eff, K_us, tau, delta0_fallback) on data/sim/.

Objective: minimise pooled yaw-rate RMSE on a train split of each platform.
Then evaluate also on a dev split for overfit check.

Per-segment delta0 is computed at predict time from input channels.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-04")
SIM = ROOT / "data" / "sim" / "segments"

PLATFORMS_TO_FIT = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def _per_segment_delta0(df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def predict_yaw(df, g, L_eff, K_us, tau, delta0):
    delta = (df["delta_road_rad"].to_numpy() - delta0) * g
    v = df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def load_segments(platform):
    paths = sorted((SIM / platform).glob("*/*/*/sim.csv"))
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # route id from parent dir name
        route = p.parents[1].name
        segs.append((route, df))
    return segs


def route_split(segs, train_frac=0.75, seed=0):
    routes = sorted({r for r, _ in segs})
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    n_train = int(len(routes) * train_frac)
    train_routes = set(routes[:n_train])
    train, dev = [], []
    for r, df in segs:
        (train if r in train_routes else dev).append((r, df))
    return train, dev


def total_rmse(params, segs, use_per_segment_delta0):
    g, L_eff, K_us, tau, delta0_fb = params
    sum_sq = 0.0
    n = 0
    for _, df in segs:
        if use_per_segment_delta0:
            d0 = _per_segment_delta0(df, fallback=delta0_fb)
        else:
            d0 = delta0_fb
        yr = predict_yaw(df, g, L_eff, K_us, tau, d0)
        truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > 2.0
        r = yr[mask] - truth[mask]
        sum_sq += float(np.sum(r * r))
        n += int(mask.sum())
    return np.sqrt(sum_sq / n) if n > 0 else np.inf


def fit_platform(platform, use_per_segment_delta0):
    print(f"\n=== Fitting {platform} (use_per_segment_delta0={use_per_segment_delta0}) ===")
    segs = load_segments(platform)
    print(f"  {len(segs)} segments loaded")
    train, dev = route_split(segs)
    print(f"  train: {len(train)} segs, dev: {len(dev)} segs")

    # Initial guess from anti-patterns example
    if platform == "FORD_F_150_LIGHTNING_MK1":
        x0 = [0.863, 3.26, 0.00350, 0.060, 0.00133]
    elif platform == "FORD_MUSTANG_MACH_E_MK1":
        x0 = [0.891, 2.22, 0.00150, 0.069, -0.0001]
    else:
        x0 = [0.938, 2.887, 0.00289, 0.062, 0.0]

    bounds = [(0.5, 1.3), (1.5, 5.0), (-0.005, 0.02), (0.01, 0.3), (-0.05, 0.05)]

    res = minimize(
        total_rmse, x0, args=(train, use_per_segment_delta0),
        method="Nelder-Mead",
        bounds=bounds,
        options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 300},
    )
    g, L_eff, K_us, tau, d0fb = res.x
    train_rmse = total_rmse(res.x, train, use_per_segment_delta0)
    dev_rmse = total_rmse(res.x, dev, use_per_segment_delta0)
    print(f"  fit: g={g:.4f} L_eff={L_eff:.4f} K_us={K_us:.5f} tau={tau:.4f} d0fb={d0fb:+.5f}")
    print(f"  train rmse={train_rmse:.5f}  dev rmse={dev_rmse:.5f}")
    # Also compute the bias-spread diagnostic
    biases = []
    for _, df in segs:
        if "yaw_rate_meas_rads" not in df:
            continue
        v = df["v_mps"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        v0 = df["yaw_rate_pred_rads"].to_numpy()
        mask = v > 2.0
        biases.append(float(np.mean(v0[mask] - truth[mask])))
    print(f"  std(per-seg-bias V0) = {np.std(biases):.5f} rad/s  (>0.002 => per-seg-delta0 helps)")
    return {
        "g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau,
        "delta0": d0fb, "delta0_fallback": d0fb,
        "use_per_segment_delta0": use_per_segment_delta0,
        "train_rmse": train_rmse, "dev_rmse": dev_rmse,
        "bias_spread_std": float(np.std(biases)),
    }


def main():
    out = {}
    # Per anti-patterns: Mach-E and Hyundai use per-segment delta0; Lightning doesn't
    config = {
        "FORD_F_150_LIGHTNING_MK1": False,
        "FORD_MUSTANG_MACH_E_MK1": True,
        "HYUNDAI_IONIQ_5": True,
    }
    for plat in PLATFORMS_TO_FIT:
        out[plat] = fit_platform(plat, config[plat])
    out_path = ROOT / "out" / "coeffs.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWritten: {out_path}")
    return out


if __name__ == "__main__":
    main()
