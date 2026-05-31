"""Fit per-platform understeer parameters: yr = v*tan(delta)/L_eff / (1+(v/v_ch)^2)

Including a small bias term might help (steering offset).
Use bicycle-with-understeer:  yr = v * delta_eff / L / (1 + K*v^2)
where delta_eff = delta - delta_offset.
"""
import sys
sys.path.insert(0, 'skills/load-segments')
from load import load
import numpy as np
from scipy.optimize import minimize

NOM_L = {'FORD_F_150_LIGHTNING_MK1': 3.70, 'FORD_MUSTANG_MACH_E_MK1': 2.984}

# Split: use 80% of segments for training
np.random.seed(42)

results = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    dfs = load(platform=plat)
    idxs = list(range(len(dfs)))
    np.random.shuffle(idxs)
    n_train = int(0.8*len(dfs))
    train_idx = set(idxs[:n_train])

    all_v_tr=[]; all_d_tr=[]; all_y_tr=[]
    all_v_dv=[]; all_d_dv=[]; all_y_dv=[]
    for i, df in enumerate(dfs):
        v = df['v_mps'].values
        d = df['delta_road_rad'].values
        y = df['yaw_rate_meas_rads'].values
        m = v > 2.0
        if i in train_idx:
            all_v_tr.append(v[m]); all_d_tr.append(d[m]); all_y_tr.append(y[m])
        else:
            all_v_dv.append(v[m]); all_d_dv.append(d[m]); all_y_dv.append(y[m])
    v_tr=np.concatenate(all_v_tr); d_tr=np.concatenate(all_d_tr); y_tr=np.concatenate(all_y_tr)
    v_dv=np.concatenate(all_v_dv); d_dv=np.concatenate(all_d_dv); y_dv=np.concatenate(all_y_dv)

    L0 = NOM_L[plat]
    # Model: yr = v*(d - d0)/L_eff / (1 + K*v^2)
    # Params: L_eff, K, d0 (steering offset)
    def loss(p, v, d, y):
        L_eff, K, d0 = p
        if L_eff <= 0.5 or K < 0:
            return 1e9
        pred = v * (d - d0) / L_eff / (1.0 + K * v**2)
        return np.mean((pred - y)**2)

    # Initial guess: nominal L, small understeer
    x0 = [L0, 1.0/(40.0**2), 0.0]
    res = minimize(loss, x0, args=(v_tr, d_tr, y_tr), method='Nelder-Mead',
                   options={'xatol':1e-6,'fatol':1e-10,'maxiter':10000})
    L_eff, K, d0 = res.x
    v_ch = 1.0/np.sqrt(K) if K > 0 else float('inf')
    pred_tr = v_tr * (d_tr - d0) / L_eff / (1.0 + K * v_tr**2)
    pred_dv = v_dv * (d_dv - d0) / L_eff / (1.0 + K * v_dv**2)
    rms_tr = np.sqrt(np.mean((pred_tr - y_tr)**2))
    rms_dv = np.sqrt(np.mean((pred_dv - y_dv)**2))
    print(f'{plat}: L_eff={L_eff:.4f}  K={K:.6f}  v_ch={v_ch:.2f}  d0={d0:.6f}')
    print(f'  train RMSE: {rms_tr:.5f}  dev RMSE: {rms_dv:.5f}')
    results[plat] = {'L_eff': float(L_eff), 'K': float(K), 'd0': float(d0)}

import json
with open('coeffs.json', 'w') as f:
    json.dump(results, f, indent=2)
print('\nWrote coeffs.json')
print(results)
