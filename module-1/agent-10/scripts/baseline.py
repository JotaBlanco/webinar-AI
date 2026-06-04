"""Compute V0 baseline RMSE per platform from sim/ truth segments."""
import glob
import os
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/data/sim/segments"

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]


def load_segment(path):
    df = pd.read_csv(path)
    return df


def yaw_rmse(df):
    if "yaw_rate_meas_rads" not in df or "yaw_rate_pred_rads" not in df:
        return None
    e = df["yaw_rate_pred_rads"].values - df["yaw_rate_meas_rads"].values
    return float(np.sqrt(np.mean(e ** 2)))


for plat in PLATFORMS:
    files = sorted(glob.glob(os.path.join(ROOT, plat, "**", "sim.csv"), recursive=True))
    if not files:
        print(f"{plat}: no files")
        continue
    errs = []
    n_pts = 0
    for f in files:
        try:
            df = load_segment(f)
            r = yaw_rmse(df)
            if r is None:
                continue
            errs.append((r, len(df)))
            n_pts += len(df)
        except Exception as e:
            pass
    if not errs:
        print(f"{plat}: no truth")
        continue
    # pooled RMSE
    sse = sum(r * r * n for r, n in errs)
    rmse = float(np.sqrt(sse / n_pts))
    print(f"{plat}: V0 yaw-rate RMSE = {rmse:.5f} rad/s   ({len(errs)} segs, {n_pts} pts)")
