"""Diagnose V1 residuals across platforms — find biases and structural patterns.
Build feature matrix for residual learner.
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-09")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "out"))

from v1_baseline import predict_v1
from harness import list_segments, PLATFORMS_FIT, ALLOWED_COLS


def collect(platform, max_segs=None):
    pairs = list_segments(platform)
    if max_segs:
        pairs = pairs[:max_segs]
    rows = []
    for sp_only, sp_full in pairs:
        sim_df = pd.read_csv(sp_only)
        if not all(c in sim_df.columns for c in ALLOWED_COLS):
            continue
        sim_df = sim_df[ALLOWED_COLS].copy()
        full = pd.read_csv(sp_full)
        if "yaw_rate_meas_rads" not in full.columns:
            continue
        yr_truth = full["yaw_rate_meas_rads"].to_numpy()
        out = predict_v1(sim_df, platform)
        yr_v1 = out["yaw_rate_pred_rads"].to_numpy()
        if len(yr_truth) != len(yr_v1):
            continue
        resid = yr_truth - yr_v1
        rows.append({
            "seg": str(sp_only),
            "platform": platform,
            "yr_truth": yr_truth,
            "yr_v1": yr_v1,
            "resid": resid,
            "v_mps": sim_df["v_mps"].to_numpy(),
            "delta_road_rad": sim_df["delta_road_rad"].to_numpy(),
            "a_long": sim_df["a_long_mps2"].to_numpy(),
            "t_s": sim_df["t_s"].to_numpy(),
        })
    return rows


if __name__ == "__main__":
    summary = {}
    for plat in PLATFORMS_FIT:
        rows = collect(plat, max_segs=80)
        resid_all = np.concatenate([r["resid"] for r in rows])
        v_all = np.concatenate([r["v_mps"] for r in rows])
        # bias mask: v > 5 (excluding low-speed noise)
        mask = v_all > 5
        summary[plat] = {
            "n_samples": len(resid_all),
            "n_segments": len(rows),
            "resid_mean": float(np.mean(resid_all)),
            "resid_std": float(np.std(resid_all)),
            "resid_mean_v5": float(np.mean(resid_all[mask])),
            "resid_std_v5": float(np.std(resid_all[mask])),
        }
    print(json.dumps(summary, indent=2))
