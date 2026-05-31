"""Analyze residuals to understand systematic error in V0."""
import sys
sys.path.insert(0, 'skills/score-model')
import numpy as np
import pandas as pd
from pathlib import Path
from score import _default_segment_paths, _platform_from_path

paths = _default_segment_paths()
print(f'Total segments: {len(paths)}')

# Load a sample and examine columns
sample = pd.read_csv(paths[0])
print('cols:', list(sample.columns))

# For each platform, fit a linear understeer correction:
# v / R = v / (L*(1+Ku*v^2)) * delta
# So yr_ideal = v*delta / L * 1/(1 + K*v^2)
# Or: yr_meas / yr_kin = 1/(1 + K*v^2)
# This is the steady-state understeer model.

# Aggregate per platform
for plat_filter in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    plat_paths = [p for p in paths if _platform_from_path(p) == plat_filter]
    print(f'\n=== {plat_filter} ({len(plat_paths)} segs) ===')
    # Gather statistics in straight, steady, transient regimes
    all_v = []
    all_delta = []
    all_yr_meas = []
    all_yr_kin = []
    for p in plat_paths[:30]:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        all_v.append(df['v_mps'].values)
        all_delta.append(df['delta_road_rad'].values)
        all_yr_meas.append(df['yaw_rate_meas_rads'].values)
        all_yr_kin.append(df['yaw_rate_pred_rads'].values)
    v = np.concatenate(all_v)
    d = np.concatenate(all_delta)
    yr_m = np.concatenate(all_yr_meas)
    yr_k = np.concatenate(all_yr_kin)

    # Filter to v > 5 m/s and |delta| > 0.005 (avoid noise)
    mask = (v > 5.0) & (np.abs(d) > 0.005)
    print(f'  n samples used: {mask.sum()}')

    # Look at residual structure
    resid = yr_m[mask] - yr_k[mask]
    print(f'  mean resid: {resid.mean():.5f}, std: {resid.std():.5f}')
    print(f'  ratio yr_m/yr_k: mean = {(yr_m[mask]/yr_k[mask]).mean():.3f}, median = {np.median(yr_m[mask]/yr_k[mask]):.3f}')

    # Fit K such that yr_m = yr_k / (1+K*v^2)
    # => yr_k/yr_m - 1 = K*v^2
    # only use steady-state-ish samples (sign agreement, no noise blow-up)
    r = yr_k[mask] / yr_m[mask]
    valid = (r > 0.3) & (r < 3.0)
    K_est = ((r[valid] - 1.0) / v[mask][valid]**2)
    print(f'  K (understeer) median: {np.median(K_est):.6f}, mean: {K_est.mean():.6f}')

    # Also fit a simpler linear scale: yr_m = a * yr_k
    a = (yr_m[mask] * yr_k[mask]).sum() / (yr_k[mask]**2).sum()
    print(f'  best linear scale a: {a:.4f}')

    # delta lag? Try shifting delta forward by a few samples (dt=0.02s)
    # Compute correlation at different lags
    yr_meas_all = yr_m[mask]
    # Use a per-segment lag estimate
    lags = []
    for arr_m, arr_k in zip(all_yr_meas, all_yr_kin):
        if len(arr_m) < 200:
            continue
        m_arr = np.array(arr_m)
        k_arr = np.array(arr_k)
        msk = (np.abs(k_arr) > 0.01)
        if msk.sum() < 50:
            continue
        # Search lags from -10 to 10 samples
        best_l = 0
        best_c = -np.inf
        for L in range(-10, 11):
            if L > 0:
                a1 = m_arr[L:]
                a2 = k_arr[:-L] if L > 0 else k_arr
            elif L < 0:
                a1 = m_arr[:L]
                a2 = k_arr[-L:]
            else:
                a1 = m_arr
                a2 = k_arr
            n = min(len(a1), len(a2))
            if n < 50:
                continue
            c = np.corrcoef(a1[:n], a2[:n])[0,1]
            if c > best_c:
                best_c = c
                best_l = L
        lags.append(best_l)
    print(f'  median best lag (samples): {np.median(lags) if lags else None}  mean: {np.mean(lags) if lags else None}')
