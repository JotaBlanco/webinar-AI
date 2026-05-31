"""V0 baseline CTE: integrate the sim-only yaw_rate_pred_rads with measured v
and compare its trajectory to the truth trajectory."""
import os, sys, glob, json, time
import numpy as np
import pandas as pd

ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-09'
sys.path.insert(0, os.path.join(ROOT, 'final-model'))
from predict import _cumtrapz

SIM_ROOT = f'{ROOT}/data/sim/segments'
SO_ROOT  = f'{ROOT}/data/sim-only/segments'

def arclength(x, y):
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    return s

def cte_rmse(x_truth, y_truth, x_pred, y_pred, ds=1.0):
    s_t = arclength(x_truth, y_truth)
    if s_t[-1] < 2*ds: return np.nan, 0
    s_tr = np.arange(0.0, s_t[-1], ds)
    xt = np.interp(s_tr, s_t, x_truth); yt = np.interp(s_tr, s_t, y_truth)
    s_p = arclength(x_pred, y_pred)
    if s_p[-1] < ds: return np.nan, 0
    s_pr = np.arange(0.0, s_p[-1], ds/2.0)
    xp = np.interp(s_pr, s_p, x_pred); yp = np.interp(s_pr, s_p, y_pred)
    n = len(xt); out = np.empty(n)
    pred_n = len(xp); half_window = 200
    for i in range(n):
        guess = int(round(s_tr[i] / (ds/2.0)))
        lo = max(0, guess - half_window); hi = min(pred_n, guess + half_window)
        dx = xp[lo:hi] - xt[i]; dy = yp[lo:hi] - yt[i]
        out[i] = np.sqrt((dx*dx + dy*dy).min())
    return float(np.sqrt(np.mean(out**2))), n

max_files = {'HYUNDAI_IONIQ_5': 100, 'FORD_MUSTANG_MACH_E_MK1': 60,
             'FORD_F_150_LIGHTNING_MK1': 60, 'TESLA_MODEL_3': 60}

for p in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1','TESLA_MODEL_3']:
    so_files = sorted(glob.glob(f'{SO_ROOT}/{p}/*/*/*/sim.csv'))[:max_files[p]]
    sse=0.0; n=0
    for sof in so_files:
        rel = os.path.relpath(sof, SO_ROOT)
        sf = os.path.join(SIM_ROOT, rel)
        if not os.path.exists(sf): continue
        sim = pd.read_csv(sf); so = pd.read_csv(sof)
        if 'x_m' not in sim.columns: continue
        t = so['t_s'].values; v = so['v_mps'].values
        yaw = so['yaw_rate_pred_rads'].values
        psi = _cumtrapz(yaw, t)
        xp = _cumtrapz(v*np.cos(psi), t)
        yp = _cumtrapz(v*np.sin(psi), t)
        xt = sim['x_m'].values; yt = sim['y_m'].values
        m = min(len(xt), len(xp))
        cte, k = cte_rmse(xt[:m], yt[:m], xp[:m], yp[:m])
        if not np.isnan(cte):
            sse += cte*cte*k; n += k
    print(f"V0 {p}: cte_rmse={np.sqrt(sse/n):.3f} m (n={n})")
