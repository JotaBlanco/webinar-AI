"""Explore relationship between V0 yaw pred, measured yaw, and inputs.

Look for systematic scale and lag biases per platform.
"""
import sys
sys.path.insert(0, 'skills/load-segments')
from load import load
import numpy as np
import pandas as pd

for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    dfs = load(platform=plat)
    print(f'\n=== {plat} ===  n_segments={len(dfs)}')
    # concat with v_mps > 2 mask
    all_v = []
    all_delta = []
    all_yt = []
    all_yp = []
    all_dt_means = []
    for df in dfs:
        v = df['v_mps'].values
        m = v > 2.0
        all_v.append(v[m])
        all_delta.append(df['delta_road_rad'].values[m])
        all_yt.append(df['yaw_rate_meas_rads'].values[m])
        all_yp.append(df['yaw_rate_pred_rads'].values[m])
        dt = np.diff(df['t_s'].values)
        all_dt_means.append(dt.mean())
    v = np.concatenate(all_v); delta = np.concatenate(all_delta)
    yt = np.concatenate(all_yt); yp = np.concatenate(all_yp)
    print(f'  median dt: {np.median(all_dt_means):.5f}s  samples (v>2): {len(v)}')
    # Linear fit yt = a * yp
    a = np.sum(yt * yp) / np.sum(yp * yp)
    print(f'  best scale a (yt ~ a*yp): {a:.4f}')
    # RMSE after scale
    rmse0 = np.sqrt(np.mean((yp - yt)**2))
    rmse1 = np.sqrt(np.mean((a*yp - yt)**2))
    print(f'  RMSE V0: {rmse0:.5f}  after scale: {rmse1:.5f}')
    # Lag analysis: shift yp by k samples, find best
    best_k = 0
    best_rmse = rmse0
    for k in range(-5, 6):
        if k > 0:
            yp_s = np.roll(yp, k); yt_s = yt
            yp_s = yp_s[k:]; yt_s = yt[k:]
        elif k < 0:
            yt_s = yt[:k]; yp_s = yp[-k:]
            # Wait that's confusing; just do shift on yp with no roll
            yp_s = yp[:k]; yt_s = yt[-k:]
        else:
            yp_s = yp; yt_s = yt
        rms = np.sqrt(np.mean((yp_s - yt_s)**2))
        if rms < best_rmse:
            best_rmse = rms; best_k = k
    print(f'  best lag (samples): {best_k}  RMSE: {best_rmse:.5f}')
    # Affine fit with delta: yt = a*v*tan(delta)/L_eff + bias
    # Examine v*tan(delta) vs yt directly to estimate effective L
    # yt should equal (v/L)*tan(delta) under KS
    # so L_eff = mean(v*tan(delta)) / mean(yt) -- use ratio
    vtd = v * np.tan(delta)
    # least squares: yt = (1/L_eff) * v*tan(delta)
    # plus offset for understeer
    A = np.column_stack([vtd, np.ones_like(vtd)])
    coef, *_ = np.linalg.lstsq(A, yt, rcond=None)
    inv_L = coef[0]; offset = coef[1]
    L_eff = 1.0/inv_L if inv_L != 0 else float('inf')
    print(f'  L_eff from fit: {L_eff:.3f} m  offset: {offset:.5e}')
    # With v*tan(delta)/L_eff residual rmse
    pred_lin = (vtd/L_eff) + offset
    rmse_lin = np.sqrt(np.mean((pred_lin - yt)**2))
    print(f'  RMSE linear fit (1-param L_eff): {rmse_lin:.5f}')
    # Slip-angle aware: yt = v*tan(delta)/L / (1 + (v/v_ch)^2)  (understeer)
    # Try grid of v_ch (characteristic speeds)
    base = vtd / 2.984  # nominal wheelbase mach-e
    if plat.startswith('FORD_F_150'):
        L0 = 3.70
    else:
        L0 = 2.984
    base = vtd / L0
    # solve yt = base / (1 + (v/v_ch)^2). Solve for v_ch by least sq
    best_vch = None
    best_rms = 1e9
    for vch in np.arange(10, 80, 2):
        pred = base / (1 + (v/vch)**2)
        r = np.sqrt(np.mean((pred - yt)**2))
        if r < best_rms:
            best_rms = r; best_vch = vch
    print(f'  Understeer fit: v_ch={best_vch}  RMSE: {best_rms:.5f}')
