"""Check if there's an effective delay/lead between delta and yaw_rate, and whether
adding a first-order yaw-rate lag helps in transients.

Model variant: filter steady-state pred through a 1st-order low-pass:
    yr[k+1] = yr[k] + (dt / tau) * (yr_ss[k] - yr[k])
That should smooth out the transient overshoot.
"""
import sys
sys.path.insert(0, 'skills/load-segments')
from load import load
import numpy as np
from scipy.optimize import minimize_scalar, minimize
import json

with open('coeffs.json') as f:
    COEFFS = json.load(f)

for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    dfs = load(platform=plat)
    c = COEFFS[plat]
    Le, K, d0 = c['L_eff'], c['K'], c['d0']
    np.random.seed(42)
    idxs = list(range(len(dfs))); np.random.shuffle(idxs)
    n_tr = int(0.8*len(dfs)); train = set(idxs[:n_tr])

    # compute ss pred and y per-segment, then apply lag with various tau
    def total_sse_for_tau(tau, on_train):
        sse = 0.0
        n = 0
        for i, df in enumerate(dfs):
            if (i in train) != on_train:
                continue
            v = df['v_mps'].values
            d = df['delta_road_rad'].values
            y = df['yaw_rate_meas_rads'].values
            t = df['t_s'].values
            yss = v * (d - d0) / Le / (1.0 + K * v * v)
            yf = np.empty_like(yss)
            yf[0] = yss[0]
            if tau <= 1e-4:
                yf = yss
            else:
                for k in range(len(t)-1):
                    dt = t[k+1] - t[k]
                    alpha = dt / (tau + dt)
                    yf[k+1] = yf[k] + alpha * (yss[k+1] - yf[k])
            m = v > 2.0
            r = yf[m] - y[m]
            sse += float(np.sum(r*r))
            n += int(m.sum())
        return sse, n

    # Grid search tau
    best = None
    for tau in [0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]:
        sse, n = total_sse_for_tau(tau, on_train=True)
        rmse_tr = np.sqrt(sse/n)
        sse, n = total_sse_for_tau(tau, on_train=False)
        rmse_dv = np.sqrt(sse/n)
        print(f'{plat} tau={tau:.3f}  train RMSE={rmse_tr:.5f}  dev RMSE={rmse_dv:.5f}')
        if best is None or rmse_dv < best[1]:
            best = (tau, rmse_dv)
    print(f'  BEST tau on dev: {best}')
    COEFFS[plat]['tau'] = best[0]

with open('coeffs.json', 'w') as f:
    json.dump(COEFFS, f, indent=2)
print(COEFFS)
