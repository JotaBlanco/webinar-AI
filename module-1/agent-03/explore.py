"""Quick exploration: enumerate sim.csv files per platform, compute V0 yaw-rate RMSE."""
import os, glob
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03"
SIM_ROOT = f"{ROOT}/data/sim/segments"

def list_segments(platform):
    pat = f"{SIM_ROOT}/{platform}/*/*/*/sim.csv"
    return sorted(glob.glob(pat))

for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "TESLA_MODEL_3"]:
    files = list_segments(plat)
    print(f"{plat}: {len(files)} segments")

# Compute baseline yaw-rate RMSE across Ford segments
for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]:
    files = list_segments(plat)
    sq_err = []
    n_total = 0
    for f in files:
        df = pd.read_csv(f)
        e = df["yaw_rate_meas_rads"].values - df["yaw_rate_pred_rads"].values
        sq_err.append(np.sum(e * e))
        n_total += len(e)
    rmse = np.sqrt(np.sum(sq_err) / n_total)
    print(f"{plat}: V0 yaw-rate RMSE = {rmse:.6f} rad/s over {n_total} samples")
