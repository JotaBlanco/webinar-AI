"""Diagnose Mach-E residuals more carefully — segment-by-segment offsets?"""
import sys, glob, json, random
import numpy as np, pandas as pd

sys.path.insert(0, 'skills/score-model')
from score import score

paths = sorted(glob.glob('data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv', recursive=True))

with open('final-model/coeffs.json') as fh:
    fits = json.load(fh)
f = fits['FORD_MUSTANG_MACH_E_MK1']

# For each segment compute the per-segment residual mean (bias) using the V1 bicycle predictor
per_seg = []
for p in paths:
    df = pd.read_csv(p)
    df = df[df['v_mps'] > 5]
    if len(df) < 50: continue
    v = df['v_mps'].values; delta = df['delta_road_rad'].values
    yr_t = df['yaw_rate_meas_rads'].values
    de = delta - f['delta_offset_rad']
    L = f['L_eff_m']; K = f['K_us']
    yr_pred = v * de / (L + K * v * v)
    resid = yr_pred - yr_t
    per_seg.append({
        'path': p, 'n': len(df),
        'mean_resid': resid.mean(),
        'std_resid': resid.std(),
        'rmse': np.sqrt((resid**2).mean()),
        'mean_v': v.mean(),
    })

ps = pd.DataFrame(per_seg)
print('per-segment stats:')
print(ps.describe())
print('\\nbias spread (sign-indicating per-segment offset):')
print('  mean of |mean_resid|:', ps['mean_resid'].abs().mean())
print('  std of mean_resid:', ps['mean_resid'].std())
print('  fraction with |bias| > 0.005:', (ps['mean_resid'].abs() > 0.005).mean())

# Try fitting per-segment delta_offset only and see if RMSE drops
yr_total_sq = 0.0; n_tot = 0
for p in paths:
    df = pd.read_csv(p)
    df = df[df['v_mps'] > 5]
    if len(df) < 50: continue
    v = df['v_mps'].values; delta = df['delta_road_rad'].values
    yr_t = df['yaw_rate_meas_rads'].values
    L = f['L_eff_m']; K = f['K_us']
    # Fit per-segment offset: minimize (v*(delta-d0)/(L+Kv^2) - yr_t)^2 over d0
    # Linear in d0: yr_pred = v*delta/(L+Kv^2) - v/(L+Kv^2) * d0
    denom = L + K * v * v
    a = v / denom         # coefficient of -d0
    b = v * delta / denom - yr_t  # residual when d0=0
    # min over d0:  sum (b - a*d0)^2 -> d0 = sum(a*b)/sum(a^2)
    d0_seg = float(np.sum(a * b) / np.sum(a * a))
    yr_pred = (v * (delta - d0_seg)) / denom
    r = yr_pred - yr_t
    yr_total_sq += np.sum(r**2)
    n_tot += len(r)

print(f'\\nIf each Mach-E segment had its own delta_offset fit, RMSE = {np.sqrt(yr_total_sq/n_tot):.5f}')
