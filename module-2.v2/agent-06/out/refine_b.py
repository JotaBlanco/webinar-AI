"""Refine per-platform bias `b` to null the residual CTE drift.

We have CTE drift of ~+8m / -10m / -7m per Ford / MachE / Ioniq. The CTE
drift is dominated by the *integrated* signed yaw bias. We can iteratively
adjust `b` to null the per-platform signed yaw residual on the full sim set,
which should also pull the CTE drift toward zero.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-06")
SEG_ROOT = ROOT / "data" / "sim" / "segments"

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

# Load current coeffs
with (ROOT / "final-model" / "coeffs.json").open() as fh:
    COEFFS = json.load(fh)

# Compute the current signed yaw residual per platform across all sim with v>2
for plat in PLATFORMS:
    paths = sorted((SEG_ROOT / plat).glob("**/sim.csv"))
    coef = COEFFS[plat]
    a, K, b = coef["a"], coef["K"], coef["b"]
    sum_resid = 0.0
    n = 0
    for p in paths:
        df = pd.read_csv(p, usecols=["v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads"])
        df = df[df["v_mps"] > 2.0]
        if len(df) < 2:
            continue
        v = df["v_mps"].to_numpy(float)
        yr_v0 = df["yaw_rate_pred_rads"].to_numpy(float)
        t = df["yaw_rate_meas_rads"].to_numpy(float)
        pred = a * yr_v0 / (1.0 + K * v * v) + b
        sum_resid += float(np.sum(pred - t))
        n += len(df)
    mean_resid = sum_resid / n
    new_b = b - mean_resid
    print(f"{plat}: current_b={b:+.6f}, mean_yaw_resid={mean_resid:+.6f}, new_b={new_b:+.6f}")
    COEFFS[plat]["b"] = new_b

out_path = ROOT / "out" / "coeffs_v2.json"
out_path.write_text(json.dumps(COEFFS, indent=2))
print(f"\nSaved {out_path}")
