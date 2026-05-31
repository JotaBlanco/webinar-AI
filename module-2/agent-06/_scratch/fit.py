"""Fit understeer coefficient + steering bias + scale per platform."""
import pandas as pd, numpy as np
from pathlib import Path
import sys

L_BY = {'FORD_F_150_LIGHTNING_MK1': 3.70, 'FORD_MUSTANG_MACH_E_MK1': 2.984}
ROOT = Path(__file__).resolve().parents[1]

def load_all(plat, paths_list=None):
    if paths_list is None:
        paths_list = sorted((ROOT / 'data/sim/segments').glob(f'{plat}/**/sim.csv'))
    rows = []
    for p in paths_list:
        df = pd.read_csv(p)
        m = df['v_mps'] > 2.0
        rows.append(df[m][['delta_road_rad','v_mps','yaw_rate_meas_rads']])
    return pd.concat(rows, ignore_index=True)

# train/dev split via skill
sys.path.insert(0, str(ROOT / 'skills/make-train-dev-split'))
from split import split as make_split

train_paths, dev_paths = make_split(dev_fraction=0.25, seed=42)
print(f'train={len(train_paths)} dev={len(dev_paths)}')

def fit_plat(plat, L, paths):
    plat_paths = [p for p in paths if plat in str(p)]
    d = load_all(plat, plat_paths)
    delta = d['delta_road_rad'].values
    v = d['v_mps'].values
    yrm = d['yaw_rate_meas_rads'].values
    print(f'=== {plat} n={len(d)} ===')
    yr_ks = (v/L)*np.tan(delta)
    print(f'KS RMSE on train = {np.sqrt(np.mean((yr_ks-yrm)**2)):.5f}')
    best=(0,0,1,1e9)
    for K in np.linspace(0, 0.005, 51):
        for d0 in np.linspace(-0.015, 0.015, 31):
            term = (v/L)*np.tan(delta - d0)/(1+K*v**2)
            sc = np.dot(term, yrm)/np.dot(term, term)
            mse = np.mean((sc*term - yrm)**2)
            if mse < best[3]:
                best = (K, d0, sc, mse)
    K, d0, sc, _ = best
    # refine
    best2=best
    for Kx in np.linspace(max(0,K-0.0003), K+0.0003, 31):
        for d0x in np.linspace(d0-0.003, d0+0.003, 31):
            term = (v/L)*np.tan(delta - d0x)/(1+Kx*v**2)
            scx = np.dot(term, yrm)/np.dot(term, term)
            mse = np.mean((scx*term - yrm)**2)
            if mse < best2[3]:
                best2 = (Kx, d0x, scx, mse)
    K,d0,sc,mse = best2
    print(f'Fit: K={K:.6e}, d0={d0:.6f}, scale={sc:.5f}, train RMSE={np.sqrt(mse):.5f}')
    return K, d0, sc

coefs = {}
for plat, L in L_BY.items():
    K, d0, sc = fit_plat(plat, L, train_paths)
    coefs[plat] = {'K': float(K), 'delta0': float(d0), 'scale': float(sc), 'L': L}

# Evaluate on dev
print('\n--- DEV evaluation ---')
for plat, L in L_BY.items():
    plat_dev = [p for p in dev_paths if plat in str(p)]
    d = load_all(plat, plat_dev)
    delta = d['delta_road_rad'].values
    v = d['v_mps'].values
    yrm = d['yaw_rate_meas_rads'].values
    yr_ks = (v/L)*np.tan(delta)
    rmse_v0 = np.sqrt(np.mean((yr_ks-yrm)**2))
    c = coefs[plat]
    yr_fit = c['scale']*(v/L)*np.tan(delta - c['delta0'])/(1+c['K']*v**2)
    rmse_fit = np.sqrt(np.mean((yr_fit-yrm)**2))
    print(f'{plat}: V0 RMSE={rmse_v0:.5f}  fit RMSE={rmse_fit:.5f}')

import json
with open(ROOT / '_scratch/coefs.json', 'w') as f:
    json.dump(coefs, f, indent=2)
print('coefs saved')
