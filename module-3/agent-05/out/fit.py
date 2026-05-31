"""Per-platform fitter: minimise yaw + CTE objective via scipy.

Objective: yaw_rmse_pooled / yaw_baseline + cte_rmse_pooled / cte_baseline
to weight the two KPIs similarly.
"""
from __future__ import annotations
import sys
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))

from _shared.traj_metrics import cte_rmse_segment
from harness import find_sim_csvs, load_segment, SIM_ROOT
from recipe_v1 import predict_with_params, _per_segment_delta0


def collect_platform_data(platform):
    csvs = find_sim_csvs(SIM_ROOT, platform)
    segs = []
    for csv in csvs:
        df = load_segment(csv)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        segs.append(df)
    return segs


def eval_params(segs, p, lam_cte=1.0, lam_yaw=1.0):
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
    yaw_rmse = math.sqrt(sum_sq_yaw / n_yaw) if n_yaw > 0 else float("nan")
    cte_rmse = math.sqrt(sum_sq_cte / n_bins) if n_bins > 0 else float("nan")
    return yaw_rmse, cte_rmse


def fit_platform(platform, use_per_seg_delta0=False, init=None, fix_L_eff=None):
    segs = collect_platform_data(platform)
    print(f"[{platform}] {len(segs)} segments")

    # Parameter vector: [g, L_eff, K_us, tau, delta0_or_fallback]
    if init is None:
        init = [0.88, 2.8, 0.0025, 0.065, 0.0]

    def unpack(x):
        g, L_eff, K_us, tau, d0 = x
        p = {"g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau}
        if use_per_seg_delta0:
            p["use_per_segment_delta0"] = True
            p["delta0_fallback"] = d0
        else:
            p["use_per_segment_delta0"] = False
            p["delta0"] = d0
        if fix_L_eff is not None:
            p["L_eff"] = fix_L_eff
        return p

    # Get baselines for normalisation
    base_p = unpack(init)
    base_yaw, base_cte = eval_params(segs, base_p)
    print(f"  init: yaw={base_yaw:.5f}  cte={base_cte:.3f}")

    def obj(x):
        p = unpack(x)
        # bound checks
        if p["g"] < 0.5 or p["g"] > 1.3: return 1e3
        if p["L_eff"] < 1.5 or p["L_eff"] > 5.0: return 1e3
        if p["K_us"] < -0.005 or p["K_us"] > 0.02: return 1e3
        if p["tau"] < 0.001 or p["tau"] > 0.5: return 1e3
        yaw, cte = eval_params(segs, p)
        if not (np.isfinite(yaw) and np.isfinite(cte)): return 1e3
        # normalised loss
        return yaw / base_yaw + cte / base_cte

    res = minimize(obj, init, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-5, "maxiter": 400, "disp": False})
    p = unpack(res.x)
    yaw, cte = eval_params(segs, p)
    print(f"  fit:  yaw={yaw:.5f}  cte={cte:.3f}")
    print(f"  params: g={p['g']:.4f} L_eff={p['L_eff']:.3f} K_us={p['K_us']:.5f} tau={p['tau']:.4f} d0={res.x[4]:.5f}")
    return p, res.x


if __name__ == "__main__":
    import json
    print("== FORD_MUSTANG_MACH_E_MK1 (per-seg δ₀ ON) ==")
    p_mache, x_mache = fit_platform("FORD_MUSTANG_MACH_E_MK1",
                                     use_per_seg_delta0=True,
                                     init=[0.891, 2.22, 0.00202, 0.069, -0.0001])
    print("== FORD_F_150_LIGHTNING_MK1 (global δ₀) ==")
    p_l, x_l = fit_platform("FORD_F_150_LIGHTNING_MK1",
                             use_per_seg_delta0=False,
                             init=[0.863, 3.26, 0.00350, 0.060, 0.00133])
    print("== HYUNDAI_IONIQ_5 (global δ₀) ==")
    p_h, x_h = fit_platform("HYUNDAI_IONIQ_5",
                             use_per_seg_delta0=False,
                             init=[0.88, 2.6, 0.0025, 0.065, 0.0])

    out = {
        "FORD_MUSTANG_MACH_E_MK1": p_mache,
        "FORD_F_150_LIGHTNING_MK1": p_l,
        "HYUNDAI_IONIQ_5": p_h,
    }
    with open(ROOT / "out" / "fitted_v1.json", "w") as f:
        json.dump(out, f, indent=2)
    print("saved fitted_v1.json")
