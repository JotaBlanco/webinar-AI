"""Explore residuals on V1 to find what's still on the table."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

import numpy as np
import pandas as pd
from v1_baseline import predict_v1, PLATFORM_PARAMS_V1


# Look at one Lightning segment to inspect residuals
plat = "FORD_F_150_LIGHTNING_MK1"
segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
print(f"Lightning segs: {len(segs)}")

# Compute pooled residual moments and lag check
all_resid = []
all_dt = []
all_v = []
all_d = []
all_yr_truth = []
all_yr_pred = []
seg_biases = []
for p in segs[:50]:
    sim = pd.read_csv(p)
    pred = predict_v1(sim, plat)["yaw_rate_pred_rads"].to_numpy()
    truth = sim["yaw_rate_meas_rads"].to_numpy()
    v = sim["v_mps"].to_numpy()
    d = sim["delta_road_rad"].to_numpy()
    mask = v > 2
    seg_biases.append(np.mean(pred[mask] - truth[mask]))
    all_resid.extend((pred - truth)[mask])
    all_v.extend(v[mask])
    all_d.extend(d[mask])
    all_yr_truth.extend(truth[mask])
    all_yr_pred.extend(pred[mask])

all_resid = np.array(all_resid)
all_v = np.array(all_v)
all_d = np.array(all_d)
all_yr_truth = np.array(all_yr_truth)
all_yr_pred = np.array(all_yr_pred)
print(f"Pooled bias={np.mean(all_resid):+.5f}, std={np.std(all_resid):.5f}")
print(f"per-seg bias mean={np.mean(seg_biases):+.5f}  std={np.std(seg_biases):.5f}  min={np.min(seg_biases):+.5f}  max={np.max(seg_biases):+.5f}")

# Correlation of residual with various things
for name, x in [("v", all_v), ("delta", all_d), ("|yr|", np.abs(all_yr_truth))]:
    c = np.corrcoef(x, all_resid)[0,1]
    print(f"  corr(resid, {name}) = {c:+.4f}")

# Lag check: try shifting predictions by -1..+5 samples and see if mean-sq error improves
print("\nLag scan (pred shift relative to truth):")
for shift in [-3, -2, -1, 0, 1, 2, 3, 4, 5]:
    if shift > 0:
        p = all_yr_pred[shift:]
        t = all_yr_truth[:-shift]
    elif shift < 0:
        p = all_yr_pred[:shift]
        t = all_yr_truth[-shift:]
    else:
        p = all_yr_pred
        t = all_yr_truth
    rmse = np.sqrt(np.mean((p-t)**2))
    print(f"  shift={shift:+d}  rmse={rmse:.6f}")
