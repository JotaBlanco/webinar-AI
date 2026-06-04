"""Local scoring: yaw-rate RMSE and distance-resampled cross-track RMSE."""
import sys, os, glob, json
import numpy as np
import pandas as pd

sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/final-model')
from predict import predict  # type: ignore

PLATFORMS_TRUTH = ['HYUNDAI_IONIQ_5', 'FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1']

DROP_COLS = {'yaw_rate_meas_rads','a_lat_meas_mps2','steer_rate_dps','x_m','y_m','psi_rad',
             'v_state_mps','delta_state_rad','yaw_rate_pred_rads','a_y_pred_mps2',
             'yaw_rate_resid_rads','a_y_resid_mps2','psi_dot_rads','a_y_mps2',
             'di_torque_actual_nm','wheel_FL_kph','wheel_FR_kph','wheel_RL_kph','wheel_RR_kph',
             'brake_pedal_state'}

def distance_resample_xte(x_true, y_true, x_pred, y_pred, ds=1.0):
    """Resample both at uniform distance ds along TRUE path, compute cross-track error.
    XTE here = euclidean distance between truth and pred at matched arc-length."""
    # arc length of true path
    dx = np.diff(x_true); dy = np.diff(y_true)
    seg = np.sqrt(dx*dx + dy*dy)
    s_true = np.concatenate([[0], np.cumsum(seg)])
    # arc length of pred
    dxp = np.diff(x_pred); dyp = np.diff(y_pred)
    segp = np.sqrt(dxp*dxp + dyp*dyp)
    s_pred = np.concatenate([[0], np.cumsum(segp)])

    L_total = min(s_true[-1], s_pred[-1])
    if L_total < 5.0:
        return None
    s = np.arange(0, L_total + ds/2, ds)
    if len(s) < 2:
        return None
    xt = np.interp(s, s_true, x_true)
    yt = np.interp(s, s_true, y_true)
    xp = np.interp(s, s_pred, x_pred)
    yp = np.interp(s, s_pred, y_pred)
    err = np.sqrt((xt-xp)**2 + (yt-yp)**2)
    return err

def score(plat, limit=None):
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/{plat}/*/*/*/sim.csv'))
    if limit:
        files = files[:limit]
    yr_sq = 0.0; yr_n = 0
    yr_sq_v0 = 0.0
    xte_sq = 0.0; xte_n = 0
    xte_sq_v0 = 0.0; xte_n_v0 = 0
    for f in files:
        df = pd.read_csv(f)
        # Strip truth/post-hoc cols to mimic sim-only contract
        sim_in_cols = [c for c in df.columns if c not in DROP_COLS]
        sim_in = df[sim_in_cols].copy()
        # also rename brake if present
        if 'brake_pedal_state' in df.columns and 'brake_pressed' not in sim_in.columns:
            sim_in['brake_pressed'] = (df['brake_pedal_state'] > 0).astype(int)

        out = predict(sim_in, plat)
        if 'yaw_rate_meas_rads' in df.columns:
            yr_true = df['yaw_rate_meas_rads'].values
            yr_pred = out['yaw_rate_pred_rads'].values
            r = yr_true - yr_pred
            yr_sq += float((r**2).sum())
            yr_n += len(r)
            # V0 baseline
            if 'yaw_rate_pred_rads' in df.columns:
                pass  # we already dropped it; recompute KS
            yr_v0 = (df['v_mps']/{'HYUNDAI_IONIQ_5':3.0,'FORD_MUSTANG_MACH_E_MK1':2.984,'FORD_F_150_LIGHTNING_MK1':3.70,'TESLA_MODEL_3':2.875}[plat])*np.tan(df['delta_road_rad'])
            yr_sq_v0 += float(((yr_true - yr_v0)**2).sum())

            # XTE: integrate truth yaw rate to get truth trajectory
            t_arr = df['t_s'].values
            v_arr = df['v_mps'].values
            N = len(t_arr)
            psi_t = np.zeros(N); xt = np.zeros(N); yt = np.zeros(N)
            for k in range(N-1):
                dt = t_arr[k+1]-t_arr[k]
                if dt <= 0 or not np.isfinite(dt): dt = 0.02
                yr_mid = 0.5*(yr_true[k]+yr_true[k+1])
                psi_t[k+1] = psi_t[k] + yr_mid*dt
                psi_mid = 0.5*(psi_t[k]+psi_t[k+1])
                v_mid = 0.5*(v_arr[k]+v_arr[k+1])
                xt[k+1] = xt[k] + v_mid*np.cos(psi_mid)*dt
                yt[k+1] = yt[k] + v_mid*np.sin(psi_mid)*dt
            if True:
                xp = out['x_m'].values; yp = out['y_m'].values
                err = distance_resample_xte(xt, yt, xp, yp, ds=1.0)
                if err is not None:
                    xte_sq += float((err**2).sum())
                    xte_n += len(err)
                # V0 trajectory
                v0_yr = yr_v0.values
                # integrate V0
                t = df['t_s'].values
                v_ = df['v_mps'].values
                N = len(t)
                psi = np.zeros(N); xv = np.zeros(N); yv = np.zeros(N)
                for k in range(N-1):
                    dt = t[k+1]-t[k]
                    if dt <= 0 or not np.isfinite(dt): dt = 0.02
                    yr_mid = 0.5*(v0_yr[k]+v0_yr[k+1])
                    psi[k+1] = psi[k] + yr_mid*dt
                    psi_mid = 0.5*(psi[k]+psi[k+1])
                    v_mid = 0.5*(v_[k]+v_[k+1])
                    xv[k+1] = xv[k] + v_mid*np.cos(psi_mid)*dt
                    yv[k+1] = yv[k] + v_mid*np.sin(psi_mid)*dt
                err_v0 = distance_resample_xte(xt, yt, xv, yv, ds=1.0)
                if err_v0 is not None:
                    xte_sq_v0 += float((err_v0**2).sum())
                    xte_n_v0 += len(err_v0)
    yr_rmse = np.sqrt(yr_sq/yr_n) if yr_n else None
    yr_rmse_v0 = np.sqrt(yr_sq_v0/yr_n) if yr_n else None
    xte_rmse = np.sqrt(xte_sq/xte_n) if xte_n else None
    xte_rmse_v0 = np.sqrt(xte_sq_v0/xte_n_v0) if xte_n_v0 else None
    return {
        'platform': plat,
        'n_segs': len(files),
        'yaw_rate_rmse': yr_rmse,
        'yaw_rate_rmse_v0': yr_rmse_v0,
        'xte_rmse': xte_rmse,
        'xte_rmse_v0': xte_rmse_v0,
    }

results = []
for plat in PLATFORMS_TRUTH:
    r = score(plat, limit=80)
    print(r)
    results.append(r)

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/out/local_scores.json','w') as f:
    json.dump(results, f, indent=2)
