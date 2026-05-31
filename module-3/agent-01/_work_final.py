"""Final evaluation with deterministic split. Try all variants and pick best."""
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
print(f"train n={len(tr)} dev n={len(dv)}")
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


# Approach A: joint fit (V1)
A = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    L = L_MAP[plat]
    delta, v, yr = load_concat(tr, plat)

    def resid(params, delta, v, yr, L):
        g, kus, d0 = params
        return v * g * (delta - d0) / (L + kus * v**2) - yr

    res = least_squares(resid, [1.0, 0.003, 0.0], args=(delta, v, yr, L),
                        bounds=([0.5, -0.005, -0.05], [2.0, 0.030, 0.05]), max_nfev=500)
    g, kus, d0 = res.x
    A[plat] = {'g': float(g), 'K_us': float(kus), 'delta_0': float(d0), 'L': L}
print("A (joint):", A)


# Approach B: two-stage (d0 from straight, g/K_us from rest)
B = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    L = L_MAP[plat]
    delta, v, yr = load_concat(tr, plat)
    m_str = np.abs(yr) < 0.003
    d0 = float(np.mean(delta[m_str]))

    def resid(params, delta, v, yr, L, d0):
        g, kus = params
        return v * g * (delta - d0) / (L + kus * v**2) - yr

    res = least_squares(resid, [1.0, 0.003], args=(delta, v, yr, L, d0),
                        bounds=([0.5, -0.005], [2.0, 0.030]), max_nfev=500)
    g, kus = res.x
    B[plat] = {'g': float(g), 'K_us': float(kus), 'delta_0': d0, 'L': L}
print("B (2stage):", B)


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


def make_predict(coeffs, tau):
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


def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out


# Baseline
r0 = score(v0, segment_paths=dv)
print(f"\nV0 dev: yaw={r0['yaw_rate_rmse']:.5f} CTE={r0['cte_rmse']:.3f}")
for k, vv in r0['per_platform'].items():
    print(f"   {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")

# All variants
variants = {
    'A_tau0': (A, 0.0),
    'A_tau05': (A, 0.05),
    'A_tau08': (A, 0.08),
    'A_tau10': (A, 0.10),
    'B_tau0': (B, 0.0),
    'B_tau05': (B, 0.05),
    'B_tau08': (B, 0.08),
}
# Mixed: Lightning from A, Mach-E from B (or vice versa)
M_AB = {'FORD_F_150_LIGHTNING_MK1': A['FORD_F_150_LIGHTNING_MK1'],
        'FORD_MUSTANG_MACH_E_MK1': B['FORD_MUSTANG_MACH_E_MK1']}
M_BA = {'FORD_F_150_LIGHTNING_MK1': B['FORD_F_150_LIGHTNING_MK1'],
        'FORD_MUSTANG_MACH_E_MK1': A['FORD_MUSTANG_MACH_E_MK1']}
variants['MAB_tau08'] = (M_AB, 0.08)
variants['MBA_tau08'] = (M_BA, 0.08)

for name, (c, tau) in variants.items():
    p = make_predict(c, tau)
    r = score(p, segment_paths=dv)
    pp = r['per_platform']
    L = pp.get('FORD_F_150_LIGHTNING_MK1', {})
    M = pp.get('FORD_MUSTANG_MACH_E_MK1', {})
    print(f"{name}: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f} | L: y={L.get('yaw_rate_rmse',0):.5f} c={L.get('cte_rmse',0):.2f} | M: y={M.get('yaw_rate_rmse',0):.5f} c={M.get('cte_rmse',0):.2f}")

import json
print("\nCoefficient sets:")
print("A:", json.dumps(A, indent=2))
print("B:", json.dumps(B, indent=2))
