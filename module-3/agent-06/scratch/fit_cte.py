"""Fit per-platform with a hybrid loss: yaw RMSE + lambda * CTE-like (integrated heading error).

Actually, simpler: minimize MSE of cumulative heading (psi). Since CTE is essentially driven by
integrated yaw error, fitting to integrated yaw-rate should target CTE directly.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import json

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))

from score import score
from split import split

import os
os.chdir(str(ROOT))

L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def yr_steady_poly(delta, v, g0, g2, delta0, K_us, L):
    return v * (g0 * delta + g2 * delta * np.abs(delta) + delta0) / (L + K_us * v * v)


def apply_lag_vec(yr_ss, t, tau):
    if tau <= 1e-4:
        return yr_ss.copy()
    n = len(yr_ss)
    y = np.empty(n); y[0] = yr_ss[0]
    dt = np.diff(t); alpha = np.clip(dt / tau, 0.0, 1.0)
    for k in range(n - 1):
        y[k + 1] = y[k] + alpha[k] * (yr_ss[k] - y[k])
    return y


def load_arrays(paths):
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        yr = df["yaw_rate_meas_rads"].to_numpy(float)
        segs.append((t, v, d, yr))
    return segs


def loss(params, segs, L, v_thr=2.0, lam=0.5):
    """Combined loss: yaw_MSE + lam * psi_MSE (integrated heading)."""
    g0, g2, delta0, K_us, tau = params
    sum_sq_yr = 0.0
    sum_sq_psi = 0.0
    n_yr = 0
    n_psi = 0
    for (t, v, d, yr) in segs:
        yr_ss = yr_steady_poly(d, v, g0, g2, delta0, K_us, L)
        yr_pred = apply_lag_vec(yr_ss, t, tau)
        mask = v > v_thr
        diff = yr_pred[mask] - yr[mask]
        sum_sq_yr += float(np.sum(diff * diff))
        n_yr += int(mask.sum())
        # Integrated heading
        dt = np.diff(t)
        psi_truth = np.concatenate([[0.0], np.cumsum(yr[:-1] * dt)])
        psi_pred = np.concatenate([[0.0], np.cumsum(yr_pred[:-1] * dt)])
        diff_psi = psi_pred - psi_truth
        sum_sq_psi += float(np.sum(diff_psi * diff_psi))
        n_psi += len(psi_truth)
    yr_mse = sum_sq_yr / max(n_yr, 1)
    psi_mse = sum_sq_psi / max(n_psi, 1)
    return yr_mse + lam * psi_mse


def fit_platform(segs, L, lam=0.5):
    x0 = np.array([1.0, 0.0, 0.0, 0.002, 0.05])
    bnds = [(0.5, 2.0), (-3.0, 3.0), (-0.05, 0.05), (-0.005, 0.02), (0.0, 0.3)]
    res = minimize(loss, x0, args=(segs, L, 2.0, lam), method="L-BFGS-B", bounds=bnds,
                   options={"maxiter": 300, "ftol": 1e-11})
    return res


all_paths = sorted((ROOT / "data" / "sim" / "segments").glob("FORD_*/**/sim.csv"))
train, dev = split(all_paths, dev_fraction=0.25, seed=42)

results = {}
for plat, L in L_BY_PLATFORM.items():
    train_plat = [p for p in train if plat in str(p)]
    print(f"\n--- {plat} (L={L}) ---")
    segs = load_arrays(train_plat)
    res = fit_platform(segs, L, lam=1.0)
    g0, g2, delta0, K_us, tau = res.x
    print(f"  g0={g0:.4f}, g2={g2:.4f}, delta0={delta0:.5f}, K_us={K_us:.5f}, tau={tau:.4f}")
    print(f"  combined loss={res.fun:.7f}")
    results[plat] = dict(g0=g0, g2=g2, delta0=delta0, K_us=K_us, tau=tau, L=L)


def predict_fit(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    if platform not in results:
        out["yaw_rate_pred_rads"] = sim_df.get("yaw_rate_pred_rads", 0.0).astype(float)
        return out
    p = results[platform]
    t = sim_df["t_s"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    yr_ss = yr_steady_poly(d, v, p["g0"], p["g2"], p["delta0"], p["K_us"], p["L"])
    yr = apply_lag_vec(yr_ss, t, p["tau"])
    out["yaw_rate_pred_rads"] = yr
    return out


dev_score = score(predict_fit, segment_paths=dev)
print("\n=== CTE-aware fit (lam=1.0) on dev ===")
print(f"yaw RMSE: {dev_score['yaw_rate_rmse']:.6f}")
print(f"CTE RMSE: {dev_score['cte_rmse']:.4f}")
print(f"Per-platform: {dev_score['per_platform']}")

with open(ROOT / "scratch" / "coeffs_cte.json", "w") as fh:
    json.dump(results, fh, indent=2)
