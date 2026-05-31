"""Score the V1 predictor against the full sim dataset.

Per platform:
- Loads sim-only segments (input-only contract — what predict() sees at grading).
- Runs predict() to get yaw_rate_pred_rads + (x,y).
- Loads matched sim segment for truth.
- Computes yaw RMSE and distance-resampled CTE RMSE.

Distance-resampled CTE: take truth trajectory (x_truth, y_truth), parameterise
by truth arclength s_truth. Take predicted trajectory (x_pred, y_pred) — note
the predict integrates yaw+v starting at (0,0,0). Truth also starts at (0,0)
with psi=0 (per generator), so they share the origin. Compute the prediction
trajectory at the same uniform-arclength samples and measure perpendicular
distance from truth path. Approximation here: use minimum point-to-point
distance from each truth sample to the predicted trajectory.
"""
import os, sys, glob, json, time
import numpy as np
import pandas as pd

ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-09'
sys.path.insert(0, os.path.join(ROOT, 'final-model'))
from predict import predict

SIM_ROOT = f'{ROOT}/data/sim/segments'
SO_ROOT  = f'{ROOT}/data/sim-only/segments'

def arclength(x, y):
    dx = np.diff(x); dy = np.diff(y)
    seg = np.hypot(dx, dy)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    return s

def resample_uniform_s(x, y, s, ds=1.0):
    if s[-1] < 2*ds:
        return None
    s_target = np.arange(0.0, s[-1], ds)
    xr = np.interp(s_target, s, x)
    yr = np.interp(s_target, s, y)
    return s_target, xr, yr

def cte_rmse(x_truth, y_truth, x_pred, y_pred, ds=1.0):
    """Distance-resampled cross-track error RMSE.
    Resample truth uniformly in its own arclength; for each truth sample, find
    nearest distance to predicted polyline (point-to-point, fine pred sampling).
    """
    s_t = arclength(x_truth, y_truth)
    if s_t[-1] < 2*ds:
        return np.nan, 0
    s_tr, xt, yt = resample_uniform_s(x_truth, y_truth, s_t, ds)
    # Densely sample predicted: also at ds/2 spacing in pred arclength
    s_p = arclength(x_pred, y_pred)
    if s_p[-1] < ds:
        return np.nan, 0
    s_pr = np.arange(0.0, s_p[-1], ds/2.0)
    xp = np.interp(s_pr, s_p, x_pred)
    yp = np.interp(s_pr, s_p, y_pred)
    # For each truth sample, nearest predicted point (uses a sliding window
    # since both are arclength-parameterised from origin)
    # Build a guess index = round(s_tr / (ds/2))
    n = len(xt)
    out = np.empty(n)
    pred_n = len(xp)
    half_window = 200  # +/- 100 m of slack
    for i in range(n):
        guess = int(round(s_tr[i] / (ds/2.0)))
        lo = max(0, guess - half_window)
        hi = min(pred_n, guess + half_window)
        dx = xp[lo:hi] - xt[i]
        dy = yp[lo:hi] - yt[i]
        d2 = dx*dx + dy*dy
        out[i] = np.sqrt(d2.min())
    return float(np.sqrt(np.mean(out**2))), n

INPUT_COLS = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2',
              'accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

def score_platform(platform, max_files=None, ds=1.0):
    so_files = sorted(glob.glob(f'{SO_ROOT}/{platform}/*/*/*/sim.csv'))
    if max_files:
        so_files = so_files[:max_files]
    yaw_sse = 0.0; yaw_n = 0
    cte_se = 0.0; cte_n = 0
    skipped = 0
    for sof in so_files:
        rel = os.path.relpath(sof, SO_ROOT)
        sf = os.path.join(SIM_ROOT, rel)
        if not os.path.exists(sf):
            skipped += 1; continue
        # Load sim-only as the predict() input. Tesla has different schema —
        # detect cols. For Tesla, sim-only has 'brake_pressed'. The grader
        # passes whatever sim-only has, so use that.
        so = pd.read_csv(sof)
        sim = pd.read_csv(sf)
        try:
            pred = predict(so, platform)
        except Exception as e:
            skipped += 1; continue
        # Yaw RMSE — Tesla has psi_dot_rads as the "truth-ish" channel (it's
        # actually V0 KS state in Tesla CSVs); for Ford/Hyundai it's yaw_rate_meas_rads.
        if 'yaw_rate_meas_rads' in sim.columns:
            truth_yaw = sim['yaw_rate_meas_rads'].values
        elif 'psi_dot_rads' in sim.columns:
            truth_yaw = sim['psi_dot_rads'].values  # Tesla: V0 itself, so RMSE will be 0 for V0-fallback
        else:
            truth_yaw = None
        if truth_yaw is not None:
            m = min(len(truth_yaw), len(pred))
            err = truth_yaw[:m] - pred['yaw_rate_pred_rads'].values[:m]
            yaw_sse += float(np.sum(err*err)); yaw_n += m
        # Trajectory truth
        if 'x_m' in sim.columns and 'y_m' in sim.columns:
            xt = sim['x_m'].values; yt = sim['y_m'].values
            xp = pred['x_m'].values; yp = pred['y_m'].values
            m = min(len(xt), len(xp))
            cte, k = cte_rmse(xt[:m], yt[:m], xp[:m], yp[:m], ds=ds)
            if not np.isnan(cte):
                cte_se += cte*cte * k
                cte_n += k
    yaw_rmse = np.sqrt(yaw_sse/yaw_n) if yaw_n else float('nan')
    cte_rmse_val = np.sqrt(cte_se/cte_n) if cte_n else float('nan')
    return {
        'platform': platform,
        'n_files': len(so_files),
        'skipped': skipped,
        'yaw_rmse_rads': yaw_rmse,
        'yaw_n_samples': yaw_n,
        'cte_rmse_m': cte_rmse_val,
        'cte_n_samples': cte_n,
    }

if __name__ == '__main__':
    results = {}
    # Limit files for time budget — but cover all platforms.
    max_files = {
        'TESLA_MODEL_3': 60,
        'FORD_MUSTANG_MACH_E_MK1': 60,
        'FORD_F_150_LIGHTNING_MK1': 60,
        'HYUNDAI_IONIQ_5': 100,
    }
    for p in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1','TESLA_MODEL_3']:
        t0 = time.time()
        r = score_platform(p, max_files=max_files[p])
        r['elapsed_s'] = time.time()-t0
        results[p] = r
        print(f"{p}: yaw_rmse={r['yaw_rmse_rads']:.5f} rad/s "
              f"cte_rmse={r['cte_rmse_m']:.3f} m  "
              f"(yaw_n={r['yaw_n_samples']}, cte_n={r['cte_n_samples']}, "
              f"files={r['n_files']}, skipped={r['skipped']}, "
              f"elapsed={r['elapsed_s']:.1f}s)", flush=True)
    # Also compute V0 baseline for comparison
    print('\n=== V0 baseline (sim-only yaw_rate_pred_rads vs truth) ===', flush=True)
    v0 = {}
    for p in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
        so_files = sorted(glob.glob(f'{SO_ROOT}/{p}/*/*/*/sim.csv'))[:max_files[p]]
        sse=0.0; n=0
        for sof in so_files:
            rel = os.path.relpath(sof, SO_ROOT)
            sf = os.path.join(SIM_ROOT, rel)
            if not os.path.exists(sf): continue
            sim = pd.read_csv(sf)
            so = pd.read_csv(sof)
            m = min(len(sim), len(so))
            err = sim['yaw_rate_meas_rads'].values[:m] - so['yaw_rate_pred_rads'].values[:m]
            sse += float(np.sum(err*err)); n += m
        v0[p] = np.sqrt(sse/n) if n else float('nan')
        print(f"  {p}: V0 yaw_rmse={v0[p]:.5f} rad/s (n={n})", flush=True)
    with open(f'{ROOT}/out/scores.json','w') as f:
        json.dump({'v1': results, 'v0_yaw_rmse': v0}, f, indent=2)
    print(f"\nWrote {ROOT}/out/scores.json", flush=True)
