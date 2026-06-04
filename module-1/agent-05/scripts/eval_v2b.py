"""End-to-end eval: yaw RMSE + distance-resampled cross-track RMSE.

For each sim.csv (new-schema), build predictions with V2b model and compare
against truth trajectory x_m, y_m (which are the KS-baseline integrated
positions in the file; close enough). Better: integrate truth psi from yaw_meas,
or use the file's x_m, y_m directly.

Note: x_m, y_m in sim.csv are integrated FROM the baseline KS model -- so
they are not the "true" trajectory. Without external GPS or a richer truth,
we can at best fairly compare to what the baseline outputs. Truth proxy for
trajectory: integrate yaw_rate_meas_rads with measured v_mps.
"""
import os, glob
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/final-model')
from predict import predict

BASE = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim/segments'

def integrate_xy(yaw, v, t):
    n = len(t)
    x = np.zeros(n); y = np.zeros(n); psi = np.zeros(n)
    for i in range(n-1):
        dt = t[i+1] - t[i]
        v_mid = 0.5*(v[i]+v[i+1])
        psi_next = psi[i] + yaw[i]*dt
        psi_mid = 0.5*(psi[i]+psi_next)
        x[i+1] = x[i] + v_mid*np.cos(psi_mid)*dt
        y[i+1] = y[i] + v_mid*np.sin(psi_mid)*dt
        psi[i+1] = psi_next
    return x, y, psi


def dist_resampled_cte(x_t, y_t, x_p, y_p):
    """Cross-track error in distance-resampled frame.
    Resample truth path by arc-length, find nearest pred point lateral distance.
    Simple approach: at each truth sample, project pred to the truth path tangent and
    compute perpendicular distance to truth point.
    Here we use simpler: per-index Euclidean distance to nearest point on pred path.
    For uniform-distance resampling we use arc-length increments of dl.
    """
    # compute arc length of truth
    dl = np.hypot(np.diff(x_t), np.diff(y_t))
    s = np.concatenate([[0.0], np.cumsum(dl)])
    if s[-1] < 1.0:
        return np.nan
    s_uniform = np.arange(0, s[-1], 1.0)  # 1m spacing
    xt_u = np.interp(s_uniform, s, x_t)
    yt_u = np.interp(s_uniform, s, y_t)
    # pred arc length
    dlp = np.hypot(np.diff(x_p), np.diff(y_p))
    sp = np.concatenate([[0.0], np.cumsum(dlp)])
    xp_u = np.interp(s_uniform, sp, x_p)
    yp_u = np.interp(s_uniform, sp, y_p)
    # per-sample lateral error (Euclidean distance after distance-resampling)
    err = np.hypot(xt_u - xp_u, yt_u - yp_u)
    return err


def eval_platform(platform, max_files=200):
    pattern = os.path.join(BASE, platform, '*', '*', '*', 'sim.csv')
    all_sse_yaw, all_n_yaw = 0.0, 0
    all_cte_sq, all_n_cte = 0.0, 0
    all_cte_sq_v0, all_n_cte_v0 = 0.0, 0
    sse_v0, n_v0 = 0.0, 0
    files = glob.glob(pattern)
    files = files[:max_files] if max_files else files
    for p in files:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        # V2b yaw RMSE
        pred = predict(df, platform)
        yaw_p = pred['yaw_rate_pred_rads'].values
        yaw_m = df['yaw_rate_meas_rads'].values
        all_sse_yaw += np.sum((yaw_p - yaw_m)**2); all_n_yaw += len(yaw_m)
        # V0 baseline
        yaw_0 = df['yaw_rate_pred_rads'].values
        sse_v0 += np.sum((yaw_0 - yaw_m)**2); n_v0 += len(yaw_m)
        # CTE: truth path = integrate yaw_meas with v_mps; pred path = V2b
        v = df['v_mps'].values; t = df['t_s'].values
        xt, yt, _ = integrate_xy(yaw_m, v, t)
        xp, yp, _ = integrate_xy(yaw_p, v, t)
        x0, y0, _ = integrate_xy(yaw_0, v, t)
        err = dist_resampled_cte(xt, yt, xp, yp)
        if not np.isscalar(err) and err.size:
            all_cte_sq += np.sum(err**2); all_n_cte += len(err)
        err0 = dist_resampled_cte(xt, yt, x0, y0)
        if not np.isscalar(err0) and err0.size:
            all_cte_sq_v0 += np.sum(err0**2); all_n_cte_v0 += len(err0)
    print(f"\n{platform} ({len(files)} files):")
    if all_n_yaw:
        print(f"  V0 yaw RMSE  = {np.sqrt(sse_v0/n_v0):.5f}")
        print(f"  V2b yaw RMSE = {np.sqrt(all_sse_yaw/all_n_yaw):.5f}")
    if all_n_cte:
        print(f"  V0 CTE RMSE  = {np.sqrt(all_cte_sq_v0/all_n_cte_v0):.3f} m")
        print(f"  V2b CTE RMSE = {np.sqrt(all_cte_sq/all_n_cte):.3f} m")
    return {
        'yaw_rmse_v0': np.sqrt(sse_v0/n_v0) if n_v0 else None,
        'yaw_rmse_v2b': np.sqrt(all_sse_yaw/all_n_yaw) if all_n_yaw else None,
        'cte_rmse_v0': np.sqrt(all_cte_sq_v0/all_n_cte_v0) if all_n_cte_v0 else None,
        'cte_rmse_v2b': np.sqrt(all_cte_sq/all_n_cte) if all_n_cte else None,
    }


if __name__ == "__main__":
    import json
    out = {}
    for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1', 'HYUNDAI_IONIQ_5']:
        out[plat] = eval_platform(plat, max_files=150)
    with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/out/eval_results.json','w') as f:
        json.dump(out, f, indent=2, default=str)
