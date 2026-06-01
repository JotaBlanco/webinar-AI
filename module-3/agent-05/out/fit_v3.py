"""Fit v3: per-platform 5-param fit (g, L_eff, K_us, tau, delta0_fallback)
with sane bounds and multiple starts. Per-segment δ₀ ON for all platforms
(approach-menu recipe). Minimises (yaw/yaw_base + cte/cte_base)."""
from __future__ import annotations
import sys
import math
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))
from _shared.traj_metrics import cte_rmse_segment
from harness import find_sim_csvs, load_segment, SIM_ROOT
from recipe_v1 import predict_with_params

# Approximate published wheelbases (m) — used as priors for L_eff init only.
WHEELBASE_PRIOR = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.708,
    "HYUNDAI_IONIQ_5": 3.000,
}

# Bounds for fit parameters
BOUNDS = {
    "g":     (0.70, 1.20),
    "L_eff": (2.00, 4.20),
    "K_us":  (-0.003, 0.015),
    "tau":   (0.005, 0.250),
    "d0":    (-0.020, 0.020),
}


def collect_platform_data(platform, max_seg=None, stride=1):
    csvs = find_sim_csvs(SIM_ROOT, platform)
    if stride > 1:
        csvs = csvs[::stride]
    if max_seg:
        csvs = csvs[:max_seg]
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


def make_unpacker(use_per_seg):
    def unpack(x):
        g, L_eff, K_us, tau, d0 = x
        p = {"g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau}
        if use_per_seg:
            p["use_per_segment_delta0"] = True
            p["delta0_fallback"] = d0
        else:
            p["use_per_segment_delta0"] = False
            p["delta0"] = d0
        return p
    return unpack


def fit_platform(platform, use_per_seg=True, starts=None, fit_stride=1):
    segs = collect_platform_data(platform, stride=fit_stride)
    L_prior = WHEELBASE_PRIOR[platform]
    print(f"[{platform}] {len(segs)} segments, L_prior={L_prior}")
    unpack = make_unpacker(use_per_seg)

    # Baselines for normalisation: V0-as-is
    v0_yaw, v0_cte = eval_params(segs, {"g": 1.0, "L_eff": L_prior, "K_us": 0.0,
                                          "tau": 0.001,
                                          "use_per_segment_delta0": False,
                                          "delta0": 0.0})
    print(f"  V0-mimic: yaw={v0_yaw:.5f}  cte={v0_cte:.3f}")

    if starts is None:
        starts = [
            [0.88, L_prior, 0.003, 0.06, 0.0],
            [0.90, L_prior * 0.92, 0.002, 0.08, 0.0],
            [0.85, L_prior * 1.08, 0.004, 0.04, 0.0],
        ]

    def obj(x):
        # Box bounds (soft)
        for val, (lo, hi) in zip(x, [BOUNDS["g"], BOUNDS["L_eff"], BOUNDS["K_us"],
                                       BOUNDS["tau"], BOUNDS["d0"]]):
            if val < lo or val > hi:
                return 1e6
        p = unpack(x)
        yaw, cte = eval_params(segs, p)
        if not (np.isfinite(yaw) and np.isfinite(cte)):
            return 1e6
        return yaw / v0_yaw + cte / v0_cte

    best = None
    for init in starts:
        res = minimize(obj, init, method="Nelder-Mead",
                       options={"xatol": 1e-4, "fatol": 1e-4,
                                "maxiter": 300, "disp": False})
        p = unpack(res.x)
        yaw, cte = eval_params(segs, p)
        print(f"  start {init} -> yaw={yaw:.5f} cte={cte:.3f} obj={res.fun:.5f}")
        if best is None or res.fun < best[0]:
            best = (res.fun, p, res.x, yaw, cte)
    obj_v, p, x, yaw, cte = best
    print(f"  BEST: yaw={yaw:.5f}  cte={cte:.3f}  obj={obj_v:.5f}")
    print(f"  params: g={p['g']:.4f} L_eff={p['L_eff']:.3f} "
          f"K_us={p['K_us']:.5f} tau={p['tau']:.4f} d0={x[4]:.5f}")
    return p, yaw, cte


if __name__ == "__main__":
    results = {}
    final = {}
    # Per-platform fit stride to keep wall time under control. Ioniq has 800 segs.
    strides = {"FORD_MUSTANG_MACH_E_MK1": 2,
                "FORD_F_150_LIGHTNING_MK1": 2,
                "HYUNDAI_IONIQ_5": 4}
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]:
        st = strides[plat]
        print(f"\n=== {plat} (per-seg δ₀ ON, fit_stride={st}) ===", flush=True)
        p_on, y_on, c_on = fit_platform(plat, use_per_seg=True, fit_stride=st)
        print(f"\n=== {plat} (global δ₀, fit_stride={st}) ===", flush=True)
        p_off, y_off, c_off = fit_platform(plat, use_per_seg=False, fit_stride=st)
        # Pick by combined normalised score
        # Use the OFF baselines for normalisation (same eval set)
        score_on = y_on / 0.02 + c_on / 200.0
        score_off = y_off / 0.02 + c_off / 200.0
        chosen = p_on if score_on <= score_off else p_off
        chosen_lbl = "ON" if score_on <= score_off else "OFF"
        print(f"\n  >> CHOSE per-seg={chosen_lbl}  on=({y_on:.5f},{c_on:.2f})  off=({y_off:.5f},{c_off:.2f})")
        final[plat] = chosen
        results[plat] = {"on": (p_on, y_on, c_on), "off": (p_off, y_off, c_off),
                          "chosen": chosen_lbl}

    with open(ROOT / "out" / "fitted_v3.json", "w") as f:
        json.dump(final, f, indent=2)
    print("\nSaved fitted_v3.json")
