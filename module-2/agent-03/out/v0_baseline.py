"""V0 baseline scoring - pass through yaw_rate_pred_rads."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-03")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
import os
os.chdir(ROOT)

from score import score, format_summary

def v0(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    return out

result = score(v0)
print(format_summary(result))
print()
print("HEADLINE: yaw_rmse=", result["yaw_rate_rmse"], "cte_rmse=", result["cte_rmse"])
