"""Refit V1 params with bounds (avoid degenerate L_eff/g collapse).

Strategy:
- Fix g=1.0 for one model variant (the g*delta scaling is degenerate with L_eff and K_us).
- Also try per-segment-delta0 mode for F-150 (V1 textbook uses global).
- Use L-BFGS-B with sane bounds.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

SEG_ROOT = ROOT / "data" / "sim" / "segments"


def per_seg_delta0(df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def predict_yr(delta, v, t, g, L_eff, K_us, tau, delta0):
    d = (delta - delta0) * g
    yr_ss = v * d / (L_eff + K_us * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


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


def make_loss(segs, use_per_seg):
    # Precompute per-seg arrays
    pre = []
    for df in segs:
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        d0_perseg = per_seg_delta0(df, fallback=0.0) if use_per_seg else None
        pre.append((t, v, delta, truth, d0_perseg))

    def loss(params):
        g, L_eff, K_us, tau, d0 = params
        if L_eff <= 0 or tau <= 0 or g <= 0:
            return 1e6
        ss = 0.0
        n = 0
        for t, v, delta, truth, d0_perseg in pre:
            d0_use = d0_perseg if use_per_seg else d0
            yr = predict_yr(delta, v, t, g, L_eff, K_us, tau, d0_use)
            m = v > 2.0
            r = yr[m] - truth[m]
            ss += float(np.sum(r * r))
            n += int(m.sum())
        return ss / max(n, 1)
    return loss


def fit_with_bounds(loss, x0):
    bounds = [(0.5, 1.5), (1.0, 5.0), (0.0, 0.02), (0.01, 0.30), (-0.05, 0.05)]
    # Try multiple starts
    best = None
    starts = [x0,
              (1.0, 2.5, 0.001, 0.06, 0.0),
              (1.0, 3.0, 0.003, 0.06, 0.0)]
    for s in starts:
        res = minimize(loss, s, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 200, "ftol": 1e-12})
        if best is None or res.fun < best.fun:
            best = res
    # polish with Nelder-Mead
    res = minimize(loss, best.x, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 2000})
    if res.fun < best.fun:
        best = res
    return best


def fit_platform(platform, x0, try_per_seg=True):
    print(f"\n=== {platform} ===")
    segs = load_segments(platform)
    print(f"  {len(segs)} segs")

    results = {}
    # global delta0
    loss = make_loss(segs, use_per_seg=False)
    res = fit_with_bounds(loss, x0)
    print(f"  GLOBAL  RMSE={np.sqrt(res.fun):.6f}  params={res.x}")
    results["global"] = (res.fun, list(res.x))

    if try_per_seg:
        loss = make_loss(segs, use_per_seg=True)
        res = fit_with_bounds(loss, x0)
        print(f"  PERSEG  RMSE={np.sqrt(res.fun):.6f}  params={res.x}")
        results["perseg"] = (res.fun, list(res.x))

    return results


if __name__ == "__main__":
    out = {}
    res = fit_platform("FORD_F_150_LIGHTNING_MK1", x0=(0.86, 3.26, 0.0035, 0.06, 0.00133))
    if "perseg" in res and res["perseg"][0] < res["global"][0]:
        f, p = res["perseg"]
        out["FORD_F_150_LIGHTNING_MK1"] = {
            "use_per_segment_delta0": True, "g": p[0], "L_eff": p[1], "K_us": p[2],
            "tau": p[3], "delta0_fallback": p[4],
        }
    else:
        f, p = res["global"]
        out["FORD_F_150_LIGHTNING_MK1"] = {
            "use_per_segment_delta0": False, "g": p[0], "L_eff": p[1], "K_us": p[2],
            "tau": p[3], "delta0": p[4],
        }

    res = fit_platform("FORD_MUSTANG_MACH_E_MK1", x0=(0.89, 2.22, 0.0015, 0.069, -0.0001))
    if res["perseg"][0] < res["global"][0]:
        f, p = res["perseg"]
        out["FORD_MUSTANG_MACH_E_MK1"] = {
            "use_per_segment_delta0": True, "g": p[0], "L_eff": p[1], "K_us": p[2],
            "tau": p[3], "delta0_fallback": p[4],
        }
    else:
        f, p = res["global"]
        out["FORD_MUSTANG_MACH_E_MK1"] = {
            "use_per_segment_delta0": False, "g": p[0], "L_eff": p[1], "K_us": p[2],
            "tau": p[3], "delta0": p[4],
        }

    res = fit_platform("HYUNDAI_IONIQ_5", x0=(0.94, 2.89, 0.0029, 0.062, 0.0))
    if res["perseg"][0] < res["global"][0]:
        f, p = res["perseg"]
        out["HYUNDAI_IONIQ_5"] = {
            "use_per_segment_delta0": True, "g": p[0], "L_eff": p[1], "K_us": p[2],
            "tau": p[3], "delta0_fallback": p[4],
        }
    else:
        f, p = res["global"]
        out["HYUNDAI_IONIQ_5"] = {
            "use_per_segment_delta0": False, "g": p[0], "L_eff": p[1], "K_us": p[2],
            "tau": p[3], "delta0": p[4],
        }

    out_path = ROOT / "out" / "v3_params.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")
    print(json.dumps(out, indent=2))
