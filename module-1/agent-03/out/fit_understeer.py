"""Fit understeer coefficient K_us per platform via
   yaw = v * delta / (L + K * v^2)
We also recompute V0 (Tesla too) for fair comparison.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

# Wheelbases from parameters.py
L = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,   # workshop default; not in our parameters.py but close
}

# Try a few candidate L for HYUNDAI — known spec is 3.00 m
big = pd.read_parquet("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/out/all_samples.parquet")

results = {}
for plat, g in big.groupby("platform"):
    v = g["v_mps"].to_numpy()
    d = g["delta_road_rad"].to_numpy()
    y = g["yaw_truth"].to_numpy()
    # Use only meaningful samples: v>2 m/s
    mask = np.isfinite(v) & np.isfinite(d) & np.isfinite(y) & (v > 2.0)
    v_, d_, y_ = v[mask], d[mask], y[mask]
    Lp = L[plat]

    def loss(K):
        pred = v_ * d_ / (Lp + K * v_ * v_)
        return float(np.mean((pred - y_) ** 2))

    res = minimize_scalar(loss, bounds=(-0.05, 0.05), method="bounded",
                          options={"xatol": 1e-6})
    K = res.x
    rmse_us = np.sqrt(res.fun)
    # V0 (pure KS): yaw = (v/L)*tan(delta)
    yaw_v0 = (v_ / Lp) * np.tan(d_)
    rmse_v0 = float(np.sqrt(np.mean((yaw_v0 - y_) ** 2)))
    # also a delta-bias term + scale
    # Fit yaw = v*(a*delta + b) / (L + K*v^2)
    # Try linear refinement on delta: delta_eff = a*delta + b
    from scipy.optimize import minimize
    def loss_full(params):
        a, b, KK = params
        pred = v_ * (a * d_ + b) / (Lp + KK * v_ * v_)
        return float(np.mean((pred - y_) ** 2))
    r2 = minimize(loss_full, x0=[1.0, 0.0, K], method="Nelder-Mead",
                  options={"xatol": 1e-7, "fatol": 1e-10, "maxiter": 5000})
    a, b, K2 = r2.x
    rmse_full = float(np.sqrt(r2.fun))

    # Slip-corrected: also try with measured slip approx via lateral accel? Skip.
    results[plat] = dict(K=K, rmse_us=rmse_us, rmse_v0=rmse_v0,
                         a=a, b=b, K2=K2, rmse_full=rmse_full, n=int(mask.sum()))
    print(f"{plat}: V0 RMSE {rmse_v0:.4f}  US K={K:+.5f} -> {rmse_us:.4f}  "
          f"full a={a:.4f} b={b:+.5f} K2={K2:+.5f} -> {rmse_full:.4f}  n={mask.sum()}")

import json
with open("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/out/coeffs.json","w") as fh:
    json.dump(results, fh, indent=2)
print("Saved coeffs.json")
