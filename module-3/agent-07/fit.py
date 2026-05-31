"""Fit per-platform parameters and evaluate variants on a held-out dev split.

Model variants:
  V0: yr = (v/L) * tan(delta)
  V1: yr = (g*(delta - d0)) * v / (L + K_us*v^2)        [no lag]
  V2: V1 + first-order lag tau
  V3: V2 + complementary fusion with a_lat/v
"""
from __future__ import annotations
import sys, glob, os, json, math, pickle
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

PLATS = ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1']
L_BY_PLAT = {'FORD_MUSTANG_MACH_E_MK1': 2.984, 'FORD_F_150_LIGHTNING_MK1': 3.70}

RNG = np.random.default_rng(42)

def list_paths(plat):
    return sorted(glob.glob(f'data/sim/segments/{plat}/*/*/*/sim.csv'))

def route_split(paths, frac_dev=0.25, seed=42):
    routes = {}
    for p in paths:
        parts = p.split('/')
        key = (parts[-4], parts[-3])  # device, route
        routes.setdefault(key, []).append(p)
    keys = sorted(routes.keys())
    rng = np.random.default_rng(seed)
    rng.shuffle(keys)
    n_dev = max(1, int(round(frac_dev * len(keys))))
    dev_keys = set(keys[:n_dev])
    train_paths = [p for k, ps in routes.items() for p in ps if k not in dev_keys]
    dev_paths = [p for k, ps in routes.items() for p in ps if k in dev_keys]
    return train_paths, dev_paths

def load_seg(p):
    df = pd.read_csv(p, usecols=['t_s','delta_road_rad','v_mps','a_lat_meas_mps2','yaw_rate_meas_rads'])
    return df

def first_order_lag(x, dt, tau):
    """Discrete first-order lowpass: y[k+1] = y[k] + (dt/tau)*(x[k]-y[k]), clamped tau>0."""
    if tau <= 1e-6:
        return x.copy()
    y = np.empty_like(x)
    y[0] = x[0]
    # variable dt
    a = dt / tau
    a = np.clip(a, 0.0, 1.0)
    for k in range(len(x) - 1):
        y[k+1] = y[k] + a[k]*(x[k] - y[k])
    return y

def predict_v1(delta, v, L, g, d0, K_us):
    return g * (delta - d0) * v / (L + K_us * v * v)

def predict_v2(t, delta, v, L, g, d0, K_us, tau):
    yr_ss = predict_v1(delta, v, L, g, d0, K_us)
    dt = np.diff(t)
    dt = np.concatenate([dt, dt[-1:]]) if len(dt) > 0 else np.array([0.02])
    return first_order_lag(yr_ss, dt, tau)

def predict_v3(t, delta, v, a_lat, L, g, d0, K_us, tau, alpha):
    yr_phys = predict_v2(t, delta, v, L, g, d0, K_us, tau)
    # a_lat / v gives yaw rate from measured lateral accel
    yr_alat = np.where(np.abs(v) > 0.5, a_lat / np.maximum(np.abs(v), 0.5) * np.sign(v), 0.0)
    # blend
    return (1.0 - alpha) * yr_phys + alpha * yr_alat

def loss_v2(params, segs):
    g, d0, K_us, tau = params
    if K_us < 0 or tau < 0 or g <= 0.5 or g >= 1.5:
        return 1e6
    total = 0.0
    n = 0
    for (t, delta, v, yr_truth, _, L) in segs:
        yp = predict_v2(t, delta, v, L, g, d0, K_us, tau)
        mask = v > 2.0
        r = yp[mask] - yr_truth[mask]
        total += float(np.sum(r*r))
        n += int(mask.sum())
    return total / max(n, 1)

def loss_v1(params, segs):
    g, d0, K_us = params
    if K_us < 0 or g <= 0.5 or g >= 1.5:
        return 1e6
    total = 0.0
    n = 0
    for (t, delta, v, yr_truth, _, L) in segs:
        yp = predict_v1(delta, v, L, g, d0, K_us)
        mask = v > 2.0
        r = yp[mask] - yr_truth[mask]
        total += float(np.sum(r*r))
        n += int(mask.sum())
    return total / max(n, 1)

def loss_v3(params, segs):
    g, d0, K_us, tau, alpha = params
    if K_us < 0 or tau < 0 or g <= 0.5 or g >= 1.5 or alpha < 0 or alpha > 1:
        return 1e6
    total = 0.0
    n = 0
    for (t, delta, v, yr_truth, a_lat, L) in segs:
        yp = predict_v3(t, delta, v, a_lat, L, g, d0, K_us, tau, alpha)
        mask = v > 2.0
        r = yp[mask] - yr_truth[mask]
        total += float(np.sum(r*r))
        n += int(mask.sum())
    return total / max(n, 1)

def preload(paths):
    out = []
    for p in paths:
        plat = p.split('/')[-5]
        L = L_BY_PLAT[plat]
        df = load_seg(p)
        t = df['t_s'].to_numpy(float)
        delta = df['delta_road_rad'].to_numpy(float)
        v = df['v_mps'].to_numpy(float)
        yr = df['yaw_rate_meas_rads'].to_numpy(float)
        al = df['a_lat_meas_mps2'].to_numpy(float)
        out.append((t, delta, v, yr, al, L))
    return out

if __name__ == '__main__':
    fits = {}
    for plat in PLATS:
        paths = list_paths(plat)
        train, dev = route_split(paths, frac_dev=0.25)
        print(f'\n=== {plat}: train {len(train)}, dev {len(dev)} ===')
        # Subsample to keep fit fast: take up to 30 random train segments
        if len(train) > 40:
            idx = RNG.choice(len(train), 40, replace=False)
            train_used = [train[i] for i in idx]
        else:
            train_used = train
        segs_train = preload(train_used)
        segs_dev = preload(dev)

        # Fit V1
        x0 = [1.0, 0.0, 0.002]
        res1 = minimize(loss_v1, x0, args=(segs_train,), method='Nelder-Mead',
                        options={'xatol':1e-5,'fatol':1e-9,'maxiter':400})
        g1, d01, ku1 = res1.x
        print(f'V1 train MSE {res1.fun:.3e}  g={g1:.4f} d0={d01:.5f} Kus={ku1:.5f}')

        # Fit V2 starting from V1
        x0 = [g1, d01, ku1, 0.07]
        res2 = minimize(loss_v2, x0, args=(segs_train,), method='Nelder-Mead',
                        options={'xatol':1e-5,'fatol':1e-9,'maxiter':600})
        g2, d02, ku2, tau2 = res2.x
        print(f'V2 train MSE {res2.fun:.3e}  g={g2:.4f} d0={d02:.5f} Kus={ku2:.5f} tau={tau2:.4f}')

        # Fit V3 starting from V2
        x0 = [g2, d02, ku2, tau2, 0.1]
        res3 = minimize(loss_v3, x0, args=(segs_train,), method='Nelder-Mead',
                        options={'xatol':1e-5,'fatol':1e-9,'maxiter':800})
        g3, d03, ku3, tau3, al3 = res3.x
        print(f'V3 train MSE {res3.fun:.3e}  g={g3:.4f} d0={d03:.5f} Kus={ku3:.5f} tau={tau3:.4f} alpha={al3:.4f}')

        # Eval on dev
        def eval_on(segs, predfn):
            yr_ss=0.0; n=0
            for (t,delta,v,yr,al,L) in segs:
                yp = predfn(t,delta,v,al,L)
                mask = v > 2.0
                r = yp[mask] - yr[mask]
                yr_ss += float(np.sum(r*r))
                n += int(mask.sum())
            return math.sqrt(yr_ss/max(n,1))

        v0fn = lambda t,d,v,al,L: (v/L)*np.tan(d)
        v1fn = lambda t,d,v,al,L: predict_v1(d,v,L,g1,d01,ku1)
        v2fn = lambda t,d,v,al,L: predict_v2(t,d,v,L,g2,d02,ku2,tau2)
        v3fn = lambda t,d,v,al,L: predict_v3(t,d,v,al,L,g3,d03,ku3,tau3,al3)

        print('  dev yaw RMSE V0', eval_on(segs_dev, v0fn))
        print('  dev yaw RMSE V1', eval_on(segs_dev, v1fn))
        print('  dev yaw RMSE V2', eval_on(segs_dev, v2fn))
        print('  dev yaw RMSE V3', eval_on(segs_dev, v3fn))
        print('  train yaw RMSE V0', eval_on(segs_train, v0fn))
        print('  train yaw RMSE V2', eval_on(segs_train, v2fn))

        fits[plat] = dict(g=g2, d0=d02, K_us=ku2, tau=tau2,
                          g_v3=g3, d0_v3=d03, K_us_v3=ku3, tau_v3=tau3, alpha_v3=al3,
                          g_v1=g1, d0_v1=d01, K_us_v1=ku1,
                          L=L_BY_PLAT[plat])

    with open('coeffs.json','w') as f:
        json.dump(fits, f, indent=2)
    print('\nSaved coeffs.json')
