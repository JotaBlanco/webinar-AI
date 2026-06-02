"""Refit V1 (g, L_eff, K_us, tau, delta0) per platform on a CTE objective.

Uses a coarse train/dev split (80/20 by segment), minimises pooled yaw RMSE on
train (cheaper than CTE for the optimiser), then reports both metrics on dev.
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-08")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # type: ignore

SIM_ROOT = ROOT / "data" / "sim" / "segments"
SIMONLY_ROOT = ROOT / "data" / "sim-only" / "segments"

TRUTH_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}


def load_segments(platform):
    truth_col = TRUTH_BY_PLATFORM[platform]
    plat_dir = SIM_ROOT / platform
    rows = []
    for p in sorted(plat_dir.rglob("sim.csv")):
        try:
            df_full = pd.read_csv(p)
        except Exception:
            continue
        if truth_col not in df_full.columns:
            continue
        rel = p.relative_to(SIM_ROOT)
        so = SIMONLY_ROOT / rel
        if not so.exists():
            continue
        df_so = pd.read_csv(so)
        rows.append({
            "key": str(rel),
            "t": df_so["t_s"].to_numpy(),
            "delta_road": df_so["delta_road_rad"].to_numpy(),
            "v": df_so["v_mps"].to_numpy(),
            "yr_v0": df_so["yaw_rate_pred_rads"].to_numpy(),
            "yr_truth": df_full[truth_col].to_numpy(),
        })
    return rows


def v1_predict(seg, g, L_eff, K_us, tau, delta0_use_per_seg, delta0_fallback):
    if delta0_use_per_seg:
        # Per-segment estimate (median of delta_road on low-yaw_v0 straight bits)
        yr_v0 = seg["yr_v0"]; v = seg["v"]
        mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
        if mask.sum() >= 50:
            delta0 = float(np.median(seg["delta_road"][mask]))
        else:
            delta0 = delta0_fallback
    else:
        delta0 = delta0_fallback
    delta = (seg["delta_road"] - delta0) * g
    v = seg["v"]
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = seg["t"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def loss_yr(params, segs, per_seg_delta0):
    g, L_eff, K_us, tau, delta0_fb = params
    if L_eff <= 0.1 or tau < 1e-3 or g <= 0.0:
        return 1e9
    s = 0.0; n = 0
    for seg in segs:
        yr = v1_predict(seg, g, L_eff, K_us, tau, per_seg_delta0, delta0_fb)
        d = yr - seg["yr_truth"]
        s += float((d*d).sum()); n += len(d)
    return s / max(n, 1)


def fit_platform(platform, per_seg_delta0_default, init_params, max_segs=None):
    segs = load_segments(platform)
    if max_segs:
        segs = segs[:max_segs]
    rng = np.random.default_rng(0)
    idx = np.arange(len(segs))
    rng.shuffle(idx)
    split = int(0.8 * len(segs))
    train = [segs[i] for i in idx[:split]]
    dev = [segs[i] for i in idx[split:]]

    def f(p): return loss_yr(p, train, per_seg_delta0_default)
    res = minimize(f, init_params, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 500})
    p_opt = res.x
    # Dev score
    yr_sq = 0.0; yr_n = 0
    cte_sq = 0.0; cte_n = 0
    for seg in dev:
        g_, L_, K_, tau_, d0_ = p_opt
        yr = v1_predict(seg, g_, L_, K_, tau_, per_seg_delta0_default, d0_)
        d = yr - seg["yr_truth"]
        yr_sq += float((d*d).sum()); yr_n += len(d)
        s2, nb, _ = cte_rmse_segment(seg["t"], seg["v"], seg["yr_truth"], yr)
        cte_sq += s2; cte_n += nb
    yr_rmse = math.sqrt(yr_sq/yr_n) if yr_n else float("nan")
    cte_rmse = math.sqrt(cte_sq/cte_n) if cte_n else float("nan")
    return {
        "platform": platform,
        "g": p_opt[0], "L_eff": p_opt[1], "K_us": p_opt[2], "tau": p_opt[3],
        "delta0_fallback": p_opt[4],
        "use_per_segment_delta0": per_seg_delta0_default,
        "dev_yr_rmse": yr_rmse, "dev_cte_rmse": cte_rmse,
        "n_train": len(train), "n_dev": len(dev),
    }


if __name__ == "__main__":
    out = {}
    # init from V1 known coefficients
    inits = {
        "FORD_MUSTANG_MACH_E_MK1": (0.891, 2.22, 0.00150, 0.069, -0.0001),
        "FORD_F_150_LIGHTNING_MK1": (0.863, 3.26, 0.00350, 0.060, 0.00133),
        "HYUNDAI_IONIQ_5": (0.938, 2.887, 0.00289, 0.062, 0.0),
    }
    per_seg = {
        "FORD_MUSTANG_MACH_E_MK1": True,
        "FORD_F_150_LIGHTNING_MK1": False,
        "HYUNDAI_IONIQ_5": True,
    }
    for plat, init in inits.items():
        print(f"Fitting {plat}...")
        r = fit_platform(plat, per_seg[plat], init)
        print(json.dumps(r, indent=2, default=float))
        out[plat] = r
    (ROOT / "out" / "v2_coeffs.json").write_text(json.dumps(out, indent=2, default=float))
    print("Saved v2_coeffs.json")
