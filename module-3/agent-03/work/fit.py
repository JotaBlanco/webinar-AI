"""Fit per-platform parameters: closed-form understeer + first-order lag.

Model:  yr_ss = v * (g*delta + delta0) / (L_eff + K_us * v^2)
        yr(t) filtered with first-order lag tau.

Parameters per platform: g, delta0, L_eff, K_us, tau.

Fit on train routes only. Evaluate honest on dev.
"""
import sys
import os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-03")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))

import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize, least_squares

from split import split
from score import score


def first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """One-pole IIR low-pass with time constant tau. y[k+1] = a*y[k] + (1-a)*x[k+1] where a = exp(-dt/tau)."""
    if tau <= 1e-6:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    a = np.exp(-dt / tau)
    for k in range(len(dt)):
        y[k + 1] = a[k] * y[k] + (1.0 - a[k]) * yr_ss[k + 1]
    return y


def predict_one(sim_df: pd.DataFrame, params: dict) -> np.ndarray:
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)
    g = params["g"]
    delta0 = params["delta0"]
    L_eff = params["L_eff"]
    K_us = params["K_us"]
    tau = params["tau"]
    delta_eff = g * delta + delta0
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    return first_order_lag(yr_ss, t, tau)


def load_segments_df(paths):
    out = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        out.append(df)
    return out


def fit_platform(train_dfs, x0=None, bounds=None):
    """Levenberg-Marquardt over (g, delta0, L_eff, K_us, tau).
    Residual: yr_pred - yr_meas, weighted by v>3 mask (also where lag/dyn matters).
    """
    # Precompute arrays
    cached = []
    for df in train_dfs:
        t = df["t_s"].to_numpy(float)
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        v = df["v_mps"].to_numpy(float)
        delta = df["delta_road_rad"].to_numpy(float)
        yr_meas = df["yaw_rate_meas_rads"].to_numpy(float)
        mask = v > 3.0
        if mask.sum() < 50:
            continue
        cached.append((t, v, delta, yr_meas, mask))
    print(f"  fitting on {len(cached)} usable segments")

    def residuals(theta):
        g, delta0, L_eff, K_us, tau = theta
        if L_eff <= 0.5 or tau < 0 or tau > 0.5:
            return np.full(1000, 1e3)
        res_chunks = []
        for t, v, delta, yr_meas, mask in cached:
            delta_eff = g * delta + delta0
            yr_ss = v * delta_eff / (L_eff + K_us * v * v)
            yr_pred = first_order_lag(yr_ss, t, tau)
            r = (yr_pred - yr_meas)[mask]
            res_chunks.append(r)
        return np.concatenate(res_chunks)

    if x0 is None:
        x0 = np.array([1.0, 0.0, 2.984, 0.002, 0.06])
    lb = np.array([0.5, -0.02, 1.5, -0.005, 0.0])
    ub = np.array([1.5, 0.02, 6.0, 0.02, 0.3])
    res = least_squares(residuals, x0, bounds=(lb, ub), method='trf', max_nfev=200, verbose=1)
    g, delta0, L_eff, K_us, tau = res.x
    print(f"  fit: g={g:.4f}  d0={delta0:.5f}  L_eff={L_eff:.3f}  K_us={K_us:.5f}  tau={tau:.4f}  RMSE={np.sqrt(np.mean(res.fun**2)):.5f}")
    return dict(g=float(g), delta0=float(delta0), L_eff=float(L_eff), K_us=float(K_us), tau=float(tau))


if __name__ == "__main__":
    train, dev = split()
    by_plat_train = {"FORD_F_150_LIGHTNING_MK1": [], "FORD_MUSTANG_MACH_E_MK1": []}
    by_plat_dev = {"FORD_F_150_LIGHTNING_MK1": [], "FORD_MUSTANG_MACH_E_MK1": []}
    for p in train:
        for k in by_plat_train:
            if k in str(p):
                by_plat_train[k].append(p)
    for p in dev:
        for k in by_plat_dev:
            if k in str(p):
                by_plat_dev[k].append(p)

    params_by_platform = {}
    for plat, paths in by_plat_train.items():
        print(f"\n=== {plat} train segs: {len(paths)} ===")
        dfs = load_segments_df(paths)
        x0 = np.array([1.0, 0.0, 2.984 if "MACH_E" in plat else 3.70, 0.002, 0.06])
        params_by_platform[plat] = fit_platform(dfs, x0=x0)

    out_file = ROOT / "work" / "params.json"
    out_file.write_text(json.dumps(params_by_platform, indent=2))
    print("\nWrote:", out_file)
    print(json.dumps(params_by_platform, indent=2))
