"""Fit understeer coefficient K_us per platform on training set.

Model: yaw_rate = v * delta_road / (L + K_us * v^2)
"""
import sys, json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'make-train-dev-split'))
from split import split

L_BY_PLATFORM = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'TESLA_MODEL_3': 2.875,
}

train, dev = split(dev_fraction=0.25, seed=42)
print(f"train={len(train)}  dev={len(dev)}")

data = {}
for p in train:
    plat = p.parts[-5]
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(float)
    d = df['delta_road_rad'].to_numpy(float)
    yr = df['yaw_rate_meas_rads'].to_numpy(float)
    m = v > 2.0
    data.setdefault(plat, []).append((v[m], d[m], yr[m]))

coeffs = {}
for plat, chunks in data.items():
    L = L_BY_PLATFORM[plat]
    v = np.concatenate([c[0] for c in chunks])
    d = np.concatenate([c[1] for c in chunks])
    yr = np.concatenate([c[2] for c in chunks])

    def loss_kus(K):
        pred = v * d / (L + K * v * v)
        return np.mean((pred - yr) ** 2)

    res = minimize_scalar(loss_kus, bracket=(-0.05, 0.0, 0.1), method='brent')
    K_us = float(res.x)
    naive_rmse = float(np.sqrt(np.mean((v/L * np.tan(d) - yr)**2)))
    fit_rmse = float(np.sqrt(loss_kus(K_us)))

    # Try a 2-parameter model: yr = (v*delta + b) / (L + K_us * v^2)
    # Also try gain on delta: yr = g * v * delta / (L + K_us * v^2)
    from scipy.optimize import minimize
    def loss_gk(params):
        g, K = params
        pred = g * v * d / (L + K * v * v)
        return np.mean((pred - yr) ** 2)
    r2 = minimize(loss_gk, [1.0, K_us], method='Nelder-Mead')
    g_opt, K_opt = float(r2.x[0]), float(r2.x[1])
    rmse_gk = float(np.sqrt(loss_gk(r2.x)))

    # Affine offset: yr = g * v * (d - d0) / (L + K*v^2)
    def loss_gkb(params):
        g, K, d0 = params
        pred = g * v * (d - d0) / (L + K * v * v)
        return np.mean((pred - yr) ** 2)
    r3 = minimize(loss_gkb, [g_opt, K_opt, 0.0], method='Nelder-Mead')
    g3, K3, d3 = float(r3.x[0]), float(r3.x[1]), float(r3.x[2])
    rmse_gkb = float(np.sqrt(loss_gkb(r3.x)))

    coeffs[plat] = {
        'L': L,
        'K_us_only': K_us,
        'rmse_K_us_only': fit_rmse,
        'g': g_opt, 'K': K_opt,
        'rmse_gk': rmse_gk,
        'g3': g3, 'K3': K3, 'd0': d3,
        'rmse_gkb': rmse_gkb,
        'rmse_naive': naive_rmse,
    }
    print(f"{plat}: naive={naive_rmse:.5f} kus={fit_rmse:.5f} (K={K_us:.4f}) "
          f"gk={rmse_gk:.5f} (g={g_opt:.4f},K={K_opt:.4f}) "
          f"gkb={rmse_gkb:.5f} (g={g3:.4f},K={K3:.4f},d0={d3:.5f})")

with open(ROOT / 'coeffs.json', 'w') as fh:
    json.dump(coeffs, fh, indent=2)
print("wrote coeffs.json")
