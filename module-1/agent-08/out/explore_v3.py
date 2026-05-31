"""Wider lag sweep + full training data + Tesla approach."""
import pandas as pd
import numpy as np
import glob
from scipy.optimize import minimize

L_BY = {
    'HYUNDAI_IONIQ_5': 3.0,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'TESLA_MODEL_3': 2.875,
}

def features_for_seg(df, lag, L):
    # smoothed delta lag: shift -lag means take future delta
    d_lag = df['delta_road_rad'].shift(lag).bfill().ffill().values
    v = df['v_mps'].values
    yr = df['yaw_rate_meas_rads'].values if 'yaw_rate_meas_rads' in df else None
    return v, d_lag, yr

def evaluate(plat, lag, n_segs=None, scale_off_K=True):
    L = L_BY[plat]
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/{plat}/*/*/*/sim.csv'))
    if n_segs:
        files = files[:n_segs]
    V=[]; D=[]; YR=[]
    for f in files:
        df = pd.read_csv(f, usecols=['v_mps','delta_road_rad','yaw_rate_meas_rads'])
        v,d,yr = features_for_seg(df, lag, L)
        V.append(v); D.append(d); YR.append(yr)
    v=np.concatenate(V); d=np.concatenate(D); yr=np.concatenate(YR)
    mask = (v>1.0) & np.isfinite(yr) & np.isfinite(d)
    v=v[mask]; d=d[mask]; yr=yr[mask]

    # Model: yr = v * (s*d + off) / (L + K*v^2)
    def cost(p):
        K,s,off = p
        pred = v*(s*d+off)/(L+K*v**2)
        return float(np.mean((yr-pred)**2))
    res = minimize(cost, x0=[0.003, 1.0, 0.0], method='Nelder-Mead', options={'xatol':1e-7,'fatol':1e-10})
    K,s,off = res.x
    pred = v*(s*d+off)/(L+K*v**2)
    rmse = float(np.sqrt(np.mean((yr-pred)**2)))
    return rmse, (K,s,off)

# Full data, scan lag from 0 to 10
for plat in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
    print(f'\n=== {plat} ===')
    best = (1e9, None, None)
    for lag in range(0, 12):
        rmse,(K,s,off) = evaluate(plat, lag)
        print(f'  lag={lag:+d} ({lag*20} ms)  RMSE={rmse:.5f}  K={K:.5f} s={s:.4f} off={off:+.6f}')
        if rmse < best[0]:
            best = (rmse, lag, (K,s,off))
    print(f'  BEST: lag={best[1]} RMSE={best[0]:.5f} params={best[2]}')
