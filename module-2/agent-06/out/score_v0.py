"""Score V0 passthrough baseline."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary  # type: ignore


def predict_v0(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    return out


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    result = score(predict_v0)
    print(format_summary(result))
    print()
    print("== headline ==")
    print(f"yaw_rate_rmse: {result['yaw_rate_rmse']:.6f}")
    print(f"cte_rmse:      {result['cte_rmse']:.6f}")
