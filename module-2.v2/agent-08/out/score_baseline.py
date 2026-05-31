"""Score the V0 baseline (just echo yaw_rate_pred_rads) for reference."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-08")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
import pandas as pd

from score import score, format_summary


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


def main():
    # We need cwd to resolve data/sim/segments — score.py uses Path.cwd()
    import os
    os.chdir(str(ROOT))
    res = score(predict_v0)
    print(format_summary(res, top_n=5))


if __name__ == "__main__":
    main()
