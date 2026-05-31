"""Fit per-platform understeer model and yaw-rate lag on train, evaluate on dev."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

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


def yr_steady(delta_road, v, g, delta0, K_us, L):
    """Steady-state understeer model."""
    return v * (g * delta_road + delta0) / (L + K_us * v * v)


def apply_lag(yr_ss, t, tau):
    """First-order lag: yr[k+1] = yr[k] + dt/tau * (yr_ss[k] - yr[k])."""
    if tau <= 1e-4:
        return yr_ss.copy()
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    for k in range(n - 1):
        alpha = dt[k] / max(tau, 1e-4)
        if alpha > 1.0:
            alpha = 1.0
        y[k + 1] = y[k] + alpha * (yr_ss[k] - y[k])
    return y


def apply_lag_vec(yr_ss, t, tau):
    """Vectorized exponential moving average for non-uniform dt."""
    if tau <= 1e-4:
        return yr_ss.copy()
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    alpha = np.clip(dt / tau, 0.0, 1.0)
    for k in range(n - 1):
        y[k + 1] = y[k] + alpha[k] * (yr_ss[k] - y[k])
    return y


def load_arrays(paths):
    """Load (t, v, delta_road, yr_meas) for each segment."""
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


def predict_one(t, v, delta, params, L):
    g, delta0, K_us, tau = params
    yr_ss = yr_steady(delta, v, g, delta0, K_us, L)
    return apply_lag_vec(yr_ss, t, tau)


def loss(params, segs, L, v_thr=2.0):
    g, delta0, K_us, tau = params
    sum_sq = 0.0
    n_total = 0
    for (t, v, d, yr) in segs:
        yr_pred = predict_one(t, v, d, params, L)
        mask = v > v_thr
        diff = yr_pred[mask] - yr[mask]
        sum_sq += float(np.sum(diff * diff))
        n_total += int(mask.sum())
    return sum_sq / max(n_total, 1)


def fit_platform(segs, L):
    """Fit (g, delta0, K_us, tau) by minimizing pooled yaw-rate MSE."""
    x0 = np.array([1.0, 0.0, 0.002, 0.05])
    bnds = [(0.5, 2.0), (-0.05, 0.05), (-0.005, 0.02), (0.0, 0.3)]
    res = minimize(loss, x0, args=(segs, L), method="L-BFGS-B", bounds=bnds,
                   options={"maxiter": 200, "ftol": 1e-10})
    return res


# Build train/dev split
all_paths = sorted((ROOT / "data" / "sim" / "segments").glob("FORD_*/**/sim.csv"))
train, dev = split(all_paths, dev_fraction=0.25, seed=42)

results = {}
for plat, L in L_BY_PLATFORM.items():
    train_plat = [p for p in train if plat in str(p)]
    print(f"\n--- {plat} (L={L}, n_train_segs={len(train_plat)}) ---")
    segs = load_arrays(train_plat)
    res = fit_platform(segs, L)
    g, delta0, K_us, tau = res.x
    print(f"  fit: g={g:.4f}, delta0={delta0:.5f}, K_us={K_us:.5f}, tau={tau:.4f}")
    print(f"  train MSE={res.fun:.7f}  train RMSE={np.sqrt(res.fun):.5f}")
    results[plat] = {"g": g, "delta0": delta0, "K_us": K_us, "tau": tau, "L": L}

# Save coeffs as JSON
import json
out_path = ROOT / "scratch" / "coeffs.json"
with out_path.open("w") as fh:
    json.dump(results, fh, indent=2)
print(f"\nSaved coeffs to {out_path}")

# Now score on dev
def predict_fit(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    if platform not in results:
        out["yaw_rate_pred_rads"] = sim_df.get("yaw_rate_pred_rads", 0.0).astype(float)
        return out
    p = results[platform]
    t = sim_df["t_s"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    yr_ss = yr_steady(d, v, p["g"], p["delta0"], p["K_us"], p["L"])
    yr = apply_lag_vec(yr_ss, t, p["tau"])
    out["yaw_rate_pred_rads"] = yr
    return out


dev_score = score(predict_fit, segment_paths=dev)
print("\n=== Per-platform fit on dev ===")
print(f"yaw RMSE: {dev_score['yaw_rate_rmse']:.6f}")
print(f"CTE RMSE: {dev_score['cte_rmse']:.4f}")
print(f"Per-platform: {dev_score['per_platform']}")
print(f"Per-regime:   {dev_score['per_regime']}")
