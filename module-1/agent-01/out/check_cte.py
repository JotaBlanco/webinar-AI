"""Sanity check on CTE: compare V0 trajectory (from sim-only yaw_rate_pred_rads)
   vs truth trajectory."""
import glob, os
import numpy as np, pandas as pd, sys
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/final-model')
from predict import _cumtrapz

SIM_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim/segments'
SIMONLY_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/data/sim-only/segments'

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

for p in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
    files = sorted(glob.glob(f'{SIMONLY_ROOT}/{p}/*/*/*/sim.csv'))[:30]
    cte_v0_list = []
    cte_truth_self = []
    for so in files:
        truth_path = os.path.join(SIM_ROOT, os.path.relpath(so, SIMONLY_ROOT))
        if not os.path.exists(truth_path): continue
        so_df = pd.read_csv(so)
        truth = pd.read_csv(truth_path)
        if 'x_m' not in truth.columns: continue
        # V0 trajectory from sim-only yaw_rate_pred_rads
        t = so_df['t_s'].values; v = so_df['v_mps'].values
        yr0 = so_df['yaw_rate_pred_rads'].values
        psi0 = _cumtrapz(yr0, t)
        x0 = _cumtrapz(v*np.cos(psi0), t); y0 = _cumtrapz(v*np.sin(psi0), t)
        cte_v0_list.append(cte_rmse(x0,y0, truth['x_m'].values, truth['y_m'].values))
        # truth integrated from truth yaw_rate via same integrator (self-consistency)
        yr_t = truth['yaw_rate_meas_rads'].values
        psi_t = _cumtrapz(yr_t, t)
        xti = _cumtrapz(v*np.cos(psi_t), t); yti = _cumtrapz(v*np.sin(psi_t), t)
        cte_truth_self.append(cte_rmse(xti, yti, truth['x_m'].values, truth['y_m'].values))
    print(f'{p}: V0_cte={np.sqrt(np.mean(np.array(cte_v0_list)**2)):.2f} m, '
          f'truth_self_cte={np.sqrt(np.mean(np.array(cte_truth_self)**2)):.2f} m '
          f'(n={len(cte_v0_list)})')
