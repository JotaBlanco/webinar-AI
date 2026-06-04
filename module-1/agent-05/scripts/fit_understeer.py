"""Fit per-platform corrections to baseline KS yaw rate.

Model variants:
  V0 (baseline):     yaw = (v/L) * tan(delta)         -> already in yaw_rate_pred_rads
  V1 (bias):         yaw = (v/L) * tan(delta - b)
  V2 (understeer):   yaw = (v/L) * tan(delta - b) / (1 + Ku * v**2)
  V3 (V2 + low-pass first-order lag on psi_dot)

Fit parameters per platform by minimizing pooled MSE on yaw_rate_meas_rads.
"""
import os, glob, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

BASE = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim/segments'
WHEELBASE = {
    'TESLA_MODEL_3': 2.875,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'HYUNDAI_IONIQ_5': 3.0,   # placeholder; we'll keep it
}

NEW_SCHEMA_COLS = {'yaw_rate_meas_rads', 'yaw_rate_pred_rads'}


def iter_files(platform):
    pattern = os.path.join(BASE, platform, '*', '*', '*', 'sim.csv')
    for p in glob.glob(pattern):
        with open(p) as fp:
            hdr = fp.readline().strip().split(',')
        if NEW_SCHEMA_COLS.issubset(set(hdr)):
            yield p


def load_platform(platform, max_files=None):
    """Load and concatenate (delta, v, yaw_meas) arrays."""
    deltas, vs, yaws = [], [], []
    count = 0
    for p in iter_files(platform):
        df = pd.read_csv(p, usecols=['delta_road_rad','v_mps','yaw_rate_meas_rads'])
        deltas.append(df['delta_road_rad'].values)
        vs.append(df['v_mps'].values)
        yaws.append(df['yaw_rate_meas_rads'].values)
        count += 1
        if max_files and count >= max_files:
            break
    return (np.concatenate(deltas),
            np.concatenate(vs),
            np.concatenate(yaws))


def fit_platform(platform):
    L = WHEELBASE[platform]
    print(f"\n=== {platform} (L={L} m) ===")
    delta, v, y_meas = load_platform(platform)
    # Baseline V0
    y0 = (v / L) * np.tan(delta)
    rmse0 = np.sqrt(np.mean((y0 - y_meas)**2))
    print(f"  V0 baseline RMSE = {rmse0:.5f}")

    # V1: bias
    def loss_v1(p):
        b = p[0]
        y = (v / L) * np.tan(delta - b)
        return np.mean((y - y_meas)**2)
    r1 = minimize(loss_v1, [0.0], method='Nelder-Mead')
    b1 = r1.x[0]
    y1 = (v / L) * np.tan(delta - b1)
    rmse1 = np.sqrt(np.mean((y1 - y_meas)**2))
    print(f"  V1 bias b={b1:.5f} rad => RMSE = {rmse1:.5f}")

    # V2: bias + understeer Ku  (gain * (1/(1+Ku v^2)))
    def loss_v2(p):
        b, Ku = p
        y = (v / L) * np.tan(delta - b) / (1 + Ku * v * v)
        return np.mean((y - y_meas)**2)
    r2 = minimize(loss_v2, [b1, 0.001], method='Nelder-Mead',
                  options={'xatol':1e-7,'fatol':1e-9,'maxiter':5000})
    b2, Ku2 = r2.x
    y2 = (v / L) * np.tan(delta - b2) / (1 + Ku2 * v * v)
    rmse2 = np.sqrt(np.mean((y2 - y_meas)**2))
    print(f"  V2 bias={b2:.5f}, Ku={Ku2:.6f} => RMSE = {rmse2:.5f}")

    # V2b: bias + Ku + steering scale (compliance/ratio mismatch)
    def loss_v2b(p):
        b, Ku, k = p
        y = (v / L) * np.tan(k * (delta - b)) / (1 + Ku * v * v)
        return np.mean((y - y_meas)**2)
    r2b = minimize(loss_v2b, [b2, Ku2, 1.0], method='Nelder-Mead',
                   options={'xatol':1e-7,'fatol':1e-9,'maxiter':10000})
    b2b, Ku2b, k2b = r2b.x
    y2b = (v / L) * np.tan(k2b * (delta - b2b)) / (1 + Ku2b * v * v)
    rmse2b = np.sqrt(np.mean((y2b - y_meas)**2))
    print(f"  V2b bias={b2b:.5f}, Ku={Ku2b:.6f}, k={k2b:.5f} => RMSE = {rmse2b:.5f}")

    return {
        'L': L,
        'V0_rmse': float(rmse0),
        'V1': {'b': float(b1), 'rmse': float(rmse1)},
        'V2': {'b': float(b2), 'Ku': float(Ku2), 'rmse': float(rmse2)},
        'V2b': {'b': float(b2b), 'Ku': float(Ku2b), 'k': float(k2b), 'rmse': float(rmse2b)},
    }


if __name__ == "__main__":
    out = {}
    for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1', 'HYUNDAI_IONIQ_5']:
        out[plat] = fit_platform(plat)
    with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/out/fit_results.json','w') as f:
        json.dump(out, f, indent=2)
    print("\nWritten out/fit_results.json")
