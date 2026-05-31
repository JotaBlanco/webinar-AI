"""Explore: baseline scores + fit per-platform params."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "load-segments"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))

from score import score
from load import load
from split import split

# V0 baseline: just return existing yaw_rate_pred_rads
def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float)
    return out

import os
os.chdir(str(ROOT))

# All FORD segments
all_paths = sorted((ROOT / "data" / "sim" / "segments").glob("FORD_*/**/sim.csv"))
print(f"Total FORD segments: {len(all_paths)}")

# Split
train, dev = split(all_paths, dev_fraction=0.25, seed=42)
print(f"Train: {len(train)}, Dev: {len(dev)}")

# Score V0 on dev
v0_dev = score(predict_v0, segment_paths=dev)
print("=== V0 on dev ===")
print(f"yaw RMSE: {v0_dev['yaw_rate_rmse']:.6f}")
print(f"CTE RMSE: {v0_dev['cte_rmse']:.4f}")
print(f"Per-platform: {v0_dev['per_platform']}")
print(f"Per-regime:   {v0_dev['per_regime']}")
