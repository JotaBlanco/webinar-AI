"""Fit understeer model: yr_corrected = yr_v0 / (1 + (v/v_ch)^2) + optional lag.

Search v_ch and lag jointly per platform. Use train split.
"""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "load-segments"))

import os
os.chdir(ROOT)

import numpy as np
import pandas as pd
from load import load


def shift_pred(arr, lag):
    """Shift array forward by `lag` samples (so pred[t] becomes pred[t-lag]).
    Positive lag: introduce delay (pred at sample i was pred[i-lag] originally).
    """
    out = np.empty_like(arr)
    if lag == 0:
        return arr.copy()
    if lag > 0:
        out[:lag] = arr[0]
        out[lag:] = arr[:-lag]
    else:
        out[lag:] = arr[-1]
        out[:lag] = arr[-lag:]
    return out


def lowpass(arr, dt, tau):
    """1st-order low-pass with time constant tau (seconds)."""
    if tau <= 0:
        return arr.copy()
    alpha = dt / (tau + dt)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = out[i-1] + alpha * (arr[i] - out[i-1])
    return out


def lowpass_vec(arr, dt, tau):
    """Vectorised-ish low-pass with constant dt."""
    if tau <= 0:
        return arr.copy()
    alpha = dt / (tau + dt)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = out[i-1] * (1 - alpha) + arr[i] * alpha
    return out


for platform in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
    print(f"\n=== {platform} ===")
    dfs = load(platform=platform)
    # Use train half: first 70%
    n_train = int(len(dfs) * 0.7)
    dfs_train = dfs[:n_train]
    dfs_dev = dfs[n_train:]
    print(f"  train segs={len(dfs_train)}, dev segs={len(dfs_dev)}")

    # Search v_ch & tau jointly on a sample of train segments to keep it cheap.
    # For each candidate, compute pooled SSE over a subset.
    sample = dfs_train[::3]  # every third

    v_ch_grid = np.array([10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 35, 40, 50, 80, 1e9])
    tau_grid = np.array([0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20])

    best = None
    results = np.full((len(v_ch_grid), len(tau_grid)), np.nan)
    for i, v_ch in enumerate(v_ch_grid):
        for j, tau in enumerate(tau_grid):
            sse = 0.0
            n = 0
            for df in sample:
                v = df["v_mps"].to_numpy()
                yrp = df["yaw_rate_pred_rads"].to_numpy()
                yrm = df["yaw_rate_meas_rads"].to_numpy()
                t = df["t_s"].to_numpy()
                if len(t) < 2:
                    continue
                dt = float(np.median(np.diff(t)))
                # Understeer correction
                yrc = yrp / (1.0 + (v / v_ch)**2)
                # Lag via low-pass
                yrc = lowpass_vec(yrc, dt, tau)
                mask = v > 2.0
                resid = yrc[mask] - yrm[mask]
                sse += float(np.sum(resid**2))
                n += int(mask.sum())
            rmse = np.sqrt(sse / n) if n > 0 else np.inf
            results[i, j] = rmse
            if best is None or rmse < best[0]:
                best = (rmse, v_ch, tau)
    print(f"  Best on train subset: v_ch={best[1]}, tau={best[2]}, rmse={best[0]:.6f}")
    # Show the top few
    flat_idx = np.argsort(results.ravel())[:5]
    for idx in flat_idx:
        i, j = np.unravel_index(idx, results.shape)
        print(f"    v_ch={v_ch_grid[i]:>6}, tau={tau_grid[j]:.2f}, rmse={results[i,j]:.6f}")

    # Now apply best to dev set
    v_ch, tau = best[1], best[2]
    sse = 0.0
    n = 0
    sse_v0 = 0.0
    for df in dfs_dev:
        v = df["v_mps"].to_numpy()
        yrp = df["yaw_rate_pred_rads"].to_numpy()
        yrm = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        if len(t) < 2:
            continue
        dt = float(np.median(np.diff(t)))
        yrc = yrp / (1.0 + (v / v_ch)**2)
        yrc = lowpass_vec(yrc, dt, tau)
        mask = v > 2.0
        sse += float(np.sum((yrc[mask] - yrm[mask])**2))
        sse_v0 += float(np.sum((yrp[mask] - yrm[mask])**2))
        n += int(mask.sum())
    print(f"  Dev RMSE: v0={np.sqrt(sse_v0/n):.6f}, corrected={np.sqrt(sse/n):.6f}")
