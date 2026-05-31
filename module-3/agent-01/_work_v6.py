"""V6: Best-of-both — V1 Lightning + V5 Mach-E."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'skills/score-model')
from split import split
from score import score
import pandas as pd
import numpy as np

tr, dv = split(dev_fraction=0.25, seed=42)

COEFFS = {
    # V1 joint fit
    'FORD_F_150_LIGHTNING_MK1': {'g': 0.9637434201304231, 'K_us': 0.0035947144818903242,
                                  'delta_0': 0.0012339825423108163, 'L': 3.7},
    # V5 two-stage fit
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


def make_predict(coeffs, tau=0.08):
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


for tau in [0.0, 0.05, 0.08, 0.10, 0.12]:
    p = make_predict(COEFFS, tau=tau)
    r = score(p, segment_paths=dv)
    print(f"V6 mixed tau={tau}: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f}")
    for k, vv in r['per_platform'].items():
        print(f"   {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")

# Also run on full data (train+dev) for completeness
print("\n=== Full scoring (all FORD segments) ===")
p = make_predict(COEFFS, tau=0.08)
r = score(p)
print(f"V6 mixed tau=0.08 FULL: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f}")
for k, vv in r['per_platform'].items():
    print(f"   {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")
print(f"per_regime: {r['per_regime']}")
