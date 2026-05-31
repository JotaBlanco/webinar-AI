"""CTE is killed by drift. Test if removing per-segment mean residual helps CTE
on the truth side. Of course we can't see truth at predict time, but check the
mean residual statistic — is there a global yaw-rate bias per platform?
"""
import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "load-segments"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "work"))
os.chdir(ROOT)

import numpy as np
from load import load
from predict_v1 import predict as predict_v1

for platform in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
    print(f"\n=== {platform} ===")
    dfs = load(platform=platform)
    n_train = int(len(dfs) * 0.7)
    dfs_train = dfs[:n_train]
    means = []
    for df in dfs_train:
        v = df["v_mps"].to_numpy()
        yrm = df["yaw_rate_meas_rads"].to_numpy()
        pred = predict_v1(df, platform)["yaw_rate_pred_rads"].to_numpy()
        mask = v > 2.0
        r = pred[mask] - yrm[mask]
        means.append(r.mean())
    means = np.array(means)
    print(f"  per-segment mean residual: mean={means.mean():.5e}, median={np.median(means):.5e}, std={means.std():.5e}")
    print(f"  abs mean: {np.abs(means).mean():.5e}")
    # If the mean is consistently nonzero, a per-platform bias correction helps.
