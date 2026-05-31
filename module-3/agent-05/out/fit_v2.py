"""Fit v2: L_eff fixed to wheelbase, per-segment δ₀ for all platforms (data shows wide bias spread on all 3)."""
from __future__ import annotations
import sys
from pathlib import Path
import math
import numpy as np
import json
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))
from _shared.traj_metrics import cte_rmse_segment
from harness import find_sim_csvs, load_segment, SIM_ROOT
from recipe_v1 import predict_with_params

# Approximate wheelbase priors (m)
WHEELBASE_PRIOR = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.708,
    "HYUNDAI_IONIQ_5": 3.000,
}


def collect_platform_data(platform):
    csvs = find_sim_csvs(SIM_ROOT, platform)
    segs = []
    for csv in csvs:
        df = load_segment(csv)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        segs.append(df)
    return segs


def eval_params(segs, p):
    sum_sq_yaw = 0.0
    n_yaw = 0
    sum_sq_cte = 0.0
    n_bins = 0
    for df in segs:
        truth = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        pred_df = predict_with_params(df, None, p)
        pred = pred_df["yaw_rate_pred_rads"].to_numpy()
        err = pred - truth
        sum_sq_yaw += float((err * err).sum())
        n_yaw += int(len(err))
        ss, nb, _ = cte_rmse_segment(t, v, truth, pred)
        sum_sq_cte += ss
        n_bins += nb
    yaw = math.sqrt(sum_sq_yaw / n_yaw) if n_yaw > 0 else float("nan")
    cte = math.sqrt(sum_sq_cte / n_bins) if n_bins > 0 else float("nan")
    return yaw, cte


def fit_platform(platform, use_per_seg_delta0, init=None):
    segs = collect_platform_data(platform)
    L_fixed = WHEELBASE_PRIOR[platform]
    print(f"[{platform}] {len(segs)} segments, L_fixed={L_fixed}")
    if init is None:
        init = [0.88, 0.0025, 0.065, 0.0]  # g, K_us, tau, d0

    def unpack(x):
        g, K_us, tau, d0 = x
        p = {"g": g, "L_eff": L_fixed, "K_us": K_us, "tau": tau}
        if use_per_seg_delta0:
            p["use_per_segment_delta0"] = True
            p["delta0_fallback"] = d0
        else:
            p["use_per_segment_delta0"] = False
            p["delta0"] = d0
        return p

    base_yaw, base_cte = eval_params(segs, unpack(init))
    print(f"  init: yaw={base_yaw:.5f}  cte={base_cte:.3f}")

    def obj(x):
        if x[0] < 0.6 or x[0] > 1.2: return 1e3
        if x[1] < -0.005 or x[1] > 0.02: return 1e3
        if x[2] < 0.001 or x[2] > 0.3: return 1e3
        if abs(x[3]) > 0.05: return 1e3
        p = unpack(x)
        yaw, cte = eval_params(segs, p)
        if not (np.isfinite(yaw) and np.isfinite(cte)): return 1e3
        return yaw / base_yaw + cte / base_cte

    res = minimize(obj, init, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-5, "maxiter": 600, "disp": False})
    p = unpack(res.x)
    yaw, cte = eval_params(segs, p)
    print(f"  fit:  yaw={yaw:.5f}  cte={cte:.3f}")
    print(f"  params: g={p['g']:.4f} L_eff={p['L_eff']:.3f} K_us={p['K_us']:.5f} tau={p['tau']:.4f} d0={res.x[3]:.5f}")
    return p


if __name__ == "__main__":
    results = {}
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]:
        # Try both with and without per-seg, pick the better one.
        print(f"\n== {plat} per-seg ON ==")
        p_on = fit_platform(plat, use_per_seg_delta0=True)
        y_on, c_on = eval_params(collect_platform_data(plat), p_on)
        print(f"\n== {plat} per-seg OFF ==")
        p_off = fit_platform(plat, use_per_seg_delta0=False)
        y_off, c_off = eval_params(collect_platform_data(plat), p_off)
        # Pick based on combined score (yaw+cte weighted)
        score_on = y_on + c_on / 200.0
        score_off = y_off + c_off / 200.0
        print(f"  >> ON score={score_on:.5f}  OFF score={score_off:.5f}")
        results[plat] = p_on if score_on <= score_off else p_off
        print(f"  >> CHOSE: {'ON' if score_on <= score_off else 'OFF'}")

    with open(ROOT / "out" / "fitted_v2.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved fitted_v2.json")
