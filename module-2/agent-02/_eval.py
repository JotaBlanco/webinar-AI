"""Test harness — score a predict function."""
import sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "skills" / "score-model"))
from score import score


def baseline_v0(sim_df, platform):
    """V0: just return the pre-computed yaw_rate_pred_rads (kinematic single-track)."""
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"]}, index=sim_df.index)


if __name__ == "__main__":
    import json
    result = score(baseline_v0)
    print(json.dumps(result, indent=2, default=str))
