"""Quick diagnostic: per-platform pooled residual stats + sample correlation
between V1 residual and a few candidate features."""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-08")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
SIM_TRUTH = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def load_segment(sim_only_csv):
    rel = sim_only_csv.relative_to(SIM_ONLY)
    truth_csv = SIM_TRUTH / rel
    if not truth_csv.exists():
        return None
    sim_df = pd.read_csv(sim_only_csv)
    truth_df = pd.read_csv(truth_csv, usecols=["yaw_rate_meas_rads"])
    if len(sim_df) != len(truth_df):
        return None
    return sim_df, truth_df["yaw_rate_meas_rads"].to_numpy(dtype=float)


for plat in PLATFORMS:
    resids = []
    yr_v1_all = []
    v_all = []
    seg_means = []
    n = 0
    for sim_csv in (SIM_ONLY / plat).rglob("sim.csv"):
        loaded = load_segment(sim_csv)
        if loaded is None:
            continue
        sim_df, yr_truth = loaded
        yr_v1 = predict_v1(sim_df, plat)["yaw_rate_pred_rads"].to_numpy(float)
        r = yr_truth - yr_v1
        mask = np.isfinite(r)
        if not mask.any():
            continue
        resids.append(r[mask])
        yr_v1_all.append(yr_v1[mask])
        v_all.append(sim_df["v_mps"].to_numpy()[mask])
        seg_means.append(r[mask].mean())
        n += 1
        if n > 300:
            break
    r = np.concatenate(resids)
    yrv1 = np.concatenate(yr_v1_all)
    vall = np.concatenate(v_all)
    sm = np.array(seg_means)
    print(f"{plat}: n_seg={n} samples={len(r)}")
    print(f"  pooled resid: mean={r.mean():.6f}  std={r.std():.6f}")
    print(f"  per-seg resid mean: median={np.median(sm):.6f}  IQR={np.percentile(sm,75)-np.percentile(sm,25):.6f}")
    # Pearson correlations
    def corr(a, b):
        if a.std() < 1e-9 or b.std() < 1e-9:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])
    print(f"  corr(resid, yr_v1)={corr(r, yrv1):.4f}  corr(resid, v)={corr(r, vall):.4f}")
    print(f"  corr(resid, v*yr_v1)={corr(r, vall*yrv1):.4f}")
    print()
