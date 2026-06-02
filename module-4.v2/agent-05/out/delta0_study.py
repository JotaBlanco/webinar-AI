"""Find better δ0 estimator. Compare V1's median(δ when yr_v0 small) vs alternatives.

Per-segment truth-based δ0: the δ0 that minimises segment mean(pred-truth).
That's the 'oracle' δ0 — only useful as upper bound.

Goal: find a calibration-free δ0 estimator that approaches the oracle.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")

PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": {"g":0.831,"L_eff":2.089,"K_us":0.00177,"tau":0.0645},
    "HYUNDAI_IONIQ_5":         {"g":0.958,"L_eff":2.959,"K_us":0.00284,"tau":0.0537},
    "FORD_F_150_LIGHTNING_MK1":{"g":0.865,"L_eff":3.274,"K_us":0.00339,"tau":0.0585},
}


def simulate(df, g, L_eff, K_us, tau, delta0):
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


def estimate_delta0_v1(df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(df.loc[mask, "delta_road_rad"]))


def estimate_delta0_robust(df, fallback=0.0, v_thresh=5.0):
    """All straight-ish samples weighted by inverse |yr_v0|."""
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    d = df["delta_road_rad"].to_numpy()
    mask = (v > v_thresh)
    if mask.sum() < 50: return fallback
    # Weight ~ exp(-|yr_v0|/scale)
    w = np.exp(-np.abs(yr_v0[mask]) / 0.02)
    if w.sum() < 10: return fallback
    return float(np.sum(d[mask]*w)/np.sum(w))


def estimate_delta0_oracle(df, p):
    """Find δ0 that zeroes mean residual against truth. For comparison only."""
    yr_truth = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    mask = v > 2.0
    # Scan
    best_d0, best_e = 0.0, 1e18
    for d0 in np.linspace(-0.02, 0.02, 401):
        yr = simulate(df, p["g"], p["L_eff"], p["K_us"], p["tau"], d0)
        e = (yr - yr_truth)[mask].mean()
        if abs(e) < abs(best_e):
            best_e = e; best_d0 = d0
    return best_d0


for plat in ["FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "FORD_F_150_LIGHTNING_MK1"]:
    seg_root = ROOT / "data" / "sim" / "segments" / plat
    paths = sorted(seg_root.glob("**/sim.csv"))
    # Stride
    paths = paths[::max(1,len(paths)//40)][:40]
    p = PARAMS[plat]
    rows = []
    for sp in paths:
        df = pd.read_csv(sp, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        if len(df) < 500: continue
        d0_v1 = estimate_delta0_v1(df)
        d0_rob = estimate_delta0_robust(df)
        d0_orc = estimate_delta0_oracle(df, p)
        rows.append((d0_v1, d0_rob, d0_orc))
    arr = np.array(rows)
    print(f"\n{plat}:  n={len(arr)}")
    print(f"  v1 vs oracle MAE: {np.mean(np.abs(arr[:,0]-arr[:,2])):.5f}")
    print(f"  robust vs oracle MAE: {np.mean(np.abs(arr[:,1]-arr[:,2])):.5f}")
    print(f"  oracle mean: {arr[:,2].mean():+.5f}  std: {arr[:,2].std():.5f}")
    print(f"  v1 mean: {arr[:,0].mean():+.5f}  robust mean: {arr[:,1].mean():+.5f}")
