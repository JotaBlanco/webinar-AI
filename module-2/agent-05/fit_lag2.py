"""Try joint (tau, K_us, g, delta0) refit per platform, plus pure-delay search."""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'make-train-dev-split'))
from split import split

L_BY_PLATFORM = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
}

train, dev = split(dev_fraction=0.25, seed=42)

def gather(paths):
    out = {}
    for p in paths:
        plat = p.parts[-5]
        df = pd.read_csv(p)
        if len(df) < 5: continue
        v = df['v_mps'].to_numpy(float)
        d = df['delta_road_rad'].to_numpy(float)
        yr_t = df['yaw_rate_meas_rads'].to_numpy(float)
        t = df['t_s'].to_numpy(float)
        dt = float(np.median(np.diff(t)))
        out.setdefault(plat, []).append((v, d, yr_t, dt))
    return out

train_data = gather(train)

def model(v, d, dt, g, K, d0, tau):
    L = None  # set per platform outside
    raise NotImplementedError

def joint_fit(chunks, L, v_thresh=2.0):
    def total_loss(params):
        g, K, d0, tau = params
        sq = 0.0; n = 0
        for v, d, yr_t, dt in chunks:
            denom = L + K * v * v
            yr_pred = g * v * (d - d0) / denom
            if tau > 0:
                a = dt / (tau + dt)
                yr_pred = lfilter([a], [1, -(1-a)], yr_pred)
            m = v > v_thresh
            sq += float(np.sum((yr_pred[m] - yr_t[m])**2))
            n += int(m.sum())
        return sq / max(n, 1)
    x0 = [1.0, 0.003, 0.0, 0.05]
    r = minimize(total_loss, x0, method='Nelder-Mead',
                 options={'xatol':1e-5, 'fatol':1e-9, 'maxiter':2000})
    return r.x, float(np.sqrt(r.fun))

out_coeffs = {}
for plat, chunks in train_data.items():
    L = L_BY_PLATFORM[plat]
    params, rmse = joint_fit(chunks, L)
    g, K, d0, tau = [float(x) for x in params]
    print(f"{plat}: g={g:.4f} K={K:.4f} d0={d0:.5f} tau={tau:.3f}s  train_rmse={rmse:.5f}")
    out_coeffs[plat] = {'L': L, 'g': g, 'K_us': K, 'delta0': d0, 'tau': tau}

# Also include Tesla as default
out_coeffs['TESLA_MODEL_3'] = {'L': 2.875, 'g': 1.0, 'K_us': 0.003, 'delta0': 0.0, 'tau': 0.05}

with open(ROOT / 'coeffs_v2.json', 'w') as fh:
    json.dump(out_coeffs, fh, indent=2)
print('wrote coeffs_v2.json')
