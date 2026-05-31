"""V5: Refit with weighted SS that emphasizes lower bias.

Idea: a small systematic bias on straight rows accumulates into CTE.
Heavily weight low-yaw-rate samples (straight driving) when fitting d0,
then fit g and K_us using cornering samples.

Two-stage approach:
1. Fit d0 from samples with |yr_meas| < 0.005 (long straight).
   d0 = mean(delta) on those rows (because v*g*(delta-d0)/(L+Kus v^2) ~ 0 when delta=d0).
2. Fit g and K_us on cornering samples (|yr_meas| > 0.01) with d0 fixed.
"""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'code')
from split import split
from score import score
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
import parameters as P

tr, dv = split(dev_fraction=0.25, seed=42)
L_MAP = {'FORD_F_150_LIGHTNING_MK1': P.F150_LIGHTNING.L,
         'FORD_MUSTANG_MACH_E_MK1': P.MACH_E.L}


def platform_from_path(p):
    return Path(p).resolve().parents[3].name


def load_concat(paths, plat):
    deltas, vs, yrs = [], [], []
    for p in paths:
        if platform_from_path(p) != plat:
            continue
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        m = (df['v_mps'] > 5).values
        deltas.append(df['delta_road_rad'].values[m])
        vs.append(df['v_mps'].values[m])
        yrs.append(df['yaw_rate_meas_rads'].values[m])
    return np.concatenate(deltas), np.concatenate(vs), np.concatenate(yrs)


v5_coeffs = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    L = L_MAP[plat]
    delta, v, yr = load_concat(tr, plat)

    # Stage 1: fit d0 on straight samples
    m_str = np.abs(yr) < 0.003
    # On straights: yr ~ v*g*(delta - d0)/L  => when yr=0, delta=d0
    # Use weighted mean: d0 = weighted mean of delta among straight rows
    d0 = float(np.mean(delta[m_str]))
    print(f"{plat}: straight n={m_str.sum()}, d0={d0:.6f}")

    # Stage 2: fit g, K_us with d0 fixed on full data, but emphasize cornering
    def resid(params, delta, v, yr, L, d0):
        g, kus = params
        pred = v * g * (delta - d0) / (L + kus * v**2)
        return pred - yr
    res = least_squares(resid, [1.0, 0.003], args=(delta, v, yr, L, d0),
                        bounds=([0.5, -0.005], [2.0, 0.030]), max_nfev=500)
    g, kus = res.x
    print(f"  Stage2 g={g:.4f} Kus={kus:.5f}")

    # Verify residual on straight rows is now near zero
    pred = v * g * (delta - d0) / (L + kus * v**2)
    print(f"  Mean resid (full): {np.mean(yr - pred):.6f}")
    print(f"  Mean resid (straight): {np.mean((yr - pred)[m_str]):.6f}")
    print(f"  RMSE: {np.sqrt(np.mean((yr-pred)**2)):.5f}")

    v5_coeffs[plat] = {'g': float(g), 'K_us': float(kus), 'delta_0': float(d0), 'L': L}


def steady_state(delta, v, c):
    return v * c['g'] * (delta - c['delta_0']) / (c['L'] + c['K_us'] * v**2)


def apply_lag(yr_ss, t, tau):
    if tau <= 0:
        return yr_ss
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    for i in range(1, len(yr_ss)):
        dt = t[i] - t[i-1]
        alpha = dt / (tau + dt)
        y[i] = y[i-1] + alpha * (yr_ss[i] - y[i-1])
    return y


def make_predict(coeffs, tau=0.05):
    def predict(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
            return out
        c = coeffs[platform]
        delta = sim_df['delta_road_rad'].values.astype(float)
        v = sim_df['v_mps'].values.astype(float)
        t = sim_df['t_s'].values.astype(float)
        yr_ss = steady_state(delta, v, c)
        yr = apply_lag(yr_ss, t, tau)
        out['yaw_rate_pred_rads'] = yr
        return out
    return predict


print("\nDev scoring:")
for tau in [0.0, 0.05, 0.08, 0.10]:
    p = make_predict(v5_coeffs, tau=tau)
    r = score(p, segment_paths=dv)
    print(f"V5 d0-from-straight tau={tau}: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f}")
    for k, vv in r['per_platform'].items():
        print(f"   {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")

import json
print("\nV5 COEFFS:")
print(json.dumps(v5_coeffs, indent=2))
