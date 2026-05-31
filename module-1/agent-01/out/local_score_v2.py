"""Score V1 vs V0 properly.
   Truth trajectory = integrate yaw_rate_meas with v_mps (same integrator).
   V0 trajectory  = integrate sim-only yaw_rate_pred_rads with v_mps.
   V1 trajectory  = predict() output (x_m, y_m).
   Report yaw RMSE + distance-resampled CTE RMSE."""
import glob, os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/final-model')
from predict import predict, _cumtrapz

SIM_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim/segments'
SIMONLY_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim-only/segments'
PLATFORMS = ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1', 'HYUNDAI_IONIQ_5']
INPUT_COLS = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2','accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

def cte_rmse(xp, yp, xt, yt, ds=1.0):
    dx = np.diff(xt); dy = np.diff(yt)
    s_t = np.concatenate(([0], np.cumsum(np.hypot(dx,dy))))
    if s_t[-1] < 2*ds: return np.nan
    ss = np.arange(0, s_t[-1], ds)
    xts = np.interp(ss, s_t, xt); yts = np.interp(ss, s_t, yt)
    dxp = np.diff(xp); dyp = np.diff(yp)
    s_p = np.concatenate(([0], np.cumsum(np.hypot(dxp,dyp))))
    if s_p[-1] < ds: return np.nan
    sf = np.arange(0, s_p[-1], 0.25)
    xpf = np.interp(sf, s_p, xp); ypf = np.interp(sf, s_p, yp)
    cte = np.empty(len(xts))
    for i in range(0, len(xts), 200):
        d = np.hypot(xpf[None,:] - xts[i:i+200,None], ypf[None,:] - yts[i:i+200,None])
        cte[i:i+200] = d.min(axis=1)
    return np.sqrt(np.mean(cte**2))

summary = {}
for p in PLATFORMS:
    so_files = sorted(glob.glob(f'{SIMONLY_ROOT}/{p}/*/*/*/sim.csv'))[::3]
    se_v0=0.; se_v1=0.; n=0
    cte_v0_list=[]; cte_v1_list=[]
    for so in so_files:
        truth_path = os.path.join(SIM_ROOT, os.path.relpath(so, SIMONLY_ROOT))
        if not os.path.exists(truth_path): continue
        sdf = pd.read_csv(so)
        truth = pd.read_csv(truth_path)
        if 'yaw_rate_meas_rads' not in truth.columns: continue
        sdf_in = sdf[INPUT_COLS].copy()
        pred = predict(sdf_in, p)
        m = sdf_in['v_mps'].values > 1.0
        y_truth = truth['yaw_rate_meas_rads'].values
        se_v0 += ((sdf_in['yaw_rate_pred_rads'].values - y_truth)[m]**2).sum()
        se_v1 += ((pred['yaw_rate_pred_rads'].values - y_truth)[m]**2).sum()
        n += m.sum()
        # truth trajectory: integrate yaw_rate_meas with v
        t = sdf_in['t_s'].values; v = sdf_in['v_mps'].values
        psi_t = _cumtrapz(y_truth, t)
        xt = _cumtrapz(v*np.cos(psi_t), t); yt = _cumtrapz(v*np.sin(psi_t), t)
        # V0 trajectory
        yr0 = sdf_in['yaw_rate_pred_rads'].values
        psi0 = _cumtrapz(yr0, t)
        x0 = _cumtrapz(v*np.cos(psi0), t); y0 = _cumtrapz(v*np.sin(psi0), t)
        c0 = cte_rmse(x0,y0,xt,yt)
        c1 = cte_rmse(pred['x_m'].values, pred['y_m'].values, xt, yt)
        if np.isfinite(c0): cte_v0_list.append(c0)
        if np.isfinite(c1): cte_v1_list.append(c1)
    rmse_v0 = np.sqrt(se_v0/n); rmse_v1 = np.sqrt(se_v1/n)
    cte_v0 = float(np.sqrt(np.mean(np.array(cte_v0_list)**2))) if cte_v0_list else float('nan')
    cte_v1 = float(np.sqrt(np.mean(np.array(cte_v1_list)**2))) if cte_v1_list else float('nan')
    print(f'{p}: segs={len(so_files)}, samples={n}')
    print(f'  yaw RMSE  V0={rmse_v0:.5f}  V1={rmse_v1:.5f}  (delta {100*(rmse_v0-rmse_v1)/rmse_v0:+.1f}%)')
    print(f'  CTE  RMSE V0={cte_v0:.2f} m  V1={cte_v1:.2f} m  (delta {100*(cte_v0-cte_v1)/cte_v0:+.1f}%)')
    summary[p] = {'yaw_v0': rmse_v0, 'yaw_v1': rmse_v1, 'cte_v0': cte_v0, 'cte_v1': cte_v1, 'n': int(n), 'segs': len(so_files)}

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/out/score_summary.json','w') as f:
    json.dump(summary, f, indent=2)
