"""Vectorized per-platform fitter.

Caches per-segment arrays once; objective is fast.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-10")


def find_segments(plat: str):
    sim_root = ROOT / "data" / "sim" / "segments" / plat
    return sorted(sim_root.rglob("sim.csv"))


def cache_segment(p: Path):
    df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps",
                                  "yaw_rate_meas_rads", "yaw_rate_pred_rads"])
    t = df["t_s"].to_numpy(dtype=np.float64)
    dt = np.diff(t, prepend=t[0])
    v = df["v_mps"].to_numpy(dtype=np.float64)
    delta_road = df["delta_road_rad"].to_numpy(dtype=np.float64)
    yr_truth = df["yaw_rate_meas_rads"].to_numpy(dtype=np.float64)
    yr_pred0 = df["yaw_rate_pred_rads"].to_numpy(dtype=np.float64)
    # Per-segment delta0 from input-only proxy.
    a_lat_proxy = v * yr_pred0
    mask = (np.abs(a_lat_proxy) < 0.3) & (v > 5.0)
    d0_segment = float(np.median(delta_road[mask])) if int(mask.sum()) >= 50 else None
    return {
        "t": t, "dt": dt, "v": v, "delta_road": delta_road,
        "yr_truth": yr_truth, "d0_segment": d0_segment,
    }


def predict_yaw_fast(seg, g, L_eff, K_us, tau, delta0):
    delta = (seg["delta_road"] - delta0) * g
    v = seg["v"]
    yr_ss = v * delta / (L_eff + K_us * v * v)
    dt = seg["dt"]
    alpha = dt / (tau + dt)
    n = len(yr_ss)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    # Loop is unavoidable for first-order lag; use np to keep it tight.
    for i in range(1, n):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def fit_platform(plat: str, use_per_seg_delta0: bool, x0=None, verbose=True):
    paths = find_segments(plat)
    segs = [cache_segment(p) for p in paths]
    n_total = sum(len(s["yr_truth"]) for s in segs)
    print(f"[{plat}] {len(segs)} segs, {n_total} samples")
    if not segs:
        return None

    if x0 is None:
        x0 = np.array([0.88, 2.85, 0.0025, 0.065, 0.0005])

    def loss(x):
        g, L_eff, K_us, tau, delta0_glob = x
        if L_eff < 1.5 or tau < 0.005 or K_us < 0 or g < 0.3 or g > 1.5:
            return 1e9
        sum_sq = 0.0
        n = 0
        for s in segs:
            d0 = (s["d0_segment"] if (use_per_seg_delta0 and s["d0_segment"] is not None)
                  else delta0_glob)
            yr = predict_yaw_fast(s, g, L_eff, K_us, tau, d0)
            r = yr - s["yr_truth"]
            sum_sq += float((r * r).sum())
            n += len(r)
        return sum_sq / n

    t0 = time.time()
    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-11, "maxiter": 1500})
    dt_fit = time.time() - t0
    g, L_eff, K_us, tau, delta0_glob = res.x
    rmse = math.sqrt(res.fun)
    print(f"  fit ({dt_fit:.1f}s, {res.nit} iter): g={g:.4f} L_eff={L_eff:.3f} "
          f"K_us={K_us:.5f} tau={tau:.4f} delta0={delta0_glob:.5f}")
    print(f"  train yaw RMSE = {rmse:.6f}")
    return {
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau), "delta0_glob": float(delta0_glob),
        "use_per_segment_delta0": use_per_seg_delta0,
        "train_yaw_rmse": rmse,
    }


if __name__ == "__main__":
    plat_cfg = {
        "FORD_F_150_LIGHTNING_MK1": False,
        "FORD_MUSTANG_MACH_E_MK1": True,
        "HYUNDAI_IONIQ_5": False,
    }
    results = {}
    for plat, use_per_seg in plat_cfg.items():
        r = fit_platform(plat, use_per_seg)
        if r:
            results[plat] = r
    out_path = ROOT / "out" / "coeffs_fit.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")
