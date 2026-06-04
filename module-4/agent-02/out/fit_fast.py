"""Fast fit of V1 shape per platform.

Caches segment data as numpy arrays once. Single L-BFGS-B per (platform, mode).
Unbuffered prints.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
SEG_ROOT = ROOT / "data" / "sim" / "segments"


def per_seg_delta0_arr(delta, v, yr_v0, fallback=0.0):
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if int(mask.sum()) < 50:
        return fallback
    return float(np.median(delta[mask]))


def predict_yr_arr(delta, v, dt, g, L_eff, K_us, tau, delta0):
    d = (delta - delta0) * g
    yr_ss = v * d / (L_eff + K_us * v * v)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def cache_platform(platform):
    print(f"caching {platform}...", flush=True)
    t0 = time.time()
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    segs = []
    for p in paths:
        df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        t = df["t_s"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        v = df["v_mps"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        d0_perseg = per_seg_delta0_arr(delta, v, yr_v0)
        mask = v > 2.0
        segs.append((delta, v, dt, truth, mask, d0_perseg))
    print(f"  {len(segs)} segs cached in {time.time()-t0:.1f}s", flush=True)
    return segs


def loss_fn(segs, use_perseg):
    def f(params):
        g, L_eff, K_us, tau, d0 = params
        if L_eff <= 0 or tau <= 0 or g <= 0:
            return 1e6
        ss = 0.0
        n = 0
        for delta, v, dt, truth, mask, d0_perseg in segs:
            d0_use = d0_perseg if use_perseg else d0
            yr = predict_yr_arr(delta, v, dt, g, L_eff, K_us, tau, d0_use)
            r = yr[mask] - truth[mask]
            ss += float(np.dot(r, r))
            n += int(mask.sum())
        return ss / max(n, 1)
    return f


def fit(platform, x0):
    segs = cache_platform(platform)
    bounds = [(0.5, 1.5), (1.0, 5.0), (0.0, 0.02), (0.01, 0.30), (-0.05, 0.05)]
    results = {}
    for mode in ("global", "perseg"):
        use_perseg = (mode == "perseg")
        f = loss_fn(segs, use_perseg)
        t0 = time.time()
        init = f(x0)
        print(f"  [{platform}/{mode}] init RMSE={np.sqrt(init):.6f}", flush=True)
        res = minimize(f, x0, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 100, "ftol": 1e-12, "gtol": 1e-10})
        print(f"  [{platform}/{mode}] L-BFGS-B RMSE={np.sqrt(res.fun):.6f}  in {time.time()-t0:.1f}s  x={res.x}", flush=True)
        results[mode] = (res.fun, list(res.x))
    return results


if __name__ == "__main__":
    out = {}
    plats = [
        ("FORD_F_150_LIGHTNING_MK1", (0.86, 3.26, 0.0035, 0.06, 0.00133)),
        ("FORD_MUSTANG_MACH_E_MK1", (0.89, 2.22, 0.0015, 0.069, -0.0001)),
        ("HYUNDAI_IONIQ_5", (0.94, 2.89, 0.0029, 0.062, 0.0)),
    ]
    for platform, x0 in plats:
        res = fit(platform, x0)
        # pick best
        best_mode = min(res, key=lambda m: res[m][0])
        f, p = res[best_mode]
        print(f"  -> {platform} chooses {best_mode} (RMSE={np.sqrt(f):.6f})", flush=True)
        if best_mode == "perseg":
            out[platform] = {
                "use_per_segment_delta0": True,
                "g": p[0], "L_eff": p[1], "K_us": p[2], "tau": p[3],
                "delta0_fallback": p[4],
            }
        else:
            out[platform] = {
                "use_per_segment_delta0": False,
                "g": p[0], "L_eff": p[1], "K_us": p[2], "tau": p[3],
                "delta0": p[4],
            }

    out_path = ROOT / "out" / "v3_params.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}", flush=True)
    print(json.dumps(out, indent=2), flush=True)
