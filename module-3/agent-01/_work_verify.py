"""Verify V5 Mach-E coefficient result."""
import sys
sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'skills/score-model')
from split import split
from score import score
import pandas as pd
import numpy as np

tr, dv = split(dev_fraction=0.25, seed=42)

V5_FULL = {
    'FORD_F_150_LIGHTNING_MK1': {'g': 0.9596708684231632, 'K_us': 0.003415578983205188,
                                  'delta_0': 0.0007806803088181088, 'L': 3.7},
    'FORD_MUSTANG_MACH_E_MK1':  {'g': 1.1781424422965947, 'K_us': 0.002649713780248179,
                                  'delta_0': 0.0003430220043923017, 'L': 2.984},
}

V6_MIXED = {
    'FORD_F_150_LIGHTNING_MK1': {'g': 0.9637434201304231, 'K_us': 0.0035947144818903242,
                                  'delta_0': 0.0012339825423108163, 'L': 3.7},
    'FORD_MUSTANG_MACH_E_MK1':  {'g': 1.1781424422965947, 'K_us': 0.002649713780248179,
                                  'delta_0': 0.0003430220043923017, 'L': 2.984},
}


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


# Same Mach-E coeffs in both. Score on dev with Mach-E filter only.
p_v5 = make_predict(V5_FULL, tau=0.08)
p_v6 = make_predict(V6_MIXED, tau=0.08)

r_v5 = score(p_v5, segment_paths=dv, platform_filter='FORD_MUSTANG_MACH_E_MK1')
r_v6 = score(p_v6, segment_paths=dv, platform_filter='FORD_MUSTANG_MACH_E_MK1')
print(f"V5 mach-e only: yaw={r_v5['yaw_rate_rmse']:.5f} CTE={r_v5['cte_rmse']:.3f}")
print(f"V6 mach-e only: yaw={r_v6['yaw_rate_rmse']:.5f} CTE={r_v6['cte_rmse']:.3f}")
# These MUST be identical since predict for Mach-E is same.
