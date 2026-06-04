"""Per-platform feature regression + check delta lag."""
import pandas as pd
import numpy as np
import glob

L_BY = {
    'HYUNDAI_IONIQ_5': 3.0,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'TESLA_MODEL_3': 2.875,
}

def load_concat(plat, limit=None):
    files = glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/{plat}/*/*/*/sim.csv')
    if limit:
        files = files[:limit]
    return files

def feature_rmse(plat, n_segs=100, lag=0):
    L = L_BY[plat]
    files = load_concat(plat, limit=n_segs)
    all_v=[]; all_d=[]; all_yr=[]; all_a=[]
    for f in files:
        df = pd.read_csv(f, usecols=['v_mps','delta_road_rad','yaw_rate_meas_rads','a_long_mps2'])
        # apply lag: shift delta by 'lag' steps (positive lag => delta leads -> use earlier delta for current yaw)
        if lag != 0:
            df['delta_road_rad'] = df['delta_road_rad'].shift(lag).bfill().ffill()
        all_v.append(df['v_mps'].values)
        all_d.append(df['delta_road_rad'].values)
        all_yr.append(df['yaw_rate_meas_rads'].values)
        all_a.append(df['a_long_mps2'].values)
    v = np.concatenate(all_v); delta = np.concatenate(all_d); yr = np.concatenate(all_yr); a = np.concatenate(all_a)
    mask = (v > 1.0) & np.isfinite(yr)
    v=v[mask]; delta=delta[mask]; yr=yr[mask]; a=a[mask]

    # Approach 1: bicycle understeer fit
    from scipy.optimize import minimize
    def cost1(p):
        K, s, off = p
        pred = v * (s*delta + off) / (L + K * v**2)
        return float(np.mean((yr - pred)**2))
    res = minimize(cost1, x0=[0.002, 1.0, 0.0], method='Nelder-Mead')
    K,s,off = res.x
    pred = v * (s*delta + off) / (L + K * v**2)
    rmse_us = float(np.sqrt(np.mean((yr-pred)**2)))

    # Approach 2: rich linear
    from numpy.linalg import lstsq
    X = np.column_stack([v*np.tan(delta), (v**3)*np.tan(delta), v, np.ones_like(v), v*v*np.tan(delta)])
    coef,_,_,_ = lstsq(X, yr, rcond=None)
    pred2 = X @ coef
    rmse_lin = float(np.sqrt(np.mean((yr-pred2)**2)))
    return rmse_us, rmse_lin, (K,s,off), coef

for plat in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
    print(f'\n=== {plat} ===')
    for lag in [-3,-2,-1,0,1,2,3]:
        r1,r2,(K,s,off),coef = feature_rmse(plat, 100, lag=lag)
        print(f'  lag={lag:+d} (0.02s steps)  understeer-fit RMSE={r1:.5f}  rich-lin RMSE={r2:.5f}  K={K:.4f} s={s:.3f} off={off:.5f}')
