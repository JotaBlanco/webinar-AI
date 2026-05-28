"""Check if there's a per-segment yaw-rate bias detectable from zero-steer windows.

If a segment has periods where delta is near zero, the measured yaw rate should
be near zero. If it's not, we may have a per-segment gyro bias we can estimate
from delta-near-zero windows."""
import os, glob
import numpy as np
import pandas as pd

SIM_ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/data/sim/segments"

for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]:
    files = sorted(glob.glob(f"{SIM_ROOT}/{plat}/*/*/*/sim.csv"))[:30]
    biases = []
    fractions = []
    for f in files:
        df = pd.read_csv(f)
        mask = (np.abs(df["delta_road_rad"]) < 0.005) & (df["v_mps"] > 3.0)
        if mask.sum() > 50:
            bias_est = df.loc[mask, "yaw_rate_meas_rads"].mean()
            biases.append(bias_est)
            fractions.append(mask.mean())
    biases = np.array(biases)
    fractions = np.array(fractions)
    print(f"{plat}: {len(biases)}/{len(files)} segs with >50 zero-steer samples")
    print(f"  per-seg bias mean={biases.mean():.5f}  std={biases.std():.5f}  "
          f"min={biases.min():.5f}  max={biases.max():.5f}")
    print(f"  fraction of zero-steer samples median={np.median(fractions):.2%}")
