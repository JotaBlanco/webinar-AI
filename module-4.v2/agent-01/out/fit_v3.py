"""V3 — same shape, but fit a YAW BIAS jointly with the other params.

The idea is to absorb the residual yaw bias as a model parameter, then the bias
should fall to zero across all regimes (not just on average).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load_paths(platform):
    root = ROOT / "data" / "sim" / "segments" / platform
    return sorted(root.glob("**/sim.csv"))


def _per_seg_delta0(delta_road, v, yr_v0, fb):
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if int(mask.sum()) < 50:
        return fb
    return float(np.median(delta_road[mask]))


def predict(sim_df, params, use_per_seg):
    delta_road = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    if use_per_seg:
        d0 = _per_seg_delta0(delta_road, v, yr_v0, params["delta0_fallback"])
    else:
        d0 = params["delta0"]
    delta = (delta_road - d0) * params["g"]
    yr_ss = v * delta / (params["L_eff"] + params["K_us"] * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (params["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr + params["yaw_bias"]


def collect(paths, max_seg):
    step = max(1, len(paths) // max_seg)
    paths = paths[::step][:max_seg]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps", "yaw_rate_pred_rads", "yaw_rate_meas_rads"])
        except Exception:
            continue
        if len(df) >= 100:
            segs.append(df)
    return segs


def fit(segs, use_per_seg, init):
    def loss(theta):
        if use_per_seg:
            g, L_eff, K_us, tau, d0_fb, yb = theta
            params = dict(g=g, L_eff=L_eff, K_us=K_us, tau=max(tau, 1e-4),
                          delta0_fallback=d0_fb, yaw_bias=yb)
        else:
            g, L_eff, K_us, tau, d0, yb = theta
            params = dict(g=g, L_eff=L_eff, K_us=K_us, tau=max(tau, 1e-4),
                          delta0=d0, yaw_bias=yb)
        if K_us < 0 or L_eff <= 0.5 or g <= 0:
            return 1e9
        sum_sq = 0.0
        n = 0
        for df in segs:
            yr = predict(df, params, use_per_seg)
            v = df["v_mps"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            mask = v > 2.0
            r = yr[mask] - truth[mask]
            sum_sq += float(np.sum(r * r))
            n += int(mask.sum())
        return np.sqrt(sum_sq / n)

    res = minimize(loss, init, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 1500})
    return res


PLATS = {
    "FORD_F_150_LIGHTNING_MK1": dict(use=True,  init=[0.864, 3.255, 0.00357, 0.057, 0.00144, 0.0]),
    "FORD_MUSTANG_MACH_E_MK1":  dict(use=True,  init=[0.877, 2.26,  0.00172, 0.084, -8e-5,   0.00144]),
    "HYUNDAI_IONIQ_5":          dict(use=True,  init=[0.955, 2.90,  0.00317, 0.050, -2e-4,   0.00074]),
}


def main():
    out = {}
    for plat, cfg in PLATS.items():
        print(f"\n=== {plat} ===")
        segs = collect(load_paths(plat), 100)
        print(f"  {len(segs)} segs")
        res = fit(segs, cfg["use"], cfg["init"])
        keys = ["g", "L_eff", "K_us", "tau",
                "delta0_fallback" if cfg["use"] else "delta0",
                "yaw_bias"]
        params = dict(zip(keys, res.x.tolist()))
        params["use_per_segment_delta0"] = cfg["use"]
        if cfg["use"]:
            params["delta0"] = 0.0
        else:
            params["delta0_fallback"] = 0.0
        print(f"  train yaw RMSE: {res.fun:.6f}")
        print(f"  params: {params}")
        out[plat] = params

    with open(HERE / "v3_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote v3_coeffs.json")


if __name__ == "__main__":
    main()
