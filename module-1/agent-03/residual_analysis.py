"""Look at residual structure on a sample of Ford segments."""
import os, glob
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03"
SIM_ROOT = f"{ROOT}/data/sim/segments"

for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]:
    files = sorted(glob.glob(f"{SIM_ROOT}/{plat}/*/*/*/sim.csv"))
    dfs = [pd.read_csv(f) for f in files[:30]]
    df = pd.concat(dfs, ignore_index=True)
    y_meas = df["yaw_rate_meas_rads"].values
    y_pred = df["yaw_rate_pred_rads"].values
    v = df["v_mps"].values
    delta = df["delta_road_rad"].values
    a_y = y_meas * v  # measured lateral accel proxy
    res = y_meas - y_pred

    # Simple correlation hints
    print(f"\n--- {plat} ---")
    print(f"y_meas std: {y_meas.std():.4f}  y_pred std: {y_pred.std():.4f}  res std: {res.std():.4f}")
    # Slope of y_meas vs y_pred (gain we'd want)
    A = np.vstack([y_pred, np.ones_like(y_pred)]).T
    gain, bias = np.linalg.lstsq(A, y_meas, rcond=None)[0]
    print(f"Linear fit y_meas = {gain:.4f} * y_pred + {bias:.6f}")
    # Predict with gain
    y2 = gain * y_pred + bias
    rmse_gain = np.sqrt(np.mean((y_meas - y2) ** 2))
    rmse0 = np.sqrt(np.mean(res ** 2))
    print(f"RMSE V0: {rmse0:.6f}   Linear-corrected RMSE: {rmse_gain:.6f}")

    # Try understeer: y_pred / (1 + K * v^2)
    # Optimise K via grid + linear bias
    best_rmse, best_K = 1e9, None
    for K in np.linspace(0.0, 0.02, 41):
        denom = 1 + K * v * v
        y_us = y_pred / denom
        rmse = np.sqrt(np.mean((y_meas - y_us) ** 2))
        if rmse < best_rmse:
            best_rmse, best_K = rmse, K
    print(f"Understeer K={best_K:.5f}  RMSE: {best_rmse:.6f}")

    # Joint fit: y_meas = a * y_pred / (1 + K*v^2) + b
    # iterate
    from scipy.optimize import minimize
    def loss(params):
        a, K, b = params
        denom = 1 + K * v * v
        yp = a * y_pred / denom + b
        return np.mean((y_meas - yp) ** 2)
    r = minimize(loss, x0=[1.0, 0.0, 0.0], method='Nelder-Mead')
    a_, K_, b_ = r.x
    rmse_j = np.sqrt(r.fun)
    print(f"Joint a={a_:.4f} K={K_:.5f} b={b_:.6f}  RMSE: {rmse_j:.6f}")
