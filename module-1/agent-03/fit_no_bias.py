"""Try fitting with b forced to 0 — a constant bias in yaw rate integrates to
quadratic position error and will hurt cross-track even if it slightly helps
yaw-rate RMSE."""
import os, glob, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import sys

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03"
sys.path.insert(0, f"{ROOT}/final-model")

SIM_ROOT = f"{ROOT}/data/sim/segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]
L_BY_PLAT = {"FORD_F_150_LIGHTNING_MK1": 3.70, "FORD_MUSTANG_MACH_E_MK1": 2.984}

def held(plat, seed=42, frac=0.7):
    files = sorted(glob.glob(f"{SIM_ROOT}/{plat}/*/*/*/sim.csv"))
    rng = np.random.RandomState(seed)
    perm = rng.permutation(len(files))
    n = int(len(files) * frac)
    return [files[i] for i in perm[:n]], [files[i] for i in perm[n:]]

results = {}
for plat in PLATFORMS:
    L = L_BY_PLAT[plat]
    tr, he = held(plat)
    df_tr = pd.concat([pd.read_csv(f) for f in tr], ignore_index=True)
    df_he = pd.concat([pd.read_csv(f) for f in he], ignore_index=True)

    def feats(df):
        return (df["v_mps"].values, df["delta_road_rad"].values,
                df["yaw_rate_meas_rads"].values, df["yaw_rate_pred_rads"].values)

    v_tr, d_tr, ym_tr, y0_tr = feats(df_tr)
    v_he, d_he, ym_he, y0_he = feats(df_he)

    # Model A0: y = a * y0 / (1 + K*v^2), no bias
    def loss(p, v, y0, ym):
        a, K = p
        yp = a * y0 / (1.0 + K * v * v)
        return np.mean((ym - yp) ** 2)

    r = minimize(loss, x0=[1.0, 0.001], args=(v_tr, y0_tr, ym_tr), method='Nelder-Mead',
                 options={'xatol': 1e-7, 'fatol': 1e-10, 'maxiter': 10000})
    a, K = r.x
    pred_he = a * y0_he / (1.0 + K * v_he * v_he)
    rmse_tr = float(np.sqrt(r.fun))
    rmse_he = float(np.sqrt(np.mean((ym_he - pred_he) ** 2)))
    print(f"{plat}: a={a:.5f} K={K:.6f}  train RMSE {rmse_tr:.6f}  held RMSE {rmse_he:.6f}")
    results[plat] = {"L": L, "a": float(a), "K": float(K), "b": 0.0}

print(json.dumps(results, indent=2))
with open(f"{ROOT}/fit_no_bias.json", "w") as fh:
    json.dump(results, fh, indent=2)
