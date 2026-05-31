"""Explore residuals per-platform to motivate model variants."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-06")
SEG_ROOT = ROOT / "data" / "sim" / "segments"

# Use only Ford/Hyundai platforms (Tesla has no independent truth)
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

# Sample a subset of segments for analysis speed
rng = np.random.default_rng(0)
all_data = {}
for plat in PLATFORMS:
    paths = sorted((SEG_ROOT / plat).glob("**/sim.csv"))
    pick = rng.choice(len(paths), size=min(60, len(paths)), replace=False)
    dfs = []
    for i in pick:
        df = pd.read_csv(paths[i])
        df = df[df["v_mps"] > 2.0]
        dfs.append(df[["v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads"]])
    cat = pd.concat(dfs, ignore_index=True)
    cat["resid"] = cat["yaw_rate_pred_rads"] - cat["yaw_rate_meas_rads"]
    all_data[plat] = cat

for plat, df in all_data.items():
    print(f"\n=== {plat} (n={len(df)}) ===")
    print(f"  resid mean: {df['resid'].mean():+.5f}, std: {df['resid'].std():.5f}")
    # Linear regression: pred vs truth (find best linear correction)
    # truth ≈ a * pred + b
    pred = df["yaw_rate_pred_rads"].to_numpy()
    truth = df["yaw_rate_meas_rads"].to_numpy()
    A = np.vstack([pred, np.ones_like(pred)]).T
    a, b = np.linalg.lstsq(A, truth, rcond=None)[0]
    print(f"  truth ≈ {a:.6f} * pred + {b:+.6f}")
    yr_cal = a * pred + b
    rmse_v0  = float(np.sqrt(np.mean((pred - truth) ** 2)))
    rmse_cal = float(np.sqrt(np.mean((yr_cal - truth) ** 2)))
    print(f"  RMSE V0: {rmse_v0:.6f}, RMSE linear: {rmse_cal:.6f}")

    # Look at relative-gain by speed bins (does the multiplier scale with v?)
    df["v_bin"] = pd.cut(df["v_mps"], bins=[0, 5, 10, 15, 20, 25, 30, 40], labels=False)
    for vb, sub in df.groupby("v_bin"):
        if len(sub) < 200 or vb is None:
            continue
        p = sub["yaw_rate_pred_rads"].to_numpy()
        t = sub["yaw_rate_meas_rads"].to_numpy()
        if np.sum(p**2) == 0:
            continue
        a_v = float(np.sum(p * t) / np.sum(p * p))  # multiplicative only
        print(f"   v_bin={vb}: n={len(sub)}, gain={a_v:.5f}, resid={sub['resid'].mean():+.5f}")
