"""Per-platform coefficient fit against pooled yaw RMSE.

Uses data/sim/ for truth (OFFLINE fitting only). The shipped predict.py reads
only allowlist columns from data/sim-only/.
"""
import sys
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "score-model"))

ROOT = REPO / "data" / "sim" / "segments"


def load_platform(plat):
    segs = []
    for p in sorted(ROOT.glob(f"{plat}/**/sim.csv")):
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        segs.append(df)
    return segs


def per_seg_delta0(df, fallback, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def run_model(df, p, use_per_seg):
    if use_per_seg:
        d0 = per_seg_delta0(df, fallback=p["delta0_fallback"])
    else:
        d0 = p["delta0"]
    delta_road = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    t = df["t_s"].to_numpy()
    delta_eff = (delta_road - d0) * p["g"]
    yr_ss = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)
    tau = p["tau"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def yaw_objective(x, segs, use_per_seg, L_eff_fixed=None, v_min=2.0):
    if L_eff_fixed is not None:
        g, K_us, tau, d0 = x
        L_eff = L_eff_fixed
    else:
        g, L_eff, K_us, tau, d0 = x
    if L_eff <= 0.5 or tau < 1e-4 or K_us < -0.01 or g < 0.5 or g > 1.5:
        return 1e6
    p = {"g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau}
    if use_per_seg:
        p["delta0_fallback"] = d0
    else:
        p["delta0"] = d0
    sum_sq = 0.0
    n = 0
    for df in segs:
        try:
            yr_pred = run_model(df, p, use_per_seg)
        except Exception:
            return 1e6
        truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > v_min
        r = yr_pred[mask] - truth[mask]
        sum_sq += float(np.sum(r * r))
        n += int(mask.sum())
    return math.sqrt(sum_sq / max(n, 1))


# L_eff pinned to platform wheelbase to break the g ↔ L_eff scale-invariance.
PLATFORMS = {
    "FORD_F_150_LIGHTNING_MK1": {"use_per_seg": False, "L_eff_fixed": 3.705,
                                  "x0": [0.95, 0.00350, 0.060, 0.00133]},
    "FORD_MUSTANG_MACH_E_MK1":  {"use_per_seg": True,  "L_eff_fixed": 2.984,
                                  "x0": [0.95, 0.00150, 0.069, -0.0001]},
    "HYUNDAI_IONIQ_5":          {"use_per_seg": True,  "L_eff_fixed": 3.00,
                                  "x0": [0.95, 0.00289, 0.062, 0.0]},
}


def main():
    results = {}
    for plat, info in PLATFORMS.items():
        segs = load_platform(plat)
        print(f"\n{plat}: {len(segs)} segments (L_eff pinned to {info['L_eff_fixed']})", flush=True)
        x0 = info["x0"]
        use_per_seg = info["use_per_seg"]
        L_eff_fixed = info["L_eff_fixed"]
        pre = yaw_objective(x0, segs, use_per_seg, L_eff_fixed)
        print(f"  pre-fit yaw rmse: {pre:.6f}", flush=True)
        res = minimize(yaw_objective, x0, args=(segs, use_per_seg, L_eff_fixed),
                       method="Nelder-Mead",
                       options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 800})
        print(f"  post-fit yaw rmse: {res.fun:.6f}", flush=True)
        g, K_us, tau, d0 = res.x
        L_eff = L_eff_fixed
        print(f"  g={g:.4f} L_eff={L_eff:.4f} K_us={K_us:.5f} tau={tau:.4f} d0={d0:.5f}",
              flush=True)
        entry = {"use_per_segment_delta0": use_per_seg, "g": float(g),
                 "L_eff": float(L_eff), "K_us": float(K_us),
                 "tau": float(max(tau, 1e-4))}
        if use_per_seg:
            entry["delta0_fallback"] = float(d0)
        else:
            entry["delta0"] = float(d0)
        results[plat] = entry

    out_path = REPO / "out" / "fitted_coeffs.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}", flush=True)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
