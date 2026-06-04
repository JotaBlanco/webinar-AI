"""Score V0 baseline (just return yaw_rate_pred_rads as-is)."""
import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT))

import os
os.chdir(ROOT)

from score import score, format_summary


def predict_v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


result = score(predict_v0)
print(format_summary(result))
print("\n\nBASELINE: yaw=%f, cte=%f" % (result["yaw_rate_rmse"], result["cte_rmse"]))
