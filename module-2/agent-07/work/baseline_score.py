"""Score V0 (passthrough yaw_rate_pred_rads) to get baseline KPIs."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

import os
os.chdir(ROOT)

import pandas as pd
from score import score


def v0_predict(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"]
    return out


if __name__ == "__main__":
    res = score(v0_predict)
    print("V0 BASELINE (all FORD_* segments):")
    print(f"  yaw_rate_rmse = {res['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse      = {res['cte_rmse']:.4f}")
    print(f"  n_segments    = {res['n_segments']}")
    print(f"  n_samples     = {res['n_samples']}")
    print(f"  failed        = {res['failed_segments']}")
    print("\nPer-platform:")
    for k, v in res["per_platform"].items():
        print(f"  {k}: yr={v['yaw_rate_rmse']:.6f}, cte={v['cte_rmse']:.4f}, n_seg={v['n_segments']}")
    print("\nPer-regime:")
    for k, v in res["per_regime"].items():
        print(f"  {k}: yr={v['yaw_rate_rmse']:.6f}, n_samples={v['n_samples']}")
