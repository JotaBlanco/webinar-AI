"""V0 baseline: identity on yaw_rate_pred_rads."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa


def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    res = score(predict_v0)
    print(format_summary(res, top_n=5))
