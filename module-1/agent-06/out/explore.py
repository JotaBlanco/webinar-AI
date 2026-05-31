"""Explore residuals on a few segments to understand the V0 error structure."""
import os, glob, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/data/sim/segments"
PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]

# Tesla parameters (sample for fits)
PARAMS = {
    "TESLA_MODEL_3":            dict(L=2.875),
    "FORD_MUSTANG_MACH_E_MK1":  dict(L=2.984),
    "FORD_F_150_LIGHTNING_MK1": dict(L=3.70),
    "HYUNDAI_IONIQ_5":          dict(L=3.00),  # guess; refine if needed
}

for p in PLATFORMS:
    paths = sorted(glob.glob(f"{ROOT}/{p}/*/*/*/sim.csv"))[:80]
    dfs = []
    for path in paths:
        d = pd.read_csv(path)
        if "yaw_rate_meas_rads" not in d.columns:
            continue
        dfs.append(d[["v_mps","delta_road_rad","yaw_rate_meas_rads","yaw_rate_pred_rads"]])
    if not dfs:
        continue
    D = pd.concat(dfs, ignore_index=True)
    print(f"\n=== {p} (rows={len(D)}) ===")
    rmse_v0 = float(np.sqrt(np.mean((D.yaw_rate_pred_rads - D.yaw_rate_meas_rads)**2)))
    print(f"V0 yaw RMSE: {rmse_v0:.4f} rad/s")

    # Recompute KS-style ψ̇ = v/L * tan(delta); compare to pred to confirm.
    L = PARAMS[p]["L"]
    ks_pred = D.v_mps/L * np.tan(D.delta_road_rad)
    rmse_ks_recalc = float(np.sqrt(np.mean((ks_pred - D.yaw_rate_meas_rads)**2)))
    print(f"  recomputed KS yaw RMSE: {rmse_ks_recalc:.4f} rad/s")

    # Fit understeer model: ψ̇ = v·δ / (L + K_us·v²)
    # Linear in K_us: psi_dot = v*delta/(L + K_us v^2)
    # Equivalent: 1/psi_dot - L/(v*delta) = K_us*v / delta  (only valid where psi_dot,delta != 0)
    # Use nonlinear fit instead.
    from scipy.optimize import minimize_scalar
    def loss(k):
        pred = D.v_mps * D.delta_road_rad / (L + k * D.v_mps**2)
        return float(np.mean((pred - D.yaw_rate_meas_rads)**2))
    res = minimize_scalar(loss, bounds=(-1.0, 2.0), method="bounded")
    K_us = res.x
    pred_us = D.v_mps * D.delta_road_rad / (L + K_us * D.v_mps**2)
    rmse_us = float(np.sqrt(np.mean((pred_us - D.yaw_rate_meas_rads)**2)))
    print(f"  best K_us = {K_us:.4f},  RMSE = {rmse_us:.4f} rad/s")

    # Also affine fit: psi_pred = a * (v/L)*tan(delta) + b*delta
    X = np.column_stack([ks_pred, D.delta_road_rad])
    y = D.yaw_rate_meas_rads
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred_aff = X @ coef
    rmse_aff = float(np.sqrt(np.mean((pred_aff - y)**2)))
    print(f"  affine fit: a={coef[0]:.4f}, b={coef[1]:.4f}, RMSE={rmse_aff:.4f}")

    # Pure scale: psi_pred = a * (v/L)*tan(delta)
    a_scale = float(np.sum(ks_pred*y)/np.sum(ks_pred**2))
    rmse_sc = float(np.sqrt(np.mean((a_scale*ks_pred - y)**2)))
    print(f"  scale fit: a={a_scale:.4f}, RMSE={rmse_sc:.4f}")
