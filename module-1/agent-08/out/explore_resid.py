"""Explore residual structure on training data."""
import pandas as pd
import numpy as np
import glob

L_BY = {
    'HYUNDAI_IONIQ_5': 3.0,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'TESLA_MODEL_3': 2.875,
}

def load_concat(plat, limit=None):
    files = glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/{plat}/*/*/*/sim.csv')
    if limit:
        files = files[:limit]
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df['_seg'] = f
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

for plat in ['HYUNDAI_IONIQ_5', 'FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1']:
    L = L_BY[plat]
    d = load_concat(plat, limit=50)
    # baseline reconstruction
    yr_pred = (d['v_mps'] / L) * np.tan(d['delta_road_rad'])
    yr_true = d['yaw_rate_meas_rads']
    # already provided
    yr_pred_stored = d['yaw_rate_pred_rads']
    print(f'\n=== {plat} ===')
    print(f'KS recompute matches stored? maxdiff={(yr_pred-yr_pred_stored).abs().max():.2e}')

    # understeer model: yr = v*delta / (L + K*v^2)
    # Solve for K per row: yr_true*(L + K*v^2) = v*delta
    # K = (v*delta/yr_true - L) / v^2
    # Use linear regression: 1/yr * v*delta = L + K*v^2
    # Better: regress yr_true on v*delta and v^3*delta
    mask = (np.abs(yr_true) > 0.01) & (d['v_mps'] > 1.0) & np.isfinite(yr_true)
    v = d.loc[mask, 'v_mps'].values
    delta = d.loc[mask, 'delta_road_rad'].values
    yr = yr_true[mask].values

    # Bicycle understeer: yr = v*delta / (L + K*v^2)
    # => v*delta/yr = L + K*v^2
    # => K = (v*delta/yr - L)/v^2  per sample
    # Or LS on: yr = a*v*delta + b*v^3*delta?  No, better: regress (v*delta)/(yr) ~ L + K*v^2
    # Or directly solve for K minimizing sum(yr_true - v*delta/(L+K*v^2))^2
    from scipy.optimize import minimize_scalar
    def cost(K):
        pred = v * delta / (L + K * v**2)
        return float(np.mean((yr - pred)**2))
    res = minimize_scalar(cost, bounds=(-0.01, 0.05), method='bounded')
    K_opt = res.x
    pred = v * delta / (L + K_opt * v**2)
    rmse_us = float(np.sqrt(np.mean((yr - pred)**2)))
    rmse_v0 = float(np.sqrt(np.mean((yr - v*delta/L)**2)))
    print(f'  K_understeer optimal = {K_opt:.6f} s^2/m')
    print(f'  RMSE V0 (subset) = {rmse_v0:.5f}')
    print(f'  RMSE understeer  = {rmse_us:.5f}')

    # Also: steering scale and offset
    # yr_true ≈ (v/L) * tan(s*delta + off) -> linearize
    # Or include a constant bias
    # Try linear regression: yr_true = a*v*tan(delta) + b*v + c
    from numpy.linalg import lstsq
    X = np.column_stack([v*np.tan(delta), v, np.ones_like(v)])
    coef,_,_,_ = lstsq(X, yr, rcond=None)
    pred2 = X @ coef
    rmse_lin = float(np.sqrt(np.mean((yr-pred2)**2)))
    print(f'  RMSE linear (v*tan+v+1) = {rmse_lin:.5f}  coef={coef}')

    # Try richer model: yr = a*v*tan(d) + b*v^3*tan(d) + c*v + d_off
    X3 = np.column_stack([v*np.tan(delta), (v**3)*np.tan(delta), v, np.ones_like(v)])
    coef3,_,_,_ = lstsq(X3, yr, rcond=None)
    pred3 = X3 @ coef3
    rmse_3 = float(np.sqrt(np.mean((yr-pred3)**2)))
    print(f'  RMSE rich (v*tan, v^3*tan, v, 1) = {rmse_3:.5f}  coef={coef3}')
