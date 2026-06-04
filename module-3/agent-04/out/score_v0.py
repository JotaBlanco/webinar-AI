"""Score V0 baseline (pass-through yaw_rate_pred_rads) across all platforms."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

import pandas as pd
from score import score, format_summary  # noqa


def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    result = score(predict_v0)
    print(format_summary(result))
    print("\nHEADLINE V0:")
    print(f"  yaw_rate_rmse = {result['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse      = {result['cte_rmse']:.4f}")
