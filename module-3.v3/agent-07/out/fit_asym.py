"""Fit per-platform (g_left, g_right) for v1-asym-gain.

Cache the V1-precomputed quantities per segment and minimize total squared
residual via 2D scan over (g_left, g_right) holding other V1 coeffs fixed.

To make it fast we re-derive the (delta_raw, v, dt) pipeline once per segment
and rerun only the integration each scan step.
"""
import sys, glob, json
from pathlib import Path
import numpy as np, pandas as pd

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
    alpha = dt / (p['tau'] + dt)
    return {
        't': t, 'dt': dt, 'v': v, 'delta_raw': delta_raw, 'alpha': alpha,
        'L_eff': p['L_eff'], 'K_us': p['K_us'], 'tau': p['tau'],
        'yt': df['yaw_rate_meas_rads'].to_numpy(),
    }

def run_predict(seg, g_left, g_right, eps=0.005):
    delta_raw = seg['delta_raw']
    w_left = 0.5 * (1.0 + np.tanh(delta_raw / eps))
    g_eff = g_left*w_left + g_right*(1.0-w_left)
    delta = delta_raw * g_eff
    v = seg['v']
    yr_ss = v * delta / (seg['L_eff'] + seg['K_us'] * v * v)
    alpha = seg['alpha']
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr

def score(segs, g_left, g_right):
    sum_sq=0.0; n=0; cte_sq=0.0; cte_n=0
    for s in segs:
        yr = run_predict(s, g_left, g_right)
        m = s['v']>2
        r = (yr - s['yt'])[m]
        sum_sq += float((r*r).sum()); n += int(m.sum())
        d = cte_diagnostics_segment(s['t'], s['v'], s['yt'], yr)
        cte_sq += d['sum_sq_m2']; cte_n += d['n_bins']
    yaw = np.sqrt(sum_sq/n) if n else float('nan')
    cte = np.sqrt(cte_sq/cte_n) if cte_n else float('nan')
    return yaw, cte

def load(plat, n=200):
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
    segs = load(plat, n=120)
    p = PLATFORM_PARAMS_V1[plat]
    g0 = p['g']
    y_v1, c_v1 = score(segs, g0, g0)
    print(f"\n=== {plat} (n_seg={len(segs)}, g_v1={g0}) ===")
    print(f"V1: yaw={y_v1:.5f}, cte={c_v1:.3f}")
    best=None
    for gl in np.linspace(g0*0.85, g0*1.15, 25):
        for gr in np.linspace(g0*0.85, g0*1.15, 25):
            y,c = score(segs, gl, gr)
            sc = y/y_v1 + 0.6*c/c_v1
            if best is None or sc<best['sc']:
                best={'sc':sc,'gl':gl,'gr':gr,'yaw':y,'cte':c}
    print(f"BEST: g_left={best['gl']:.4f}, g_right={best['gr']:.4f} -> yaw={best['yaw']:.5f} (Δ{100*(best['yaw']-y_v1)/y_v1:+.1f}%), cte={best['cte']:.3f} (Δ{100*(best['cte']-c_v1)/c_v1:+.1f}%)")
    out[plat] = {
        'g_left': float(best['gl']), 'g_right': float(best['gr']),
        'blend_eps': 0.005, 'tau': p['tau'], 'K_us': p['K_us'], 'L_eff': p['L_eff'],
        '_v1_yaw': y_v1, '_v1_cte': c_v1,
        '_fit_yaw': best['yaw'], '_fit_cte': best['cte'],
    }
with open(ROOT / "models/v1-asym-gain/coeffs.json","w") as f:
    json.dump(out, f, indent=2)
print("\nSaved coeffs")
