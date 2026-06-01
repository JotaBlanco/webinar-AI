"""Rung-1 minimum viable attempt: linear dynamic single-track on Mach-E.

Uses carParams priors; per-segment δ₀ retained (same straight-row gate as V1).
Steering scale `g` reused from V1. Two-state Euler integration of (vy, yr).
We do a *single-parameter* fit on C_af for Mach-E and compare against V1 on a
held-out dev set.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-05")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment

# Mach-E carParams
M = 2336.0
IZ = 4879.05
A_F = 1.3130
B_R = 1.671
C_AR = 355_912.0
G_STEER = 0.891  # V1 steering scale

def _per_segment_delta0(sim_df, fallback=-0.0001,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())

def rung1_predict(sim_df, C_af):
    delta0 = _per_segment_delta0(sim_df)
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * G_STEER
    vx = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    vx_safe = np.maximum(vx, 1.0)
    dt = np.diff(t, prepend=t[0])
    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    for i in range(len(vx)):
        alpha_f = delta[i] - (vy + A_F * yr) / vx_safe[i]
        alpha_r = -(vy - B_R * yr) / vx_safe[i]
        F_yf = C_af * alpha_f
        F_yr = C_AR * alpha_r
        vy_dot = (F_yf + F_yr) / M - vx[i] * yr
        yr_dot = (A_F * F_yf - B_R * F_yr) / IZ
        vy += vy_dot * dt[i]
        yr += yr_dot * dt[i]
        # clamp to keep integration stable when the linear tyre over-reacts
        if not np.isfinite(vy) or abs(vy) > 50.0: vy = 0.0
        if not np.isfinite(yr) or abs(yr) > 5.0: yr = 0.0
        out[i] = yr
    return out

def v1_predict(sim_df):
    g = 0.891
    L_eff = 2.22
    K_us = 0.00150
    tau = 0.069
    delta0 = _per_segment_delta0(sim_df)
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def load_machE(max_segments=80, seed=11):
    seg_root = ROOT / "data" / "sim" / "segments" / "FORD_MUSTANG_MACH_E_MK1"
    paths = sorted(p for p in seg_root.glob("**/sim.csv") if p.is_file())
    rng = np.random.default_rng(seed)
    rng.shuffle(paths)
    paths = paths[:max_segments]
    return [(p.resolve().parents[1].name, p, pd.read_csv(p)) for p in paths]


def pooled(segments, pred_fn):
    yaw_sum_sq = 0.0; yaw_n = 0; cte_sum_sq = 0.0; cte_n = 0
    for _, _, df in segments:
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        yr_truth = df["yaw_rate_meas_rads"].to_numpy(float)
        yr_pred = pred_fn(df)
        mask_v = v > 2.0
        resid = yr_pred - yr_truth
        yaw_sum_sq += float(np.sum(resid[mask_v]**2)); yaw_n += int(mask_v.sum())
        cte = cte_diagnostics_segment(t, v, yr_truth, yr_pred, 1.0, 20.0)
        cte_sum_sq += cte["sum_sq_m2"]; cte_n += cte["n_bins"]
    return math.sqrt(yaw_sum_sq / yaw_n), math.sqrt(cte_sum_sq / cte_n)


def main():
    segs = load_machE()
    n_dev = max(1, int(len(segs) * 0.25))
    routes = sorted({r for r, _, _ in segs})
    rng = np.random.default_rng(3)
    rng.shuffle(routes)
    dev_routes = set(routes[: max(1, len(routes) // 4)])
    train = [s for s in segs if s[0] not in dev_routes]
    dev = [s for s in segs if s[0] in dev_routes]
    print(f"train={len(train)}, dev={len(dev)}")

    # V1 baseline on this subset
    v1_yaw_train, v1_cte_train = pooled(train, v1_predict)
    v1_yaw_dev, v1_cte_dev = pooled(dev, v1_predict)
    print(f"V1 — train: yaw={v1_yaw_train:.5f} cte={v1_cte_train:.3f} | dev: yaw={v1_yaw_dev:.5f} cte={v1_cte_dev:.3f}")

    # Sweep C_af
    def obj(C_af):
        yaw, _ = pooled(train, lambda df: rung1_predict(df, C_af))
        return yaw

    res = minimize_scalar(obj, bounds=(150_000, 500_000), method="bounded",
                          options={"xatol": 2000.0, "maxiter": 10})
    C_af_fit = res.x
    print(f"Rung1 fitted C_af = {C_af_fit:.0f} (carParams prior: 286_551)")
    r1_yaw_train, r1_cte_train = pooled(train, lambda df: rung1_predict(df, C_af_fit))
    r1_yaw_dev, r1_cte_dev = pooled(dev, lambda df: rung1_predict(df, C_af_fit))
    print(f"Rung1 — train: yaw={r1_yaw_train:.5f} cte={r1_cte_train:.3f} | dev: yaw={r1_yaw_dev:.5f} cte={r1_cte_dev:.3f}")

    delta_yaw_dev = r1_yaw_dev - v1_yaw_dev
    delta_cte_dev = r1_cte_dev - v1_cte_dev
    print(f"Delta vs V1 on dev: dyaw={delta_yaw_dev:+.5f} dcte={delta_cte_dev:+.3f}")
    print("(positive = worse than V1)")


if __name__ == "__main__":
    main()
