"""Look at the residual structure of the understeer model."""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-09")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment

SIM_ROOT = ROOT / "data" / "sim" / "segments"

L_BY_PLATFORM = {
    "TESLA_MODEL_3":              2.875,
    "FORD_MUSTANG_MACH_E_MK1":    2.984,
    "FORD_F_150_LIGHTNING_MK1":   3.70,
    "HYUNDAI_IONIQ_5":            3.00,
}

# From fit
COEFFS = {
    "FORD_MUSTANG_MACH_E_MK1": {"K_us": 0.002635, "scale": 1.1831},
    "FORD_F_150_LIGHTNING_MK1": {"K_us": 0.003440, "scale": 0.9608},
    "HYUNDAI_IONIQ_5": {"K_us": 0.003522, "scale": 0.9719},
}


def load_segment(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "yaw_rate_meas_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
    return df


def analyse(platform):
    L = L_BY_PLATFORM[platform]
    K_us = COEFFS[platform]["K_us"]
    scale = COEFFS[platform]["scale"]
    seg_biases = []
    seg_yaw_rmses = []
    seg_lens = []
    seg_v_means = []
    seg_delta_means = []
    paths = sorted((SIM_ROOT / platform).rglob("sim.csv"))
    for p in paths:
        df = load_segment(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        yr = df["yaw_rate_meas_rads"].to_numpy()
        mask = np.isfinite(yr) & np.isfinite(v) & np.isfinite(d) & (v > 1.0)
        if mask.sum() < 50:
            continue
        v_ = v[mask]; d_ = d[mask]; yr_ = yr[mask]
        yp = v_ * d_ * scale / (L + K_us * v_ * v_)
        resid = yr_ - yp
        seg_biases.append(np.mean(resid))
        seg_yaw_rmses.append(math.sqrt(np.mean(resid ** 2)))
        seg_lens.append(len(yr_))
        seg_v_means.append(np.mean(v_))
        seg_delta_means.append(np.mean(d_))
    b = np.array(seg_biases)
    print(f"  segments: {len(b)}")
    print(f"  bias rad/s: mean={b.mean():.5f} std={b.std():.5f} median={np.median(b):.5f}")
    print(f"  abs bias mean: {np.mean(np.abs(b)):.5f}")
    print(f"  per-seg yaw RMSE: median={np.median(seg_yaw_rmses):.5f} 90th={np.percentile(seg_yaw_rmses, 90):.5f}")
    # what's the bias correlated with?
    sv = np.array(seg_v_means)
    sd = np.array(seg_delta_means)
    if len(b) > 3:
        print(f"  corr(bias, mean_v): {np.corrcoef(b, sv)[0,1]:.3f}")
        print(f"  corr(bias, mean_delta): {np.corrcoef(b, sd)[0,1]:.3f}")


for plat in COEFFS:
    print(f"=== {plat} ===")
    analyse(plat)
