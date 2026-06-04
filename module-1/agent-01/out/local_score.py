"""Local score: simulate canonical-grader contract.
   - Read sim-only/segments/<platform>/.../sim.csv as the input.
   - Read matching sim/segments/.../sim.csv only to extract truth columns
     (yaw_rate_meas_rads, x_m, y_m) for scoring.
   - Score yaw-rate RMSE and distance-resampled cross-track RMSE.
"""
import glob, json, sys, os
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/final-model')
from predict import predict

SIM_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim/segments'
SIMONLY_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim-only/segments'

PLATFORMS = ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1', 'HYUNDAI_IONIQ_5']

def distance_resampled_cte_rmse(x_pred, y_pred, x_truth, y_truth, ds=1.0):
    """Resample both polylines by arc length, compare nearest-point distance.
    Simple variant: along truth, take points every ds m; for each, find closest
    point on pred polyline (in straight Euclidean) — that distance is CTE."""
    # arc length on truth
    dx = np.diff(x_truth); dy = np.diff(y_truth)
    s_truth = np.concatenate(([0], np.cumsum(np.hypot(dx, dy))))
    if s_truth[-1] < 2*ds:
        return np.nan
    s_samples = np.arange(0, s_truth[-1], ds)
    xt = np.interp(s_samples, s_truth, x_truth)
    yt = np.interp(s_samples, s_truth, y_truth)
    # densify pred to fine resolution then nearest neighbour
    dxp = np.diff(x_pred); dyp = np.diff(y_pred)
    s_pred = np.concatenate(([0], np.cumsum(np.hypot(dxp, dyp))))
    if s_pred[-1] < ds:
        return np.nan
    s_fine = np.arange(0, s_pred[-1], 0.25)
    xpf = np.interp(s_fine, s_pred, x_pred)
    ypf = np.interp(s_fine, s_pred, y_pred)
    # nearest-neighbour CTE per truth sample
    cte = np.empty(len(xt))
    # vectorise in chunks
    chunk = 200
    for i in range(0, len(xt), chunk):
        xc = xt[i:i+chunk][:, None]; yc = yt[i:i+chunk][:, None]
        d = np.hypot(xpf[None,:] - xc, ypf[None,:] - yc)
        cte[i:i+chunk] = d.min(axis=1)
    return np.sqrt(np.mean(cte**2))

INPUT_COLS = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2','accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

for p in PLATFORMS:
    so_files = sorted(glob.glob(f'{SIMONLY_ROOT}/{p}/*/*/*/sim.csv'))
    # subsample for speed
    sample_files = so_files[::3]
    se_yr = 0.0; n_yr = 0
    cte_rmses = []
    yr_v0_se = 0.0
    failed = 0
    for so_path in sample_files:
        rel = os.path.relpath(so_path, SIMONLY_ROOT)
        truth_path = os.path.join(SIM_ROOT, rel)
        if not os.path.exists(truth_path): continue
        sim_df = pd.read_csv(so_path)
        # Enforce contract: subset to only the 8 input columns
        sim_df_in = sim_df[INPUT_COLS].copy()
        try:
            pred = predict(sim_df_in, p)
        except Exception as e:
            failed += 1; continue
        truth = pd.read_csv(truth_path)
        if 'yaw_rate_meas_rads' not in truth.columns:
            continue
        m = sim_df_in['v_mps'].values > 1.0
        r = (pred['yaw_rate_pred_rads'].values - truth['yaw_rate_meas_rads'].values)[m]
        se_yr += (r*r).sum(); n_yr += len(r)
        # V0 baseline
        r0 = (sim_df_in['yaw_rate_pred_rads'].values - truth['yaw_rate_meas_rads'].values)[m]
        yr_v0_se += (r0*r0).sum()
        # CTE
        if 'x_m' in truth.columns and 'y_m' in truth.columns:
            try:
                rmse_cte = distance_resampled_cte_rmse(
                    pred['x_m'].values, pred['y_m'].values,
                    truth['x_m'].values, truth['y_m'].values, ds=1.0)
                if np.isfinite(rmse_cte):
                    cte_rmses.append(rmse_cte)
            except Exception:
                pass
    rmse_yr = np.sqrt(se_yr/n_yr) if n_yr else float('nan')
    rmse_v0 = np.sqrt(yr_v0_se/n_yr) if n_yr else float('nan')
    cte_mean = float(np.sqrt(np.mean(np.array(cte_rmses)**2))) if cte_rmses else float('nan')
    print(f'{p}: segs={len(sample_files)}, failed={failed}')
    print(f'  V1 yaw_rate RMSE = {rmse_yr:.5f} rad/s   (V0 = {rmse_v0:.5f})')
    print(f'  V1 cross-track RMSE (per-seg quadratic mean) = {cte_mean:.3f} m  (n_segs={len(cte_rmses)})')
