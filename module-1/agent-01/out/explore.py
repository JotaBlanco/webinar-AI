"""Exploratory: baseline RMSE per platform, residual structure."""
import glob, os, json
import numpy as np
import pandas as pd

ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim/segments'
PLATFORMS_WITH_TRUTH = ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1', 'HYUNDAI_IONIQ_5']
# Tesla has no truth column.

L_MAP = {
    'TESLA_MODEL_3': 2.875,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'HYUNDAI_IONIQ_5': 3.00,  # assume similar; will refine
}

def load_platform(p, max_segs=None):
    files = sorted(glob.glob(f'{ROOT}/{p}/*/*/*/sim.csv'))
    if max_segs:
        files = files[:max_segs]
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df['_seg'] = f
        dfs.append(df)
    return dfs

for p in PLATFORMS_WITH_TRUTH:
    dfs = load_platform(p)
    # baseline V0: use yaw_rate_pred_rads vs yaw_rate_meas_rads
    sq = []
    nsum = 0
    for df in dfs:
        if 'yaw_rate_meas_rads' not in df.columns: continue
        # exclude very low-speed (signal-to-noise)
        m = df['v_mps'] > 0.5
        res = (df['yaw_rate_pred_rads'][m] - df['yaw_rate_meas_rads'][m]).values
        sq.append((res**2).sum())
        nsum += len(res)
    rmse = np.sqrt(sum(sq)/nsum) if nsum else float('nan')
    print(f'{p}: N segs={len(dfs)}, samples={nsum}, V0 yaw_rate RMSE = {rmse:.5f} rad/s')

# Look at residual vs v, vs delta
print('\n--- understeer fit check ---')
for p in PLATFORMS_WITH_TRUTH:
    dfs = load_platform(p, max_segs=50)
    L = L_MAP[p]
    Y_meas, V, D = [], [], []
    for df in dfs:
        if 'yaw_rate_meas_rads' not in df.columns: continue
        m = df['v_mps'] > 2.0
        Y_meas.append(df['yaw_rate_meas_rads'][m].values)
        V.append(df['v_mps'][m].values)
        D.append(df['delta_road_rad'][m].values)
    Y = np.concatenate(Y_meas)
    V = np.concatenate(V)
    D = np.concatenate(D)
    # model: psi_dot = v*delta / (L + K*v^2)
    # rearrange: v*delta/psi_dot - L = K * v^2  (only where psi_dot != 0)
    # Better: minimize over K with least-squares on yaw_rate
    from scipy.optimize import minimize_scalar
    def loss(K):
        pred = V * D / (L + K * V*V)
        return np.mean((pred - Y)**2)
    res = minimize_scalar(loss, bounds=(-0.1, 0.1), method='bounded')
    K = res.x
    pred = V * D / (L + K * V*V)
    rmse = np.sqrt(np.mean((pred - Y)**2))
    pred0 = V * np.tan(D) / L
    rmse0 = np.sqrt(np.mean((pred0 - Y)**2))
    print(f'{p}: L={L}, fitted K={K:.5f}, RMSE V0={rmse0:.5f}, RMSE_us={rmse:.5f}')
