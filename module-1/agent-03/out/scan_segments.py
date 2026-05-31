"""Scan all sim/segments to gather (v, delta_road, yaw_rate_meas, yaw_rate_pred)
for each platform. Tesla format differs (psi_dot_rads instead of yaw_rate_meas_rads).
"""
import os, glob, sys
import pandas as pd
import numpy as np

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/data/sim/segments"

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1",
             "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]

def truth_col(df):
    if "yaw_rate_meas_rads" in df.columns:
        return "yaw_rate_meas_rads"
    if "psi_dot_rads" in df.columns:
        return "psi_dot_rads"
    return None

def pred_col(df):
    if "yaw_rate_pred_rads" in df.columns:
        return "yaw_rate_pred_rads"
    if "psi_dot_rads" in df.columns:
        # Tesla — no separate pred — re-compute from v, delta
        return None
    return None

rows = []
for plat in PLATFORMS:
    files = glob.glob(os.path.join(BASE, plat, "*", "*", "*", "sim.csv"))
    print(f"{plat}: {len(files)} files", file=sys.stderr)
    n_used = 0
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception as e:
            continue
        tc = truth_col(df)
        if tc is None or "v_mps" not in df.columns or "delta_road_rad" not in df.columns:
            continue
        sub = df[["t_s", "v_mps", "delta_road_rad", tc]].rename(columns={tc: "yaw_truth"})
        sub["platform"] = plat
        sub["file"] = f
        if "yaw_rate_pred_rads" in df.columns:
            sub["yaw_v0"] = df["yaw_rate_pred_rads"]
        else:
            # Tesla: V0 baseline is KS open-loop (v/L)*tan(delta_road)
            sub["yaw_v0"] = np.nan  # compute later if needed
        rows.append(sub)
        n_used += 1
    print(f"  used {n_used}", file=sys.stderr)

big = pd.concat(rows, ignore_index=True)
print(f"Total samples: {len(big)}")
big.to_parquet("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/out/all_samples.parquet")

# Summary baseline rmse per platform
for plat, g in big.groupby("platform"):
    truth = g["yaw_truth"].to_numpy()
    v0 = g["yaw_v0"].to_numpy()
    mask = np.isfinite(truth) & np.isfinite(v0)
    if mask.sum() > 0:
        rmse = np.sqrt(np.mean((truth[mask]-v0[mask])**2))
        print(f"V0 RMSE {plat}: {rmse:.4f} rad/s  (n={mask.sum()})")
    else:
        print(f"V0 RMSE {plat}: no pred col")
