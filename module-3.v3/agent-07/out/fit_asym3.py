"""Fit just (g_left, g_right) per platform — V1's other coeffs are kept.

Use closed-form-ish approach: minimize weighted sum of yaw RMSE^2 + lambda * CTE RMSE^2,
optimising 2 params only. Keep the rest of V1 fixed.
"""
import sys, glob, json, time
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0
from traj_metrics import cte_diagnostics_segment

ALLOWED = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2','accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

def prep_segment(df, plat):
    p = PLATFORM_PARAMS_V1[plat]
    cols = [c for c in ALLOWED if c in df.columns]
    sim = df[cols].copy()
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta_raw = sim['delta_road_rad'].to_numpy() - delta0
    v = sim['v_mps'].to_numpy(); t = sim['t_s'].to_numpy()
    dt = np.diff(t, prepend=t[0])
    return {
        't': t, 'dt': dt, 'v': v, 'delta_raw': delta_raw,
        'mask_v': v>2,
        'yt': df['yaw_rate_meas_rads'].to_numpy(),
        'L_eff': p['L_eff'], 'K_us': p['K_us'], 'tau': p['tau'],
    }

def predict_yaw(seg, g_left, g_right, eps=0.005):
    delta_raw = seg['delta_raw']; v = seg['v']; dt = seg['dt']
    w_left = 0.5 * (1.0 + np.tanh(delta_raw / eps))
    g_eff = g_left*w_left + g_right*(1.0-w_left)
    delta = delta_raw * g_eff
    yr_ss = v * delta / (seg['L_eff'] + seg['K_us'] * v * v)
    alpha = dt / (seg['tau'] + dt)
    n = len(yr_ss)
    one_minus_a = 1.0 - alpha
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for i in range(1, n):
        yr[i] = one_minus_a[i]*yr[i-1] + alpha[i]*yr_ss[i]
    return yr

def scores(segs, g_left, g_right):
    yaw_sq=0;yaw_n=0;cte_sq=0;cte_n=0
    for s in segs:
        yr = predict_yaw(s, g_left, g_right)
        m=s['mask_v']; r=(yr-s['yt'])[m]
        yaw_sq+=float((r*r).sum()); yaw_n+=int(m.sum())
        d=cte_diagnostics_segment(s['t'],s['v'],s['yt'],yr)
        cte_sq+=d['sum_sq_m2']; cte_n+=d['n_bins']
    yaw = np.sqrt(yaw_sq/yaw_n)
    cte = np.sqrt(cte_sq/cte_n) if cte_n else float('nan')
    return yaw, cte

def loss(params, segs, yaw_anchor, cte_anchor, weight_cte=0.5):
    g_left, g_right = params
    if g_left<=0 or g_right<=0: return 1e9
    yaw, cte = scores(segs, g_left, g_right)
    return yaw/yaw_anchor + weight_cte*cte/cte_anchor

def load(plat, n=120):
    paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))[:n]
    segs=[]
    for p in paths:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns: continue
        segs.append(prep_segment(df, plat))
    return segs

PLATFORMS = ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1', 'HYUNDAI_IONIQ_5']
out = {}
for plat in PLATFORMS:
    t0 = time.time()
    segs = load(plat, n=80)
    p = PLATFORM_PARAMS_V1[plat]
    yaw_v1, cte_v1 = scores(segs, p['g'], p['g'])
    print(f"\n=== {plat} (n_seg={len(segs)}) ===")
    print(f"V1: yaw={yaw_v1:.5f}, cte={cte_v1:.3f}")
    res = minimize(loss, [p['g'], p['g']],
                   args=(segs, yaw_v1, cte_v1, 0.5),
                   method='Nelder-Mead',
                   options={'xatol':1e-5,'fatol':1e-7,'maxiter':100})
    gl, gr = res.x
    yaw, cte = scores(segs, gl, gr)
    print(f"BEST: g_left={gl:.4f}, g_right={gr:.4f} -> yaw={yaw:.5f} ({100*(yaw-yaw_v1)/yaw_v1:+.1f}%), cte={cte:.3f} ({100*(cte-cte_v1)/cte_v1:+.1f}%) in {time.time()-t0:.0f}s")
    out[plat] = {
        'g_left': float(gl), 'g_right': float(gr),
        'blend_eps': 0.005,
        'L_eff': p['L_eff'], 'K_us': p['K_us'], 'tau': p['tau'],
        'k_dd': 0.0,
        '_yaw_v1': yaw_v1, '_cte_v1': cte_v1,
        '_yaw_fit': yaw, '_cte_fit': cte,
    }

with open(ROOT / "models/v1-asym-gain/coeffs.json","w") as f:
    json.dump(out, f, indent=2)
print("\nSaved")
