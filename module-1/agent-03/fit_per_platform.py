"""Fit per-platform yaw-rate correction with held-out split.

Model: y_meas = a * (v/L) * tan(delta) / (1 + K * v^2) + b * delta + c

Where:
- a: overall gain (steering-ratio correction)
- K: understeer gradient
- b: linear delta sensitivity term (residual)
- c: bias

We also try a simpler model: gain * y_pred / (1 + K*v^2) + b
"""
import os, glob, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03"
SIM_ROOT = f"{ROOT}/data/sim/segments"

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]
L_BY_PLAT = {"FORD_F_150_LIGHTNING_MK1": 3.70, "FORD_MUSTANG_MACH_E_MK1": 2.984}

def load_segments_split(plat, seed=0, train_frac=0.7):
    files = sorted(glob.glob(f"{SIM_ROOT}/{plat}/*/*/*/sim.csv"))
    rng = np.random.RandomState(seed)
    perm = rng.permutation(len(files))
    n_train = int(len(files) * train_frac)
    train = [files[i] for i in perm[:n_train]]
    held = [files[i] for i in perm[n_train:]]
    return train, held

def concat(files):
    dfs = [pd.read_csv(f) for f in files]
    return pd.concat(dfs, ignore_index=True)

def rmse(a, b):
    return np.sqrt(np.mean((a - b) ** 2))

results = {}

for plat in PLATFORMS:
    print(f"\n=== {plat} ===")
    train_files, held_files = load_segments_split(plat, seed=42)
    print(f"train segs: {len(train_files)}  held segs: {len(held_files)}")

    df_tr = concat(train_files)
    df_he = concat(held_files)

    def features(df):
        v = df["v_mps"].values
        delta = df["delta_road_rad"].values
        y_meas = df["yaw_rate_meas_rads"].values
        y_pred_v0 = df["yaw_rate_pred_rads"].values
        return v, delta, y_meas, y_pred_v0

    v_tr, d_tr, ym_tr, y0_tr = features(df_tr)
    v_he, d_he, ym_he, y0_he = features(df_he)

    L = L_BY_PLAT[plat]

    # Baseline V0
    print(f"V0 RMSE train={rmse(ym_tr, y0_tr):.6f}  held={rmse(ym_he, y0_he):.6f}")

    # Model A: y = a * (v/L) * tan(d) / (1 + K*v^2) + b
    # Equivalently y = a * y0_alt + b  with y0_alt computed from raw (we have y0_tr already, equal to (v/L)*tan(d))
    # Note: V0 already has small clamp_v effects but mostly equivalent.

    def make_pred_A(params, v, d, y0):
        a, K, b = params
        return a * y0 / (1.0 + K * v * v) + b

    def loss_A(params, v, d, y0, ym):
        return np.mean((ym - make_pred_A(params, v, d, y0)) ** 2)

    r = minimize(loss_A, x0=[1.0, 0.001, 0.0], args=(v_tr, d_tr, y0_tr, ym_tr), method='Nelder-Mead',
                 options={'xatol': 1e-7, 'fatol': 1e-10, 'maxiter': 5000})
    A_params = r.x.tolist()
    pred_tr = make_pred_A(r.x, v_tr, d_tr, y0_tr)
    pred_he = make_pred_A(r.x, v_he, d_he, y0_he)
    print(f"Model A (a,K,b) = {A_params}")
    print(f"  RMSE train={rmse(ym_tr, pred_tr):.6f}  held={rmse(ym_he, pred_he):.6f}")

    # Model B: bicycle-model steady-state yaw rate
    # y = v*delta / (L + K*v^2)  where K is the understeer gradient parameter
    # Equivalent to A with a=1, K -> K/L. Try with extra gain
    def make_pred_B(params, v, d):
        a, K, b = params
        return a * v * d / (L + K * v * v) + b

    def loss_B(params, v, d, ym):
        return np.mean((ym - make_pred_B(params, v, d)) ** 2)

    r = minimize(loss_B, x0=[1.0, 0.1, 0.0], args=(v_tr, d_tr, ym_tr), method='Nelder-Mead',
                 options={'xatol': 1e-7, 'fatol': 1e-10, 'maxiter': 5000})
    B_params = r.x.tolist()
    pred_tr = make_pred_B(r.x, v_tr, d_tr)
    pred_he = make_pred_B(r.x, v_he, d_he)
    print(f"Model B (a,K,b) = {B_params}")
    print(f"  RMSE train={rmse(ym_tr, pred_tr):.6f}  held={rmse(ym_he, pred_he):.6f}")

    # Model C: also include a separate delta term (steering offset / calibration)
    # y = a * v * (delta - d0) / (L + K*v^2) + b
    def make_pred_C(params, v, d):
        a, K, d0, b = params
        return a * v * (d - d0) / (L + K * v * v) + b

    def loss_C(params, v, d, ym):
        return np.mean((ym - make_pred_C(params, v, d)) ** 2)

    r = minimize(loss_C, x0=[1.0, 0.1, 0.0, 0.0], args=(v_tr, d_tr, ym_tr), method='Nelder-Mead',
                 options={'xatol': 1e-7, 'fatol': 1e-10, 'maxiter': 10000})
    C_params = r.x.tolist()
    pred_tr = make_pred_C(r.x, v_tr, d_tr)
    pred_he = make_pred_C(r.x, v_he, d_he)
    print(f"Model C (a,K,d0,b) = {C_params}")
    print(f"  RMSE train={rmse(ym_tr, pred_tr):.6f}  held={rmse(ym_he, pred_he):.6f}")

    results[plat] = {
        "L": L,
        "model_A": A_params,
        "model_B": B_params,
        "model_C": C_params,
        "rmse_v0_held": float(rmse(ym_he, y0_he)),
        "rmse_A_held": float(rmse(ym_he, make_pred_A(np.array(A_params), v_he, d_he, y0_he))),
        "rmse_B_held": float(rmse(ym_he, make_pred_B(np.array(B_params), v_he, d_he))),
        "rmse_C_held": float(rmse(ym_he, make_pred_C(np.array(C_params), v_he, d_he))),
    }

with open(f"{ROOT}/fit_results.json", "w") as fh:
    json.dump(results, fh, indent=2)
print("\nSaved fit_results.json")
