"""Local scoring mimicking the grading contract:
- predict(sim_df, platform) is called with sim_df = pd.read_csv on sim-only segments
- compare yaw_rate_pred_rads vs truth yaw_rate_meas_rads from the matching sim segment
- cross-track error: distance-resampled trajectory vs truth (x_m, y_m).
"""
import sys, os, glob, json
import numpy as np
import pandas as pd

sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/final-model')
from predict import predict

SIMONLY = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim-only/segments'
SIM = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments'

INPUT_COLS = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2',
              'accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

def distance_resample_xte(pred_x, pred_y, true_x, true_y, ds=1.0):
    """Resample both trajectories at uniform arc-length steps on the truth path,
    then compute lateral distance from each truth point to the pred path
    (nearest segment). Returns RMSE in m."""
    # arc length of truth
    dx = np.diff(true_x); dy = np.diff(true_y)
    seg = np.sqrt(dx**2 + dy**2)
    s_true = np.concatenate(([0.0], np.cumsum(seg)))
    L = s_true[-1]
    if L < ds*2:
        return np.nan
    s_uniform = np.arange(0, L, ds)
    # Resample truth
    rx = np.interp(s_uniform, s_true, true_x)
    ry = np.interp(s_uniform, s_true, true_y)
    # For each resampled truth point, find min distance to pred polyline (point-to-segment)
    pts = np.column_stack([rx, ry])
    px = np.asarray(pred_x); py = np.asarray(pred_y)
    A = np.column_stack([px[:-1], py[:-1]])
    B = np.column_stack([px[1:], py[1:]])
    AB = B - A
    AB2 = (AB**2).sum(axis=1)
    AB2[AB2 == 0] = 1e-9
    # For each point compute distance to each segment (could be expensive but fine for short)
    dists = np.empty(len(pts))
    for i, p in enumerate(pts):
        AP = p - A
        t = (AP * AB).sum(axis=1) / AB2
        t = np.clip(t, 0, 1)
        proj = A + t[:,None] * AB
        d2 = ((proj - p)**2).sum(axis=1)
        dists[i] = np.sqrt(d2.min())
    return float(np.sqrt((dists**2).mean()))


per_platform = {}
for plat in os.listdir(SIMONLY):
    pdir = os.path.join(SIMONLY, plat)
    if not os.path.isdir(pdir): continue
    files = sorted(glob.glob(f'{pdir}/*/*/*/sim.csv'))
    yaw_sse = 0.0
    yaw_n = 0
    base_yaw_sse = 0.0
    xte_rmses = []
    base_xte_rmses = []
    for f in files:
        sim_only = pd.read_csv(f)
        # match in sim/
        rel = os.path.relpath(f, SIMONLY)
        sim_truth_path = os.path.join(SIM, rel)
        if not os.path.exists(sim_truth_path):
            continue
        sim_truth = pd.read_csv(sim_truth_path)
        if 'yaw_rate_meas_rads' not in sim_truth.columns:
            continue
        # Verify input columns present
        missing = [c for c in INPUT_COLS if c not in sim_only.columns]
        if missing:
            print(f"missing in {f}: {missing}")
            continue
        # predict only sees input columns
        pred_df = predict(sim_only[INPUT_COLS].copy(), plat)
        # truth yaw
        truth = sim_truth['yaw_rate_meas_rads'].values
        py = pred_df['yaw_rate_pred_rads'].values
        bp = sim_only['yaw_rate_pred_rads'].values  # baseline KS
        # align lengths
        n = min(len(truth), len(py))
        truth = truth[:n]; py = py[:n]; bp = bp[:n]
        yaw_sse += ((truth - py)**2).sum()
        base_yaw_sse += ((truth - bp)**2).sum()
        yaw_n += n
        # cross-track
        tx = sim_truth['x_m'].values[:n]
        ty = sim_truth['y_m'].values[:n]
        px = pred_df['x_m'].values[:n]
        pyy = pred_df['y_m'].values[:n]
        try:
            xte = distance_resample_xte(px, pyy, tx, ty, ds=1.0)
            if not np.isnan(xte):
                xte_rmses.append(xte)
        except Exception as e:
            pass
        # baseline xte: integrate baseline yaw rate
        v = sim_only['v_mps'].values[:n]
        t = sim_only['t_s'].values[:n]
        psi_b = np.zeros(n);
        if n>1:
            dt = np.diff(t)
            psi_b[1:] = np.cumsum(0.5*(bp[:-1]+bp[1:])*dt)
            vx = v*np.cos(psi_b); vy = v*np.sin(psi_b)
            bx = np.zeros(n); by = np.zeros(n)
            bx[1:] = np.cumsum(0.5*(vx[:-1]+vx[1:])*dt)
            by[1:] = np.cumsum(0.5*(vy[:-1]+vy[1:])*dt)
            try:
                xte_b = distance_resample_xte(bx, by, tx, ty, ds=1.0)
                if not np.isnan(xte_b):
                    base_xte_rmses.append(xte_b)
            except: pass

    if yaw_n>0:
        yaw_rmse = float(np.sqrt(yaw_sse/yaw_n))
        base_rmse = float(np.sqrt(base_yaw_sse/yaw_n))
        xte_rmse = float(np.mean(xte_rmses)) if xte_rmses else None
        base_xte = float(np.mean(base_xte_rmses)) if base_xte_rmses else None
        per_platform[plat] = {
            'n_samples': int(yaw_n),
            'n_segments_scored': len(xte_rmses),
            'yaw_rmse_model': yaw_rmse,
            'yaw_rmse_baseline': base_rmse,
            'xte_rmse_model_m': xte_rmse,
            'xte_rmse_baseline_m': base_xte,
        }
        print(f"\n{plat}:")
        print(f"  N samples scored: {yaw_n}")
        print(f"  yaw RMSE  baseline -> model: {base_rmse:.5f} -> {yaw_rmse:.5f} ({100*(1-yaw_rmse/base_rmse):.1f}% better)")
        if xte_rmse is not None:
            print(f"  XTE RMSE (m) baseline -> model: {base_xte:.3f} -> {xte_rmse:.3f}")

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/out/score.json','w') as fh:
    json.dump(per_platform, fh, indent=2)
print("\nWrote out/score.json")
