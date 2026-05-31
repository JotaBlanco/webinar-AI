"""Look for systematic structure in V0 residuals — bias, scale, lag."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "load-segments"))

import os
os.chdir(ROOT)

import numpy as np
import pandas as pd
from load import load

for platform in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
    print(f"\n=== {platform} ===")
    dfs = load(platform=platform)
    print(f"  segments: {len(dfs)}")
    # Pool a few stats from a sample of segments
    all_yr_meas = []
    all_yr_pred = []
    all_v = []
    all_delta = []
    for df in dfs[:40]:
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        all_yr_meas.append(df["yaw_rate_meas_rads"].to_numpy())
        all_yr_pred.append(df["yaw_rate_pred_rads"].to_numpy())
        all_v.append(df["v_mps"].to_numpy())
        all_delta.append(df["delta_road_rad"].to_numpy())
    yr_meas = np.concatenate(all_yr_meas)
    yr_pred = np.concatenate(all_yr_pred)
    v = np.concatenate(all_v)
    delta = np.concatenate(all_delta)
    mask = v > 2.0
    resid = (yr_pred - yr_meas)[mask]
    print(f"  resid mean (pred-meas):   {resid.mean(): .5e}")
    print(f"  resid std:                {resid.std(): .5e}")
    print(f"  |yr_meas| mean:           {np.abs(yr_meas[mask]).mean(): .5e}")
    print(f"  |yr_pred| mean:           {np.abs(yr_pred[mask]).mean(): .5e}")
    # Slope of pred vs meas (regression through 0): does V0 over/under-predict?
    yp = yr_pred[mask]
    ym = yr_meas[mask]
    # Slope k where yp ~ k * ym (least squares through origin):
    k = np.sum(yp * ym) / np.sum(ym * ym)
    print(f"  yp ≈ {k:.4f} * ym  (slope through origin)")
    # Inverse: ym ~ k_inv * yp -> correction factor for pred
    k_inv = np.sum(yp * ym) / np.sum(yp * yp)
    print(f"  ym ≈ {k_inv:.4f} * yp  (i.e., to match truth, multiply pred by {k_inv:.4f})")
    # Speed-dependence of correction: bin by v
    print("  Correction factor by v-bin:")
    edges = [2, 6, 12, 18, 25, 35]
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (v >= lo) & (v < hi)
        if m.sum() < 100:
            continue
        ypb = yr_pred[m]
        ymb = yr_meas[m]
        denom = np.sum(ypb * ypb)
        if denom < 1e-9:
            continue
        kk = np.sum(ypb * ymb) / denom
        rmse_v0 = np.sqrt(((ypb - ymb)**2).mean())
        rmse_scaled = np.sqrt(((kk*ypb - ymb)**2).mean())
        print(f"    v in [{lo:>2},{hi:>2}): k={kk:.4f}, n={m.sum():>7d}, rmse_v0={rmse_v0:.5f}, rmse_scaled={rmse_scaled:.5f}")
    # Cross-correlation lag (yr_meas vs yr_pred) — coarse estimate over a single segment
    # Use Mach-E first transient-rich segment
    print("  Lag analysis on segments (lag in samples where pred matches meas best, dt~0.02):")
    for j, df in enumerate(dfs[:8]):
        v_s = df["v_mps"].to_numpy()
        if v_s.mean() < 5:
            continue
        ypm = df["yaw_rate_pred_rads"].to_numpy()
        ymm = df["yaw_rate_meas_rads"].to_numpy()
        # Detrend
        ypc = ypm - ypm.mean()
        ymc = ymm - ymm.mean()
        if ypc.std() < 1e-4 or ymc.std() < 1e-4:
            continue
        max_lag = 20
        best_lag = 0
        best_corr = -1e9
        for lag in range(-max_lag, max_lag + 1):
            if lag >= 0:
                a = ypc[:len(ypc)-lag]
                b = ymc[lag:]
            else:
                a = ypc[-lag:]
                b = ymc[:len(ymc)+lag]
            if len(a) < 50:
                continue
            c = np.sum(a*b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-12)
            if c > best_corr:
                best_corr = c
                best_lag = lag
        print(f"    seg {j}: best_lag={best_lag} samples (~{best_lag*0.02*1000:.0f} ms), corr={best_corr:.3f}, len={len(ypm)}")
