"""Fit per-platform parameters (g, K_us, delta_0, tau) from training segments."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'code')
from split import split
import pandas as pd
import numpy as np
import parameters as P
from scipy.optimize import least_squares

tr, dv = split(dev_fraction=0.25, seed=42)

L_MAP = {'FORD_F_150_LIGHTNING_MK1': P.F150_LIGHTNING.L,
         'FORD_MUSTANG_MACH_E_MK1': P.MACH_E.L}


def platform_from_path(p):
    return Path(p).resolve().parents[3].name


def load_concat(paths, plat):
    deltas, vs, yrs, a_lats, ts_list = [], [], [], [], []
    for p in paths:
        if platform_from_path(p) != plat:
            continue
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        m = (df['v_mps'] > 5).values
        deltas.append(df['delta_road_rad'].values[m])
        vs.append(df['v_mps'].values[m])
        yrs.append(df['yaw_rate_meas_rads'].values[m])
        if 'a_lat_meas_mps2' in df.columns:
            a_lats.append(df['a_lat_meas_mps2'].values[m])
        else:
            a_lats.append(np.zeros(m.sum()))
        ts_list.append(df['t_s'].values[m])
    return (np.concatenate(deltas), np.concatenate(vs),
            np.concatenate(yrs), np.concatenate(a_lats))


results = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    L = L_MAP[plat]
    delta, v, yr, a_lat = load_concat(tr, plat)
    print(f"\n{plat}: {len(delta)} samples (v>5)")

    # Estimate delta_0
    mask_straight = np.abs(yr) < 0.005
    d0_est = float(np.median(delta[mask_straight]))
    print(f"  delta_0 init: {d0_est:.6f} ({np.degrees(d0_est):.4f} deg)")

    def resid(params, delta, v, yr, L):
        g, kus, d0 = params
        pred = v * g * (delta - d0) / (L + kus * v**2)
        return pred - yr

    x0 = [1.0, 0.003, d0_est]
    res = least_squares(
        resid, x0, args=(delta, v, yr, L),
        bounds=([0.5, -0.005, -0.05], [2.0, 0.030, 0.05]),
        max_nfev=500,
    )
    g, kus, d0 = res.x
    pred = v * g * (delta - d0) / (L + kus * v**2)
    rmse_ss = float(np.sqrt(np.mean((pred - yr)**2)))
    print(f"  Fit g={g:.4f}, K_us={kus:.5f}, delta_0={d0:.6f}")
    print(f"  SS pred RMSE on train: {rmse_ss:.5f}")
    print(f"  Bounds: lower-peg? {[abs(g-0.5)<1e-3, abs(kus-(-0.005))<1e-4, abs(d0-(-0.05))<1e-4]}")
    print(f"  Bounds: upper-peg? {[abs(g-2.0)<1e-3, abs(kus-0.030)<1e-4, abs(d0-0.05)<1e-4]}")

    results[plat] = {'g': g, 'K_us': kus, 'delta_0': d0, 'L': L}

print("\nFINAL:")
for k, v in results.items():
    print(f"  {k}: {v}")
