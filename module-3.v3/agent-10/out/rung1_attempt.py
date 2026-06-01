"""Rung-1 attempt: linear dynamic single-track for Mach-E and IONIQ-5.

Fixed m, Iz, a, b, C_ar from carParams (or reasonable IONIQ-5 estimates).
Fitted: g (steering scale), C_af, tau-on-top.

If the rung-1 yaw-RMSE per platform beats rung-0, swap into final-model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]

# Per-platform fixed params. Mach-E from carParams, IONIQ-5 estimated.
PLAT_FIXED = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "m": 2336.0, "Iz": 4879.05, "a": 1.3130, "b": 1.6710, "C_ar": 355_912.0,
    },
    "HYUNDAI_IONIQ_5": {
        # IONIQ-5 reasonable estimates (no carParams in code): m~2100, Iz~4000, near 50/50
        "m": 2100.0, "Iz": 4000.0, "a": 1.4435, "b": 1.4435, "C_ar": 220_000.0,
    },
}


def _per_segment_delta0(df, fallback=0.0):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < 0.03) & (v > 5)
    if int(mask.sum()) < 50:
        return float(fallback)
    return float(df.loc[mask, "delta_road_rad"].median())


def rung1_predict(df, p):
    """p = {g, C_af, C_ar, m, Iz, a, b, delta0_fallback, tau}"""
    delta0 = _per_segment_delta0(df, fallback=p.get("delta0_fallback", 0.0))
    delta_raw = df["delta_road_rad"].to_numpy(dtype=float)
    delta = (delta_raw - delta0) * p["g"]
    vx = df["v_mps"].to_numpy(dtype=float)
    t = df["t_s"].to_numpy(dtype=float)
    vx_safe = np.maximum(vx, 1.0)
    dt = np.diff(t, prepend=t[0])

    C_af, C_ar = p["C_af"], p["C_ar"]
    m, Iz = p["m"], p["Iz"]
    a, b = p["a"], p["b"]

    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    SUBSTEPS = 5  # substep for Euler stability at 50 Hz with stiff dynamics
    for i in range(len(vx)):
        h = dt[i] / SUBSTEPS
        for _ in range(SUBSTEPS):
            alpha_f = delta[i] - (vy + a * yr) / vx_safe[i]
            alpha_r = -(vy - b * yr) / vx_safe[i]
            F_yf = C_af * alpha_f
            F_yr = C_ar * alpha_r
            vy_dot = (F_yf + F_yr) / m - vx[i] * yr
            yr_dot = (a * F_yf - b * F_yr) / Iz
            vy += vy_dot * h
            yr += yr_dot * h
        out[i] = yr
    # Optional first-order lag on output
    tau = p.get("tau", 0.0)
    if tau > 0:
        alpha = dt / (tau + dt)
        smoothed = np.empty_like(out)
        smoothed[0] = out[0]
        for i in range(1, len(out)):
            smoothed[i] = smoothed[i-1] + alpha[i] * (out[i] - smoothed[i-1])
        out = smoothed
    return out


def load_platform(platform, n_max=None):
    root = ROOT / "data" / "sim" / "segments" / platform
    segs = []
    paths = sorted(root.glob("**/sim.csv"))
    if n_max:
        # subsample for speed: use first n_max
        paths = paths[:n_max]
    for p in paths:
        df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps",
                                     "yaw_rate_pred_rads", "yaw_rate_meas_rads"])
        if len(df) < 100:
            continue
        segs.append(df)
    return segs


def pooled_rmse(theta, segs, fixed, layout):
    p = dict(fixed)
    p.update(dict(zip(layout, theta)))
    sq = 0.0
    n = 0
    for df in segs:
        try:
            yr = rung1_predict(df, p)
        except Exception:
            return 1e6
        truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        m = v > 2.0
        r = yr[m] - truth[m]
        sq += float(np.sum(r * r))
        n += int(m.sum())
    if n == 0: return 1e6
    return np.sqrt(sq / n)


def fit(platform, n_max=None):
    print(f"\n## rung-1 {platform}")
    fixed = PLAT_FIXED[platform]
    fixed["delta0_fallback"] = 0.0
    segs = load_platform(platform, n_max=n_max)
    print(f"   {len(segs)} segments")
    layout = ["g", "C_af", "tau"]
    x0 = np.array([0.9, 80_000.0, 0.0])

    def loss(theta):
        g, C_af, tau = theta
        if not (0.3 < g < 1.3): return 1e6
        if not (20_000 < C_af < 400_000): return 1e6
        if not (0.0 <= tau < 0.3): return 1e6
        return pooled_rmse(theta, segs, fixed, layout)

    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-3, "fatol": 1e-7, "maxiter": 150, "disp": False})
    print(f"   fitted: g={res.x[0]:.3f} C_af={res.x[1]:.0f} tau={res.x[2]:.3f} -> rmse={res.fun:.6f}")
    return res


def main():
    # Use subset for speed during fitting; full eval afterwards
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        n_max = 60  # subset for speed
        fit(plat, n_max=n_max)


if __name__ == "__main__":
    main()
