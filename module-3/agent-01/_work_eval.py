"""Build a predict() that uses fitted (g, K_us, delta_0) + optional first-order lag.
Evaluate on dev set vs V0."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'skills/make-train-dev-split')
from score import score
from split import split
import pandas as pd
import numpy as np

COEFFS = {
    'FORD_F_150_LIGHTNING_MK1': {'g': 0.9637434201304231, 'K_us': 0.0035947144818903242,
                                  'delta_0': 0.0012339825423108163, 'L': 3.7, 'tau': 0.0},
    'FORD_MUSTANG_MACH_E_MK1':  {'g': 1.1758194286274308, 'K_us': 0.0025190900693713852,
                                  'delta_0': -3.6482033317411595e-05, 'L': 2.984, 'tau': 0.0},
}


def steady_state(delta, v, c):
    return v * c['g'] * (delta - c['delta_0']) / (c['L'] + c['K_us'] * v**2)


def apply_lag(yr_ss, t, tau):
    """First-order low-pass: y' = (yr_ss - y)/tau, integrate explicitly."""
    if tau <= 0:
        return yr_ss
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    for i in range(1, len(yr_ss)):
        dt = t[i] - t[i-1]
        alpha = dt / (tau + dt)  # exponential smoothing factor
        y[i] = y[i-1] + alpha * (yr_ss[i] - y[i-1])
    return y


def make_predict(coeffs):
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
        yr = apply_lag(yr_ss, t, c['tau'])
        out['yaw_rate_pred_rads'] = yr
        return out
    return predict


tr, dv = split(dev_fraction=0.25, seed=42)


def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out


print("=== V0 on dev ===")
r0 = score(v0, segment_paths=dv)
print(f"  yaw RMSE: {r0['yaw_rate_rmse']:.5f}, CTE RMSE: {r0['cte_rmse']:.3f}")
for k, vv in r0['per_platform'].items():
    print(f"  {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")
print(f"  per_regime: {r0['per_regime']}")

print("\n=== V1: SS (no lag) on dev ===")
predict = make_predict(COEFFS)
r1 = score(predict, segment_paths=dv)
print(f"  yaw RMSE: {r1['yaw_rate_rmse']:.5f}, CTE RMSE: {r1['cte_rmse']:.3f}")
for k, vv in r1['per_platform'].items():
    print(f"  {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")
print(f"  per_regime: {r1['per_regime']}")

# Try a few tau values
for tau in [0.03, 0.05, 0.08, 0.12, 0.15]:
    cc = {k: {**v, 'tau': tau} for k, v in COEFFS.items()}
    p = make_predict(cc)
    r = score(p, segment_paths=dv)
    print(f"  V2 tau={tau:.2f}: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f}")
