"""V0 baseline scoring."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))

import os
os.chdir(ROOT)

import pandas as pd
from score import score
from split import split

train, dev = split(dev_fraction=0.25, seed=42)
print(f"train segments: {len(train)}, dev segments: {len(dev)}")

def v0_predict(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"]
    return out

print("\n=== V0 on DEV (all platforms) ===")
res = score(v0_predict, segment_paths=dev)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
print(f"per_regime:    {res['per_regime']}")
print(f"failed:        {res['failed_segments']}")

print("\n=== V0 on TRAIN ===")
res = score(v0_predict, segment_paths=train)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
