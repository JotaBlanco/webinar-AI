"""Diagnose V1 residuals on Mach-E dev."""
import json, sys
import numpy as np
import pandas as pd

with open('artifacts/split.json') as f:
    split = json.load(f)
dev = [p for p in split['dev'] if 'MACH_E' in p]

with open('artifacts/coeffs.json') as f:
    coeffs = json.load(f)
c = coeffs['FORD_MUSTANG_MACH_E_MK1']

def yr_phys(v, delta, t):
    g, d0, Le, K, tau = c['g'], c['delta0'], c['L_eff'], c['K_us'], c['tau']
    yr_ss = v * (g * (delta - d0)) / (Le + K * v * v)
    dt = np.diff(t); dt = np.append(dt, dt[-1])
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for k in range(len(yr_ss)-1):
        a = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + a * (yr_ss[k+1] - yr[k])
    return yr

per_seg_bias = []
per_seg_rmse = []
for p in dev:
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(float)
    delta = df['delta_road_rad'].to_numpy(float)
    t = df['t_s'].to_numpy(float)
    yr_t = df['yaw_rate_meas_rads'].to_numpy(float)
    yr_p = yr_phys(v, delta, t)
    m = v > 2.0
    r = yr_p[m] - yr_t[m]
    per_seg_bias.append(np.mean(r))
    per_seg_rmse.append(np.sqrt(np.mean(r*r)))
print('Mach-E dev segments:', len(dev))
print('per-seg bias mean ± std:', np.mean(per_seg_bias), '±', np.std(per_seg_bias))
print('per-seg bias min/max:', min(per_seg_bias), max(per_seg_bias))
print('per-seg RMSE mean:', np.mean(per_seg_rmse))
# Distribution of biases
print('|bias|>0.002 count:', np.sum(np.abs(per_seg_bias)>0.002))
