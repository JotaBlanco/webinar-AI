"""Refit V1 coefficients per platform on dev data, jointly minimising yaw RMSE.

V1 model:
    delta_eff = (delta_road - delta0) * g
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)
    first-order lag with time constant tau (discrete IIR).

Fit: 5 free params per platform (g, L_eff, K_us, tau, delta0) — or use per-segment delta0.
Optimize yaw RMSE over pooled samples (v_mps > 2.0).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

SEG_ROOT = ROOT / "data" / "sim" / "segments"

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def predict_yr(delta_road, v, t, g, L_eff, K_us, tau, delta0):
    delta = (delta_road - delta0) * g
    yr_ss = v * delta / (L_eff + K_us * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def load_segments(platform: str):
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    segs = []
    for p in paths:
        df = pd.read_csv(p, usecols=lambda c: c in {
            "t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"
        })
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        segs.append(df)
    return segs


def loss_global_delta0(params, segs):
    g, L_eff, K_us, tau, delta0 = params
    if L_eff <= 0 or tau <= 0 or g <= 0:
        return 1e6
    sum_sq = 0.0
    n = 0
    for df in segs:
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        yr = predict_yr(delta, v, t, g, L_eff, K_us, tau, delta0)
        m = v > 2.0
        r = yr[m] - truth[m]
        sum_sq += float(np.sum(r * r))
        n += int(m.sum())
    return sum_sq / max(n, 1)


def loss_per_seg_delta0(params, segs):
    g, L_eff, K_us, tau, fallback = params
    if L_eff <= 0 or tau <= 0 or g <= 0:
        return 1e6
    sum_sq = 0.0
    n = 0
    for df in segs:
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        # per-seg delta0 derived from v0 col (still using v0 — V1 strategy)
        delta0 = per_segment_delta0(df, fallback=fallback)
        yr = predict_yr(delta, v, t, g, L_eff, K_us, tau, delta0)
        m = v > 2.0
        r = yr[m] - truth[m]
        sum_sq += float(np.sum(r * r))
        n += int(m.sum())
    return sum_sq / max(n, 1)


def fit_platform(platform: str, use_per_seg_delta0: bool, x0):
    print(f"\n=== fitting {platform} (per_seg_delta0={use_per_seg_delta0}) ===")
    segs = load_segments(platform)
    print(f"  {len(segs)} segments")
    if use_per_seg_delta0:
        f = lambda x: loss_per_seg_delta0(x, segs)
    else:
        f = lambda x: loss_global_delta0(x, segs)
    init_loss = f(x0)
    print(f"  init MSE: {init_loss:.8f}  init RMSE: {np.sqrt(init_loss):.6f}")
    res = minimize(f, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 1000})
    print(f"  final MSE: {res.fun:.8f}  final RMSE: {np.sqrt(res.fun):.6f}")
    print(f"  params: g={res.x[0]:.4f} L_eff={res.x[1]:.4f} K_us={res.x[2]:.6f} tau={res.x[3]:.4f} delta0/fallback={res.x[4]:.6f}")
    return res.x, res.fun


if __name__ == "__main__":
    results = {}
    # F-150 Lightning: V1 uses global delta0
    x, _ = fit_platform(
        "FORD_F_150_LIGHTNING_MK1",
        use_per_seg_delta0=False,
        x0=[0.863, 3.26, 0.00350, 0.060, 0.00133],
    )
    results["FORD_F_150_LIGHTNING_MK1"] = {
        "use_per_segment_delta0": False,
        "g": float(x[0]), "L_eff": float(x[1]), "K_us": float(x[2]),
        "tau": float(x[3]), "delta0": float(x[4]),
    }

    # Mach-E: try BOTH per-seg and global, take whichever fits better.
    x_g, l_g = fit_platform(
        "FORD_MUSTANG_MACH_E_MK1",
        use_per_seg_delta0=False,
        x0=[0.891, 2.22, 0.00150, 0.069, -0.0001],
    )
    x_s, l_s = fit_platform(
        "FORD_MUSTANG_MACH_E_MK1",
        use_per_seg_delta0=True,
        x0=[0.891, 2.22, 0.00150, 0.069, -0.0001],
    )
    if l_g < l_s:
        results["FORD_MUSTANG_MACH_E_MK1"] = {
            "use_per_segment_delta0": False,
            "g": float(x_g[0]), "L_eff": float(x_g[1]), "K_us": float(x_g[2]),
            "tau": float(x_g[3]), "delta0": float(x_g[4]),
        }
        print(f"  Mach-E: GLOBAL delta0 wins ({np.sqrt(l_g):.6f} vs {np.sqrt(l_s):.6f})")
    else:
        results["FORD_MUSTANG_MACH_E_MK1"] = {
            "use_per_segment_delta0": True,
            "g": float(x_s[0]), "L_eff": float(x_s[1]), "K_us": float(x_s[2]),
            "tau": float(x_s[3]), "delta0_fallback": float(x_s[4]),
        }
        print(f"  Mach-E: PER-SEG delta0 wins ({np.sqrt(l_s):.6f} vs {np.sqrt(l_g):.6f})")

    # Hyundai: try BOTH
    x_g, l_g = fit_platform(
        "HYUNDAI_IONIQ_5",
        use_per_seg_delta0=False,
        x0=[0.938, 2.887, 0.00289, 0.062, 0.0],
    )
    x_s, l_s = fit_platform(
        "HYUNDAI_IONIQ_5",
        use_per_seg_delta0=True,
        x0=[0.938, 2.887, 0.00289, 0.062, 0.0],
    )
    if l_g < l_s:
        results["HYUNDAI_IONIQ_5"] = {
            "use_per_segment_delta0": False,
            "g": float(x_g[0]), "L_eff": float(x_g[1]), "K_us": float(x_g[2]),
            "tau": float(x_g[3]), "delta0": float(x_g[4]),
        }
        print(f"  Hyundai: GLOBAL delta0 wins ({np.sqrt(l_g):.6f} vs {np.sqrt(l_s):.6f})")
    else:
        results["HYUNDAI_IONIQ_5"] = {
            "use_per_segment_delta0": True,
            "g": float(x_s[0]), "L_eff": float(x_s[1]), "K_us": float(x_s[2]),
            "tau": float(x_s[3]), "delta0_fallback": float(x_s[4]),
        }
        print(f"  Hyundai: PER-SEG delta0 wins ({np.sqrt(l_s):.6f} vs {np.sqrt(l_g):.6f})")

    import json
    out_path = ROOT / "out" / "v2_params.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {out_path}")
    print(json.dumps(results, indent=2))
