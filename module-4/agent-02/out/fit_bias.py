"""Fit per-platform additive yaw-rate bias correction on top of refit V1.

Tries: a single scalar yaw-rate offset per platform that minimises pooled yaw RMSE.
Then test CTE impact.
"""
from __future__ import annotations
import sys, json, time, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "final-model"))

from _shared.traj_metrics import cte_rmse_segment
import predict as final_predict_mod

SEG_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def collect(platform):
    """For each segment: cache (t, v, mask, truth, yr_pred_finalmodel)."""
    print(f"  collecting {platform}...", flush=True)
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        yr_pred = final_predict_mod.predict(df, platform)["yaw_rate_pred_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        mask = v > 2.0
        segs.append((t, v, truth, yr_pred, mask))
    return segs


def score_with_bias(segs, bias):
    yaw_ss = yaw_n = 0
    cte_ss = cte_n = 0
    for t, v, truth, yr_pred, mask in segs:
        yr = yr_pred + bias
        r = yr[mask] - truth[mask]
        yaw_ss += float(np.dot(r, r)); yaw_n += int(mask.sum())
        ss, nb, _ = cte_rmse_segment(t, v, truth, yr)
        cte_ss += ss; cte_n += nb
    yaw_rmse = math.sqrt(yaw_ss/max(yaw_n,1))
    cte_rmse = math.sqrt(cte_ss/max(cte_n,1))
    return yaw_rmse, cte_rmse


if __name__ == "__main__":
    biases = {}
    for plat in PLATFORMS:
        segs = collect(plat)
        # closed-form: bias = mean(truth - yr_pred) over mask
        sum_d = 0.0; n = 0
        for t, v, truth, yr_pred, mask in segs:
            sum_d += float(np.sum(truth[mask] - yr_pred[mask]))
            n += int(mask.sum())
        bias_yaw = sum_d / max(n, 1)
        print(f"\n{plat}: bias_minimising_yaw_RMSE = {bias_yaw:+.6f}", flush=True)
        # report scores for zero, yaw-optimal, and a sweep
        for b in [0.0, bias_yaw, 0.5*bias_yaw, 2*bias_yaw, -bias_yaw]:
            y, c = score_with_bias(segs, b)
            print(f"  bias={b:+.6f}  yaw={y:.6f}  CTE={c:.4f}", flush=True)
        biases[plat] = bias_yaw

    out_path = ROOT / "out" / "yaw_biases.json"
    out_path.write_text(json.dumps(biases, indent=2))
    print(f"\nWrote {out_path}")
    print(json.dumps(biases, indent=2))
