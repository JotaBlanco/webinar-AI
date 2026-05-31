"""Fit per-platform improved model:
   yaw_rate = v * (a * delta_lagged + b) / (L + K * v^2)
   where delta_lagged = delta shifted by n_lag samples (50Hz -> 0.02s/sample).
   Search lag in [0..15] samples, fit (a,b,K,L) jointly.
"""
import glob, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim/segments'
PLATFORMS = ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1', 'HYUNDAI_IONIQ_5']
L_PRIOR = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'HYUNDAI_IONIQ_5': 3.00,
    'TESLA_MODEL_3': 2.875,
}

def load_platform_arrays(p, max_segs=None):
    files = sorted(glob.glob(f'{ROOT}/{p}/*/*/*/sim.csv'))
    if max_segs:
        files = files[:max_segs]
    segs = []
    for f in files:
        df = pd.read_csv(f)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        segs.append((df['delta_road_rad'].values, df['v_mps'].values, df['yaw_rate_meas_rads'].values))
    return segs

def apply_lag(arr, n):
    """Shift array forward by n samples (predict uses delta from n samples ago)."""
    if n == 0:
        return arr
    out = np.empty_like(arr)
    out[:n] = arr[0]
    out[n:] = arr[:-n]
    return out

def predict_yr(delta, v, L, K, a, b):
    return v * (a * delta + b) / (L + K * v * v)

def loss_fn(params, segs, lag):
    L, K, a, b = params
    se = 0.0
    n = 0
    for D, V, Y in segs:
        Dl = apply_lag(D, lag)
        m = V > 1.0
        if not m.any(): continue
        pred = predict_yr(Dl[m], V[m], L, K, a, b)
        r = pred - Y[m]
        se += (r*r).sum()
        n += len(r)
    return se / max(n, 1)

results = {}
for p in PLATFORMS:
    segs = load_platform_arrays(p)
    print(f'\n=== {p} (segs={len(segs)}) ===')
    # baseline V0 RMSE (yaw_rate_pred_rads): re-compute the V0 with tan to be sure
    L0 = L_PRIOR[p]
    se=0; n=0
    for D,V,Y in segs:
        m = V > 1.0
        pred = V[m]*np.tan(D[m])/L0
        se += ((pred-Y[m])**2).sum(); n += m.sum()
    rmse_v0 = np.sqrt(se/n)
    print(f'V0 (tan, L={L0}): RMSE={rmse_v0:.5f}')

    best = None
    for lag in range(0, 16):
        x0 = np.array([L0, 0.003, 1.0, 0.0])
        # Bounds
        from scipy.optimize import minimize
        res = minimize(loss_fn, x0, args=(segs, lag),
                       method='Nelder-Mead',
                       options={'xatol':1e-6, 'fatol':1e-10, 'maxiter':2000})
        rmse = np.sqrt(res.fun)
        if best is None or rmse < best['rmse']:
            best = {'rmse': rmse, 'lag': lag, 'params': res.x.tolist()}
    print(f'best: lag={best["lag"]}, params (L,K,a,b)={best["params"]}, RMSE={best["rmse"]:.5f}')
    results[p] = best

# Also fit Tesla with no truth -> just use openpilot params, no fit. Use a sensible K from Ford avg.
K_avg = float(np.mean([results[p]['params'][1] for p in PLATFORMS]))
results['TESLA_MODEL_3'] = {
    'rmse': None,
    'lag': 0,
    'params': [L_PRIOR['TESLA_MODEL_3'], K_avg, 1.0, 0.0],
}
print(f'\nTesla fallback: L={L_PRIOR["TESLA_MODEL_3"]}, K={K_avg:.5f}, a=1, b=0, lag=0')

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/out/coefs.json', 'w') as f:
    json.dump(results, f, indent=2)
print('\nSaved coefs.json')
