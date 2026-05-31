"""Quick analysis of yaw-rate residuals for V0 across Ford segments."""
import sys, glob, collections
import numpy as np, pandas as pd

paths = sorted(glob.glob('data/sim/segments/FORD_*/**/sim.csv', recursive=True))
print('n_segments:', len(paths))

agg = collections.defaultdict(list)
for p in paths:
    plat = p.split('/segments/')[1].split('/')[0]
    if len(agg[plat]) > 60:
        continue
    df = pd.read_csv(p)
    agg[plat].append(df)

for plat, dfs in agg.items():
    d = pd.concat(dfs, ignore_index=True)
    d = d[d['v_mps'] > 5].reset_index(drop=True)
    yr_t = d['yaw_rate_meas_rads'].values
    yr_p = d['yaw_rate_pred_rads'].values
    v = d['v_mps'].values
    delta = d['delta_road_rad'].values
    ay = v * yr_t
    resid = yr_p - yr_t
    print(f'\n=== {plat}: n={len(d)} segs_sampled={len(dfs)} ===')
    print(f'  RMSE: {np.sqrt((resid**2).mean()):.5f}')
    print(f'  mean(resid)={resid.mean():.5f}  std(resid)={resid.std():.5f}')
    mask = np.abs(yr_t) > 0.02
    ratio = yr_p[mask] / yr_t[mask]
    ratio = ratio[(ratio > 0) & (ratio < 5)]
    print(f'  mean yr_pred/yr_truth (|yr|>0.02): {ratio.mean():.4f} median={np.median(ratio):.4f}')
    # Best scale: yr_truth = a * yr_pred
    a_best = np.sum(yr_p * yr_t) / np.sum(yr_p * yr_p)
    print(f'  best scale: yr_truth ≈ {a_best:.4f} * yr_pred')
    # Best affine in delta: yr_truth ≈ (v/L) * tan(k * (delta + d0)) — fit by k * tan(delta) scale
    # Actually fit: yr_truth = c * v * delta (linear bicycle low-speed approx)
    # Or fit understeer: 1/yr_truth = L/(v*delta) + K_us * v / g
    # Build regression on data with |delta|>0.005
    m2 = np.abs(delta) > 0.005
    # yr_truth/v as a function of delta and ay/g
    g = 9.81
    # Bicycle: delta = L/R + K_us * ay/g  => yr_truth = v / R; (v/yr_truth) = L/delta_eff... messy
    # Simpler: predict ratio (yr_truth / yr_pred) ~ 1 - K * v^2
    yr_p_nz = yr_p[m2]
    yr_t_nz = yr_t[m2]
    v_nz = v[m2]
    delta_nz = delta[m2]
    # Avoid division blow-ups
    mm = np.abs(yr_p_nz) > 0.005
    ratio2 = yr_t_nz[mm] / yr_p_nz[mm]
    v2 = v_nz[mm]
    # Fit: ratio2 ≈ a - b * v^2
    A = np.vstack([np.ones_like(v2), v2**2]).T
    coef, *_ = np.linalg.lstsq(A, ratio2, rcond=None)
    print(f'  fit yr_t/yr_p = {coef[0]:.4f} + {coef[1]:.6f} * v^2')
    # Also: yr_t/yr_p ≈ 1/(1 + K*v^2) ; equivalent to L/(L+K*L*v^2)... derive K_us:
    # Steady-state bicycle: yaw_rate = v*delta / (L + K_us*v^2)
    # So yr_t/yr_p = L/(L + K_us*v^2) ≈ 1 - (K_us/L)*v^2 for small v
    # From fit: -K_us/L ≈ coef[1]/coef[0]
    if plat == 'FORD_F_150_LIGHTNING_MK1':
        L = 3.70
    else:
        L = 2.984
    K_us_est = -coef[1] / coef[0] * L
    print(f'  implied K_us (understeer m) = {K_us_est:.5f} ; L={L}')
    # Also nonlinear fit: yr_t = v*delta / (L + K_us*v^2) — direct lstsq for K_us
    # rearrange: v*delta/yr_t = L + K_us*v^2
    m3 = np.abs(yr_t_nz) > 0.01
    lhs = (v_nz[m3] * delta_nz[m3]) / yr_t_nz[m3]
    rhs_v2 = v_nz[m3]**2
    A2 = np.vstack([np.ones_like(rhs_v2), rhs_v2]).T
    coef2, *_ = np.linalg.lstsq(A2, lhs, rcond=None)
    print(f'  direct fit v*delta/yr_t = {coef2[0]:.4f} + {coef2[1]:.5f}*v^2  (intercept ~ L)')
    # Steering offset: fit delta_offset such that yr_t = v/L * tan(delta - delta_offset) ≈ (v/L)*(delta-d0)
    # yr_t * L / v ≈ delta - d0  => d0 = delta - yr_t*L/v (mean)
    mm2 = (v_nz > 5) & (np.abs(delta_nz) > 0.001)
    d0 = (delta_nz[mm2] - yr_t_nz[mm2] * L / v_nz[mm2]).mean()
    print(f'  mean delta_offset estimate: {d0:.5f} rad ({np.degrees(d0):.3f} deg)')
