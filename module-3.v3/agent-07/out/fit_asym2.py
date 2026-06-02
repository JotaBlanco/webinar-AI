"""Faster asymmetric-gain fit using scipy.optimize.minimize.

Now also fits a steering-derivative feedforward term k_dd and refits L_eff/K_us/tau
slightly to combine the structural change with re-calibration.
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
    ddelta = np.gradient(sim['delta_road_rad'].to_numpy(), t) if len(t)>=3 else np.zeros_like(delta_raw)
    return {
        't': t, 'dt': dt, 'v': v, 'delta_raw': delta_raw, 'ddelta': ddelta,
        'mask_v': v>2,
        'yt': df['yaw_rate_meas_rads'].to_numpy(),
    }

def predict_yaw(seg, g_left, g_right, eps, L_eff, K_us, tau, k_dd):
    delta_raw = seg['delta_raw']; v = seg['v']; dt = seg['dt']
    w_left = 0.5 * (1.0 + np.tanh(delta_raw / max(eps, 1e-6)))
    g_eff = g_left*w_left + g_right*(1.0-w_left)
    delta = delta_raw * g_eff
    yr_ss = v * delta / (L_eff + K_us * v * v)
    alpha = dt / (tau + dt)
    # First-order lag
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    # Use cumulative product trick? Lag is yr[i] = (1-a)*yr[i-1] + a*yr_ss[i]
    # Hard to vectorize fully; loop in numpy but tight
    n = len(yr)
    one_minus_a = 1.0 - alpha
    a = alpha
    yr_prev = yr_ss[0]
    yrs = yr_ss
    yr_arr = np.empty(n)
    yr_arr[0] = yr_prev
    for i in range(1, n):
        yr_prev = one_minus_a[i]*yr_prev + a[i]*yrs[i]
        yr_arr[i] = yr_prev
    # Feedforward
    yr_arr = yr_arr + k_dd * seg['ddelta'] * np.clip(v, 0.0, 40.0)/30.0
    return yr_arr

def loss(params, segs, weights=(1.0, 0.5)):
    g_left, g_right, eps, L_eff, K_us, tau, k_dd = params
    if eps <= 0 or L_eff <= 0 or tau <= 0 or K_us < 0:
        return 1e9
    yaw_sq = 0.0; yaw_n = 0
    cte_sq = 0.0; cte_n = 0
    for s in segs:
        yr = predict_yaw(s, g_left, g_right, eps, L_eff, K_us, tau, k_dd)
        if not np.all(np.isfinite(yr)):
            return 1e9
        m = s['mask_v']
        r = (yr - s['yt'])[m]
        yaw_sq += float((r*r).sum()); yaw_n += int(m.sum())
        d = cte_diagnostics_segment(s['t'], s['v'], s['yt'], yr)
        cte_sq += d['sum_sq_m2']; cte_n += d['n_bins']
    yaw = np.sqrt(yaw_sq/yaw_n) if yaw_n else float('nan')
    cte = np.sqrt(cte_sq/cte_n) if cte_n else float('nan')
    # Normalize by V1 anchors? We use ratios.
    return weights[0]*yaw + weights[1]*cte*0.0001  # small CTE weight in absolute terms

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
    segs = load(plat, n=80)  # smaller for speed
    p = PLATFORM_PARAMS_V1[plat]
    x0 = np.array([p['g'], p['g'], 0.005, p['L_eff'], p['K_us'], p['tau'], 0.0])
    y_v1 = loss(x0, segs, weights=(1.0,0.0))
    print(f"\n=== {plat} (n_seg={len(segs)}) ===")
    print(f"V1 yaw_only loss = {y_v1:.6f}")
    # Optimise
    res = minimize(
        loss, x0, args=(segs, (1.0, 0.5)),
        method='Nelder-Mead',
        options={'xatol':1e-5,'fatol':1e-7,'maxiter':400,'disp':False}
    )
    x = res.x
    print(f"opt result: success={res.success}, iters={res.nit}, final loss={res.fun:.6f}")
    print(f"  g_left={x[0]:.4f}, g_right={x[1]:.4f}, eps={x[2]:.4f}, L_eff={x[3]:.3f}, K_us={x[4]:.5f}, tau={x[5]:.3f}, k_dd={x[6]:.4f}")
    # Re-score yaw+cte
    yaw_sq=0;yaw_n=0;cte_sq=0;cte_n=0
    for s in segs:
        yr = predict_yaw(s, *x)
        m=s['mask_v']; r=(yr-s['yt'])[m]
        yaw_sq+=float((r*r).sum()); yaw_n+=int(m.sum())
        d=cte_diagnostics_segment(s['t'],s['v'],s['yt'],yr)
        cte_sq+=d['sum_sq_m2']; cte_n+=d['n_bins']
    yaw_new = np.sqrt(yaw_sq/yaw_n)
    cte_new = np.sqrt(cte_sq/cte_n) if cte_n else float('nan')
    # V1 baselines
    yaw_sq=0;yaw_n=0;cte_sq=0;cte_n=0
    for s in segs:
        yr = predict_yaw(s, p['g'], p['g'], 0.005, p['L_eff'], p['K_us'], p['tau'], 0.0)
        m=s['mask_v']; r=(yr-s['yt'])[m]
        yaw_sq+=float((r*r).sum()); yaw_n+=int(m.sum())
        d=cte_diagnostics_segment(s['t'],s['v'],s['yt'],yr)
        cte_sq+=d['sum_sq_m2']; cte_n+=d['n_bins']
    yaw_v1 = np.sqrt(yaw_sq/yaw_n)
    cte_v1 = np.sqrt(cte_sq/cte_n) if cte_n else float('nan')
    print(f"YAW: {yaw_v1:.5f} -> {yaw_new:.5f} ({100*(yaw_new-yaw_v1)/yaw_v1:+.1f}%)")
    print(f"CTE: {cte_v1:.3f} -> {cte_new:.3f} ({100*(cte_new-cte_v1)/cte_v1:+.1f}%)")
    print(f"  ({time.time()-t0:.0f}s)")
    out[plat] = {
        'g_left': float(x[0]), 'g_right': float(x[1]),
        'blend_eps': float(x[2]),
        'L_eff': float(x[3]), 'K_us': float(x[4]), 'tau': float(x[5]),
        'k_dd': float(x[6]),
        '_yaw_v1': yaw_v1, '_cte_v1': cte_v1,
        '_yaw_fit': yaw_new, '_cte_fit': cte_new,
    }
with open(ROOT / "models/v1-asym-gain/coeffs.json","w") as f:
    json.dump(out, f, indent=2)
print("\nSaved coeffs to models/v1-asym-gain/coeffs.json")
