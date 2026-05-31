"""Fit a per-platform understeer gradient + steering scale + bias.

Linear bicycle steady-state: psi_dot = v * delta / (L + K * v^2)
We also try a more general linear fit:
    psi_dot_pred = a * delta * v / (1 + b * v^2)  (single-gain)
or:
    psi_dot_pred = (alpha * delta + beta * delta * v * v) ... we'll do scaled.

Easiest robust approach:
    Let r_kin = delta / (L + K * v^2) * v  (one-parameter K, with L known)
    Choose K by least squares to minimize psi_dot - psi_dot_meas.

We also allow a steering scale s (effective steering ratio correction) and a yaw-rate bias b0:
    psi_dot_pred = s * v * delta / (L + K * v^2) + b0

Closed-form for K is nonlinear; use a small grid search + linear fit for (s, b0) per K.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')

WB = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'TESLA_MODEL_3': 2.875,
}

paths = sorted((ROOT / 'data/sim/segments').glob('FORD_*/**/sim.csv'))


def load_platform(platform):
    rows_v, rows_d, rows_yr = [], [], []
    for p in paths:
        if p.resolve().parents[3].name != platform:
            continue
        df = pd.read_csv(p, usecols=['v_mps', 'delta_road_rad', 'yaw_rate_meas_rads'])
        # only use samples where v > 2 (matches scoring filter)
        m = df['v_mps'].values > 2.0
        rows_v.append(df['v_mps'].values[m])
        rows_d.append(df['delta_road_rad'].values[m])
        rows_yr.append(df['yaw_rate_meas_rads'].values[m])
    return np.concatenate(rows_v), np.concatenate(rows_d), np.concatenate(rows_yr)


def fit_one(v, delta, yr_meas, L):
    """Grid-search K, then closed-form for s,b0."""
    # baseline V0 reference: pred0 = (v/L) * tan(delta)
    # Try: yr_model(s, K, b0) = s * v * delta / (L + K * v^2) + b0
    best = None
    for K in np.linspace(-0.005, 0.02, 51):
        feat = v * delta / (L + K * v * v)  # nonzero only if delta != 0
        # Linear regression: yr_meas = s * feat + b0
        # use least squares
        A = np.vstack([feat, np.ones_like(feat)]).T
        sol, res, rank, sv = np.linalg.lstsq(A, yr_meas, rcond=None)
        s, b0 = sol
        pred = s * feat + b0
        rmse = float(np.sqrt(np.mean((pred - yr_meas) ** 2)))
        if best is None or rmse < best[0]:
            best = (rmse, K, s, b0)
    return best


for plat in ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1']:
    print(f'\n== {plat} ==')
    v, d, yr = load_platform(plat)
    print(f'  samples: {len(v):,}')
    L = WB[plat]
    # V0 RMSE
    v0_pred = (v / L) * np.tan(d)
    v0_rmse = float(np.sqrt(np.mean((v0_pred - yr) ** 2)))
    print(f'  V0 yr_rmse (v>2): {v0_rmse:.6f}')
    rmse, K, s, b0 = fit_one(v, d, yr, L)
    print(f'  best K={K:.5f}  s={s:.5f}  b0={b0:.6e}  rmse={rmse:.6f}')
    # also try no-bias version
    best = None
    for K in np.linspace(-0.005, 0.02, 51):
        feat = v * d / (L + K * v * v)
        # least-sq s only:
        s = float(np.dot(feat, yr) / np.dot(feat, feat))
        pred = s * feat
        rmse2 = float(np.sqrt(np.mean((pred - yr) ** 2)))
        if best is None or rmse2 < best[0]:
            best = (rmse2, K, s)
    print(f'  no-bias: K={best[1]:.5f} s={best[2]:.5f} rmse={best[0]:.6f}')
