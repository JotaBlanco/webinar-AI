"""Search for an optimal first-order low-pass time-constant tau (s) per platform,
applied to the V1 yaw-rate prediction. Tau represents the lumped steering+tire
lag the kinematic model ignores. We also search a pure time delay (samples).
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import lfilter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'make-train-dev-split'))
sys.path.insert(0, str(ROOT / 'final-model'))
from split import split
import predict as predict_mod

train, dev = split(dev_fraction=0.25, seed=42)

# Build per-platform pooled (yr_pred_v1, yr_truth, dt)
def gather(paths):
    out = {}
    for p in paths:
        plat = p.parts[-5]
        df = pd.read_csv(p)
        if len(df) < 5: continue
        pred = predict_mod.predict(df, plat)
        v = df['v_mps'].to_numpy(float)
        yr_t = df['yaw_rate_meas_rads'].to_numpy(float)
        yr_p = pred['yaw_rate_pred_rads'].to_numpy(float)
        t = df['t_s'].to_numpy(float)
        dt = float(np.median(np.diff(t)))
        out.setdefault(plat, []).append((yr_p, yr_t, v, dt))
    return out

train_data = gather(train)

def apply_lpf(yr, tau, dt):
    if tau <= 0: return yr.copy()
    a = dt / (tau + dt)
    # y[n] = a*x[n] + (1-a)*y[n-1]
    return lfilter([a], [1, -(1-a)], yr)

def loss_tau(tau, chunks, v_thresh=2.0):
    sq = 0.0
    n = 0
    for yr_p, yr_t, v, dt in chunks:
        yp = apply_lpf(yr_p, tau, dt)
        m = v > v_thresh
        sq += float(np.sum((yp[m] - yr_t[m])**2))
        n += int(m.sum())
    return sq / max(n, 1)

results = {}
for plat, chunks in train_data.items():
    best = (None, 1e9)
    for tau in np.linspace(0.0, 0.5, 26):
        l = loss_tau(tau, chunks)
        if l < best[1]:
            best = (tau, l)
    tau_star = best[0]
    rmse = float(np.sqrt(best[1]))
    rmse_0 = float(np.sqrt(loss_tau(0.0, chunks)))
    print(f"{plat}: best_tau={tau_star:.3f}s  rmse@tau={rmse:.5f}  rmse@0={rmse_0:.5f}")
    results[plat] = {'tau': float(tau_star), 'rmse_train': rmse, 'rmse_train_no_lag': rmse_0}

with open(ROOT / 'lag_fit.json', 'w') as fh:
    json.dump(results, fh, indent=2)
