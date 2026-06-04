"""Full pooled bench: load every sim.csv, run a predict function, score yaw + CTE RMSE.

Scores both yaw-rate RMSE (pooled, v>2 m/s mask) and CTE RMSE (pooled
distance-resampled). Compares V0 (passthrough), V1 (textbook), V2 (refit params).
"""
from __future__ import annotations

import sys
import json
import math
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))

from _shared.traj_metrics import cte_rmse_segment
from v1_baseline import predict_v1, PLATFORM_PARAMS_V1

SEG_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]


def per_seg_delta0(df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def predict_v1_with_params(sim_df, platform, params):
    """V1 shape but with custom params dict (same keys as PLATFORM_PARAMS_V1)."""
    if platform not in params:
        return sim_df["yaw_rate_pred_rads"].to_numpy()
    p = params[platform]
    if p.get("use_per_segment_delta0", False):
        delta0 = per_seg_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
    else:
        delta0 = p["delta0"]
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict_v0(sim_df, platform):
    return sim_df["yaw_rate_pred_rads"].to_numpy()


def predict_v1_textbook(sim_df, platform):
    return predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()


def load_segments(platform):
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    out = []
    for p in paths:
        df = pd.read_csv(p)
        out.append((p, df))
    return out


def score_model(predict_fn, label, params=None):
    print(f"\n=== {label} ===")
    yaw_sumsq_total = 0.0
    yaw_n_total = 0
    cte_sumsq_total = 0.0
    cte_n_total = 0
    per_plat = defaultdict(lambda: {"yaw_ss": 0.0, "yaw_n": 0, "cte_ss": 0.0, "cte_n": 0})
    for plat in PLATFORMS:
        segs = load_segments(plat)
        for path, df in segs:
            if "yaw_rate_meas_rads" not in df.columns:
                continue  # tesla
            if params is None:
                yr_pred = predict_fn(df, plat)
            else:
                yr_pred = predict_fn(df, plat, params)
            truth = df["yaw_rate_meas_rads"].to_numpy()
            v = df["v_mps"].to_numpy()
            t = df["t_s"].to_numpy()
            mask = v > 2.0
            r = yr_pred[mask] - truth[mask]
            yaw_sumsq_total += float(np.sum(r * r))
            yaw_n_total += int(mask.sum())
            per_plat[plat]["yaw_ss"] += float(np.sum(r * r))
            per_plat[plat]["yaw_n"] += int(mask.sum())

            # CTE
            ss, nb, _ = cte_rmse_segment(t, v, truth, yr_pred)
            cte_sumsq_total += ss
            cte_n_total += nb
            per_plat[plat]["cte_ss"] += ss
            per_plat[plat]["cte_n"] += nb
    yaw_rmse = math.sqrt(yaw_sumsq_total / max(yaw_n_total, 1))
    cte_rmse = math.sqrt(cte_sumsq_total / max(cte_n_total, 1))
    print(f"  POOLED  yaw RMSE: {yaw_rmse:.6f}  CTE RMSE: {cte_rmse:.4f}")
    for plat, st in per_plat.items():
        y = math.sqrt(st["yaw_ss"] / max(st["yaw_n"], 1)) if st["yaw_n"] else float("nan")
        c = math.sqrt(st["cte_ss"] / max(st["cte_n"], 1)) if st["cte_n"] else float("nan")
        print(f"  {plat:30s}  yaw={y:.6f}  CTE={c:.4f}  (n_yaw={st['yaw_n']}, n_cte={st['cte_n']})")
    return yaw_rmse, cte_rmse


if __name__ == "__main__":
    score_model(predict_v0, "V0 baseline (passthrough)")
    score_model(predict_v1_textbook, "V1 baseline (textbook params)")

    # V2: refit params from fit_v2.py output — but Mach-E params are degenerate
    # (g, L, K_us all collapsed near zero). Use textbook for Mach-E instead.
    v2_params = json.loads((ROOT / "out" / "v2_params.json").read_text())
    # Sanity: if g < 0.01 something went wrong with fit — replace with textbook.
    fixed_params = {}
    for k, p in v2_params.items():
        if p.get("g", 1.0) < 0.01:
            print(f"  [warn] {k} fit collapsed (g={p['g']:.2e}); using V1 textbook")
            fixed_params[k] = PLATFORM_PARAMS_V1[k]
        else:
            fixed_params[k] = p
    score_model(predict_v1_with_params, "V2 (refit + degenerate guard)", params=fixed_params)
