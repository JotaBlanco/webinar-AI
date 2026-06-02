"""Fit per-platform (k_dd, gain_corr) for v1-steerrate-ff."""
import sys, glob, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1
from traj_metrics import cte_diagnostics_segment

ALLOWED = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2','accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

def load_platform(plat, n_seg=200):
    paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))[:n_seg]
    out = []
    for p in paths:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns: continue
        cols = [c for c in ALLOWED if c in df.columns]
        sim = df[cols].copy()
        v1 = predict_v1(sim, plat)['yaw_rate_pred_rads'].to_numpy()
        t = df['t_s'].to_numpy(); v = df['v_mps'].to_numpy()
        delta = df['delta_road_rad'].to_numpy()
        ddelta = np.gradient(delta, t) if len(t)>=3 else np.zeros_like(delta)
        yt = df['yaw_rate_meas_rads'].to_numpy()
        out.append({'t':t,'v':v,'v1':v1,'ddelta':ddelta,'yt':yt})
    return out

def score_yaw(segs, k_dd, g_corr):
    sum_sq = 0.0; n = 0
    for s in segs:
        m = s['v']>2
        yr = s['v1']*g_corr + k_dd * s['ddelta'] * np.clip(s['v'], 0.0, 40.0)/30.0
        r = (yr - s['yt'])[m]
        sum_sq += float((r*r).sum()); n += int(m.sum())
    return np.sqrt(sum_sq/n) if n else float('nan')

def score_cte(segs, k_dd, g_corr):
    total_sq=0.0; total_n=0
    for s in segs:
        yr = s['v1']*g_corr + k_dd * s['ddelta'] * np.clip(s['v'], 0.0, 40.0)/30.0
        d = cte_diagnostics_segment(s['t'], s['v'], s['yt'], yr)
        total_sq += d['sum_sq_m2']; total_n += d['n_bins']
    return np.sqrt(total_sq/total_n) if total_n else float('nan')

PLATFORMS = ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1', 'HYUNDAI_IONIQ_5']
results = {}
for plat in PLATFORMS:
    segs = load_platform(plat, n_seg=120)
    print(f"\n=== {plat} ({len(segs)} segs) ===")
    # Score V1 as baseline
    yaw_v1 = score_yaw(segs, 0.0, 1.0); cte_v1 = score_cte(segs, 0.0, 1.0)
    print(f"V1: yaw={yaw_v1:.5f}, cte={cte_v1:.3f}")
    best = None
    for g in np.linspace(0.98, 1.03, 11):
        for k in np.linspace(-0.10, 0.30, 21):
            y = score_yaw(segs, k, g)
            c = score_cte(segs, k, g)
            # Combined score: yaw and CTE both matter; weight yaw heavier
            sc = y / yaw_v1 + 0.5 * c / cte_v1
            if best is None or sc < best['sc']:
                best = {'sc': sc, 'k': k, 'g': g, 'yaw': y, 'cte': c}
    print(f"BEST: g={best['g']:.4f}, k_dd={best['k']:.3f} -> yaw={best['yaw']:.5f} (Δ{100*(best['yaw']-yaw_v1)/yaw_v1:+.1f}%), cte={best['cte']:.3f} (Δ{100*(best['cte']-cte_v1)/cte_v1:+.1f}%)")
    results[plat] = {'k_dd': float(best['k']), 'gain_corr': float(best['g']),
                     'yaw_v1': yaw_v1, 'cte_v1': cte_v1,
                     'yaw_fit': best['yaw'], 'cte_fit': best['cte']}

with open(ROOT / "out/ff_coeffs.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved", ROOT / "out/ff_coeffs.json")
