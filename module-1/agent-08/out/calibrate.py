"""Final calibration: per-platform (K, s, off, lag). Save coeffs.json."""
import pandas as pd
import numpy as np
import glob
import json
from scipy.optimize import minimize

L_BY = {
    'HYUNDAI_IONIQ_5': 3.0,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'TESLA_MODEL_3': 2.875,
}

def load_full(plat):
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/{plat}/*/*/*/sim.csv'))
    V=[]; YR=[]; segs=[]
    Ds = {lag: [] for lag in range(0, 8)}
    for f in files:
        df = pd.read_csv(f, usecols=['v_mps','delta_road_rad','yaw_rate_meas_rads'])
        V.append(df['v_mps'].values)
        YR.append(df['yaw_rate_meas_rads'].values)
        for lag in Ds:
            Ds[lag].append(df['delta_road_rad'].shift(lag).bfill().ffill().values)
    v = np.concatenate(V); yr = np.concatenate(YR)
    Ds = {lag: np.concatenate(arrs) for lag, arrs in Ds.items()}
    return v, yr, Ds

def fit_for_lag(v, yr, d, L):
    mask = (v>1.0) & np.isfinite(yr) & np.isfinite(d)
    vv=v[mask]; yy=yr[mask]; dd=d[mask]
    def cost(p):
        K,s,off = p
        pred = vv*(s*dd+off)/(L+K*vv**2)
        return float(np.mean((yy-pred)**2))
    res = minimize(cost, x0=[0.003, 1.0, 0.0], method='Nelder-Mead',
                   options={'xatol':1e-8,'fatol':1e-12,'maxiter':2000})
    K,s,off = res.x
    pred = vv*(s*dd+off)/(L+K*vv**2)
    rmse = float(np.sqrt(np.mean((yy-pred)**2)))
    return rmse, (K,s,off)

coeffs = {}
for plat in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
    L = L_BY[plat]
    print(f'\n=== {plat} (L={L}) ===')
    v, yr, Ds = load_full(plat)
    best = (1e9, None, None)
    for lag, d in Ds.items():
        rmse, params = fit_for_lag(v, yr, d, L)
        K,s,off = params
        print(f'  lag={lag} ({lag*20}ms)  RMSE={rmse:.5f}  K={K:.5f} s={s:.4f} off={off:+.6f}')
        if rmse < best[0]:
            best = (rmse, lag, params)
    rmse, lag, (K,s,off) = best
    coeffs[plat] = dict(L=L, K=K, s=s, off=off, lag=lag, rmse=rmse)
    print(f'  -> BEST lag={lag} RMSE={rmse:.5f}')

# Tesla: use a sensible prior. Median K across fitted platforms; identity scale; zero offset; lag from average.
fit_K_med = float(np.median([coeffs[p]['K'] for p in coeffs]))
fit_lag_med = int(round(np.median([coeffs[p]['lag'] for p in coeffs])))
coeffs['TESLA_MODEL_3'] = dict(L=2.875, K=fit_K_med, s=1.0, off=0.0, lag=fit_lag_med, rmse=None)
print(f'\nTesla (prior-only): K={fit_K_med:.5f}, lag={fit_lag_med}')

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/final-model/coeffs.json','w') as f:
    json.dump(coeffs, f, indent=2)

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/out/coeffs.json','w') as f:
    json.dump(coeffs, f, indent=2)

print('\nFinal coeffs:')
print(json.dumps(coeffs, indent=2))
