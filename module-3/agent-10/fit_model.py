"""Fit a per-platform lateral model.

Model: yr_ss = v * g * (delta - delta0) / (L_eff + K_us * v^2)
        yr   = first_order_lag(yr_ss, tau)
"""
import sys, math, json, pickle
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import least_squares

sys.path.insert(0, 'skills/make-train-dev-split')
from split import split

train, dev = split(dev_fraction=0.25, seed=42)

def load_segment_arrays(p):
    df = pd.read_csv(p)
    cols = ['t_s','v_mps','delta_road_rad','yaw_rate_meas_rads']
    df = df[cols].astype(float)
    df = df.dropna()
    return df

# Group by platform
by_plat = {}
for p in train:
    plat = p.parts[-5]
    by_plat.setdefault(plat, []).append(p)

print('Loading train data...')
data = {}
for plat, paths in by_plat.items():
    seg_list = [load_segment_arrays(pp) for pp in paths]
    data[plat] = seg_list
    n_rows = sum(len(d) for d in seg_list)
    print(f'  {plat}: {len(seg_list)} segments, {n_rows} rows')


def gather_rows(seg_list, v_min=3.0):
    vs = []; ds = []; yrs = []
    for df in seg_list:
        m = df['v_mps'] > v_min
        vs.append(df.loc[m, 'v_mps'].to_numpy())
        ds.append(df.loc[m, 'delta_road_rad'].to_numpy())
        yrs.append(df.loc[m, 'yaw_rate_meas_rads'].to_numpy())
    return np.concatenate(vs), np.concatenate(ds), np.concatenate(yrs)

def fit_static(seg_list, L_prior, plat):
    v, d, yr = gather_rows(seg_list, v_min=3.0)
    print(f'    {plat}: fitting on {len(v)} rows')
    def resid(theta):
        g, L_eff, K_us, d0 = theta
        pred = v * g * (d - d0) / (L_eff + K_us * v*v)
        return pred - yr
    x0 = [1.0, L_prior, 0.002, 0.0]
    res = least_squares(resid, x0, bounds=([0.3, 1.0, -0.01, -0.05], [2.0, 6.0, 0.03, 0.05]))
    print(f'    {plat} cost={res.cost:.4f}  g={res.x[0]:.5f} L_eff={res.x[1]:.5f} K_us={res.x[2]:.6f} d0={res.x[3]:.6f}')
    return res.x

L_priors = {'FORD_MUSTANG_MACH_E_MK1': 2.984, 'FORD_F_150_LIGHTNING_MK1': 3.70}

params = {}
for plat, segs in data.items():
    print(f'Fitting static for {plat}...')
    g, L_eff, K_us, d0 = fit_static(segs, L_priors[plat], plat)
    params[plat] = dict(g=float(g), L_eff=float(L_eff), K_us=float(K_us), delta0=float(d0))

def lag_apply(yr_ss, t, tau):
    if tau <= 0:
        return yr_ss
    out = np.empty_like(yr_ss)
    out[0] = yr_ss[0]
    for k in range(len(yr_ss)-1):
        dt = t[k+1] - t[k]
        alpha = dt / (tau + dt)
        out[k+1] = out[k] + alpha * (yr_ss[k+1] - out[k])
    return out

def fit_tau(seg_list, par, plat, taus=np.linspace(0.0, 0.15, 16)):
    best_tau, best_ss, best_n = 0.0, math.inf, 1
    for tau in taus:
        ss = 0.0; n = 0
        for df in seg_list:
            v = df['v_mps'].to_numpy()
            d = df['delta_road_rad'].to_numpy()
            yr = df['yaw_rate_meas_rads'].to_numpy()
            t = df['t_s'].to_numpy()
            yr_ss = v * par['g'] * (d - par['delta0']) / (par['L_eff'] + par['K_us'] * v*v)
            yr_p = lag_apply(yr_ss, t, tau)
            m = v > 2.0
            ss += float(np.sum((yr_p[m] - yr[m])**2))
            n += int(m.sum())
        if ss < best_ss:
            best_ss = ss; best_tau = tau; best_n = n
    print(f'  {plat} best tau = {best_tau:.3f}  rmse on train = {math.sqrt(best_ss/best_n):.6f}')
    return float(best_tau)

for plat, segs in data.items():
    print(f'Fitting tau for {plat}...')
    params[plat]['tau'] = fit_tau(segs, params[plat], plat)

print('\nFITTED PARAMS:')
print(json.dumps(params, indent=2))

with open('/tmp/params.json', 'w') as f:
    json.dump(params, f, indent=2)
print('saved /tmp/params.json')
