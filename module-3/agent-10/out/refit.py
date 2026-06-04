"""Quick per-platform refit of {g, L_eff, K_us, tau, delta0_fallback}
against pooled yaw-rate RMSE on the segments we have (with truth).

Uses input-only per-segment delta0 for Mach-E/IONIQ-5 (legal),
single global delta0 for Lightning. Scipy.optimize.minimize, Nelder-Mead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]


def _per_segment_delta0(df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return float(fallback)
    return float(df.loc[mask, "delta_road_rad"].median())


def predict_one(df, p, use_seg_delta0):
    if use_seg_delta0:
        delta0 = _per_segment_delta0(df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta = (df["delta_road_rad"].to_numpy(dtype=float) - delta0) * p["g"]
    v = df["v_mps"].to_numpy(dtype=float)
    t = df["t_s"].to_numpy(dtype=float)
    denom = p["L_eff"] + p["K_us"] * v * v
    yr_ss = v * delta / denom
    dt = np.diff(t, prepend=t[0])
    tau = p["tau"]
    alpha = dt / (tau + dt) if tau > 0 else np.ones_like(dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def load_segments(platform):
    root = ROOT / "data" / "sim" / "segments" / platform
    segs = []
    for p in sorted(root.glob("**/sim.csv")):
        df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps",
                                     "yaw_rate_pred_rads", "yaw_rate_meas_rads"])
        if len(df) < 100:
            continue
        segs.append(df)
    return segs


def pooled_yaw_rmse(theta, segs, use_seg_delta0, layout):
    """layout: list of names in order matching theta."""
    p = dict(zip(layout, theta))
    # provide both keys for predict_one
    if "delta0" not in p:
        p["delta0"] = 0.0
    if "delta0_fallback" not in p:
        p["delta0_fallback"] = 0.0
    sq_sum = 0.0
    n = 0
    for df in segs:
        try:
            yr_pred = predict_one(df, p, use_seg_delta0)
        except Exception:
            return 1e9
        yr_truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        mask = v > 2.0
        r = yr_pred[mask] - yr_truth[mask]
        sq_sum += float(np.sum(r * r))
        n += int(mask.sum())
    return np.sqrt(sq_sum / n) if n > 0 else 1e9


def fit_platform(platform, use_seg_delta0, init):
    print(f"\n## fitting {platform} (use_seg_delta0={use_seg_delta0})")
    segs = load_segments(platform)
    print(f"   {len(segs)} segments loaded")
    if use_seg_delta0:
        layout = ["g", "L_eff", "K_us", "tau", "delta0_fallback"]
    else:
        layout = ["g", "L_eff", "K_us", "tau", "delta0"]
    x0 = np.array([init[k] for k in layout])
    print(f"   start: {dict(zip(layout, x0))}")
    rmse0 = pooled_yaw_rmse(x0, segs, use_seg_delta0, layout)
    print(f"   start rmse: {rmse0:.6f}")

    # Reasonable bounds via penalty: keep things in sensible ranges
    def loss(theta):
        p = dict(zip(layout, theta))
        if p["g"] <= 0.3 or p["g"] > 1.5: return 1e6
        if p["L_eff"] <= 0.5 or p["L_eff"] > 6.0: return 1e6
        if p["K_us"] < -0.01 or p["K_us"] > 0.02: return 1e6
        if p["tau"] < 0.0 or p["tau"] > 0.5: return 1e6
        return pooled_yaw_rmse(theta, segs, use_seg_delta0, layout)

    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 400, "disp": False})
    fitted = dict(zip(layout, res.x))
    print(f"   fitted: {fitted}")
    print(f"   fitted rmse: {res.fun:.6f}")
    return fitted, float(res.fun), float(rmse0)


def main():
    init = {
        "FORD_F_150_LIGHTNING_MK1": {
            "use_per_segment_delta0": False,
            "delta0": 0.00133, "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
        },
        "FORD_MUSTANG_MACH_E_MK1": {
            "use_per_segment_delta0": True,
            "delta0_fallback": -0.0001, "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
        },
        "HYUNDAI_IONIQ_5": {
            "use_per_segment_delta0": True,
            "delta0_fallback": 0.0, "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
        },
    }
    out = {}
    for plat, p0 in init.items():
        use_seg = p0["use_per_segment_delta0"]
        fitted, rmse_after, rmse_before = fit_platform(plat, use_seg, p0)
        out_p = {"use_per_segment_delta0": use_seg}
        out_p.update(fitted)
        # Keep both delta0 keys for the predict
        if use_seg:
            out_p["delta0_fallback"] = float(out_p.get("delta0_fallback", 0.0))
        else:
            out_p["delta0"] = float(out_p.get("delta0", 0.0))
        out[plat] = {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                     for k, v in out_p.items()}
        print(f"   delta_rmse: {rmse_before:.6f} -> {rmse_after:.6f}")
    out_path = ROOT / "out" / "coeffs_refit.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
