"""Rung-1 minimum viable attempt: linear dynamic single-track, C_af fitted.

Fix m, Iz, a, b, C_ar from code/parameters.py per platform. Fit C_af only.
Evaluate on a held-out dev split (route-grouped) against pooled yaw RMSE for
Mach-E only (cheapest test). Compare against rung-0 final on same dev split.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "final-model"))
from parameters import MACH_E  # noqa
import predict as predict_mod  # noqa


def rung1_yaw(sim_df, C_af, C_ar, m, Iz, a, b):
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    vx = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)
    vx_safe = np.maximum(vx, 1.0)
    dt = np.diff(t, prepend=t[0])
    # Adopt smaller sub-steps to avoid Euler instability at high stiffness.
    n_sub = 4
    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    for i in range(len(vx)):
        h = float(dt[i]) / n_sub
        for _ in range(n_sub):
            af = delta[i] - (vy + a * yr) / vx_safe[i]
            ar = -(vy - b * yr) / vx_safe[i]
            Fyf = C_af * af
            Fyr = C_ar * ar
            vy_dot = (Fyf + Fyr) / m - vx[i] * yr
            yr_dot = (a * Fyf - b * Fyr) / Iz
            vy += vy_dot * h
            yr += yr_dot * h
            # Stability guard
            if not (np.isfinite(vy) and np.isfinite(yr)) or abs(yr) > 5.0:
                vy = 0.0
                yr = 0.0
                break
        out[i] = yr
    return out


def load_segs(platform, max_segs=None):
    root = ROOT / "data" / "sim" / "segments" / platform
    segs = sorted(p for p in root.glob("**/sim.csv") if p.is_file())
    if max_segs:
        segs = segs[:max_segs]
    out = []
    for p in segs:
        df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps",
                                      "yaw_rate_pred_rads", "yaw_rate_meas_rads"])
        # route id is parents[1].name
        out.append((str(p.parents[1].name), df))
    return out


def pooled_rmse(segs, fn):
    sse = 0.0
    n = 0
    for _, df in segs:
        yr = fn(df)
        y = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > 2.0
        r = yr[mask] - y[mask]
        sse += float(np.sum(r * r))
        n += int(mask.sum())
    return np.sqrt(sse / max(n, 1))


if __name__ == "__main__":
    platform = "FORD_MUSTANG_MACH_E_MK1"
    p = MACH_E
    print(f"Loading {platform}...")
    # Cap to 60 segs to keep the rung-1 attempt under budget.
    all_segs = load_segs(platform, max_segs=60)
    print(f"  {len(all_segs)} segments (capped)")

    # Route-grouped split: first 80% routes train, last 20% dev
    routes = sorted({r for r, _ in all_segs})
    n_train = int(len(routes) * 0.8)
    train_routes = set(routes[:n_train])
    train = [(r, d) for r, d in all_segs if r in train_routes]
    dev = [(r, d) for r, d in all_segs if r not in train_routes]
    print(f"  train: {len(train)} segs, dev: {len(dev)} segs")

    # Fit C_af on train
    C_ar = p.C_alpha_r
    m = p.m
    Iz = p.I_z
    a = p.l_f
    b = p.l_r

    def obj(C_af):
        return pooled_rmse(train, lambda df: rung1_yaw(df, C_af, C_ar, m, Iz, a, b))

    print(f"  Fitting C_af in [40k, 400k]...")
    t0 = time.time()
    res = minimize_scalar(obj, bounds=(40_000, 400_000), method="bounded",
                          options={"xatol": 500})
    print(f"  fit took {time.time()-t0:.1f}s, C_af* = {res.x:.0f}, train rmse = {res.fun:.6f}")

    # Eval on dev
    rung1_dev_rmse = pooled_rmse(dev, lambda df: rung1_yaw(df, res.x, C_ar, m, Iz, a, b))
    print(f"  Rung-1 dev RMSE: {rung1_dev_rmse:.6f}")

    # Compare against rung-0 (final-model predict) on same dev
    def rung0_fn(df):
        # predict expects yaw_rate_pred_rads in df — it's there
        return predict_mod.predict(df, platform)["yaw_rate_pred_rads"].to_numpy()

    rung0_dev_rmse = pooled_rmse(dev, rung0_fn)
    print(f"  Rung-0 dev RMSE: {rung0_dev_rmse:.6f}")

    print(f"\n  Δ = rung1 - rung0 = {(rung1_dev_rmse - rung0_dev_rmse)*1000:+.3f} mrad/s")
    print(f"  Rung-1 {'BEATS' if rung1_dev_rmse < rung0_dev_rmse else 'LOSES TO'} rung-0 on Mach-E dev.")
